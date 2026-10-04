import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from cfscripts.core.statements import extract_statement, render_statement
from cfscripts.web import db, restatements, server, solutions, statements
from test_ranked_queue import PAYLOAD


FIELDS = {
    "task": r"Given $$$a_1, a_2$$$, print their sum.",
    "input": r"Read $$$n$$$, then the array.",
    "output": "Print the answer.",
    "constraints": r"$$$1 \le n \le 100$$$; $$$a_i \le 10^9$$$.",
}


def model_content(fields=FIELDS):
    return '\n\n'.join(f'## {key.title()}\n{value}' for key, value in fields.items())


class RestatementGenerationTests(unittest.TestCase):
    def setUp(self):
        self.html = render_statement(PAYLOAD, 2049, "C")

    def generate(self, html=None, fields=None):
        with patch.object(restatements, "_chat", return_value=(model_content(fields or FIELDS), "test-model")):
            return restatements.generate(html or self.html)

    def test_keeps_exact_limits_and_sample_markup_without_rewriting_original(self):
        html, model = self.generate()
        original = BeautifulSoup(self.html, "html.parser")
        result = BeautifulSoup(html, "html.parser")
        self.assertEqual(model, "test-model")
        self.assertEqual(str(result.select_one(".header")), str(original.select_one(".header")))
        self.assertEqual(str(result.select_one(".sample-tests")), str(original.select_one(".sample-tests")))
        self.assertEqual([node.get_text() for node in result.select("pre")], [node.get_text() for node in original.select("pre")])
        self.assertIn(r"$$$a_1, a_2$$$", result.get_text())
        self.assertIn("sample explanation", original.get_text())
        self.assertNotIn("sample explanation", result.get_text())

    def test_raw_html_and_unsafe_links_from_model_are_inert_and_math_survives(self):
        fields = {**FIELDS, "task": '<script>alert(1)</script>\n\n[click](javascript:alert(1))\n\n'
                  r'$$$a_i < a_{i+1} \land x > 0$$$'}
        html, _ = self.generate(fields=fields)
        result = BeautifulSoup(html, "html.parser")
        self.assertIsNone(result.find("script"))
        self.assertIsNone(result.find("a"))
        self.assertNotIn("<em>", html)
        self.assertIn(r"$$$a_i < a_{i+1} \land x > 0$$$", result.get_text())

    def test_rejects_malformed_or_incomplete_model_response(self):
        for response in ["unstructured response", "[]", model_content({**FIELDS, "task": ""}),
                         model_content({**FIELDS, "output": ""}),
                         model_content({**FIELDS, "input": ""}), model_content({"task": "Only a task"}),
                         model_content() + '\n## Task\nRepeated task']:
            with self.subTest(response=response), patch.object(restatements, "_chat", return_value=(response, "test")):
                with self.assertRaises(solutions.SolutionUnavailable):
                    restatements.generate(self.html)

    def test_prompt_uses_only_statement_and_preserves_definitions_in_notes(self):
        with patch.object(restatements, "_chat", return_value=(model_content(), "test")) as chat, \
             patch.object(solutions, "get_editorial_excerpt", side_effect=AssertionError("No editorial")):
            restatements.generate(self.html)
        prompt = chat.call_args.args[0]
        self.assertIn("sample explanation", prompt)
        self.assertIn(r"$$$a_i \le 10^9$$$", prompt)
        self.assertIn("aggregate limits", prompt)
        self.assertIn("Do not add observations, algorithms, hints, code", prompt)
        self.assertNotIn("## The key idea", prompt)

    def test_source_review_restores_an_explicit_allowance_missing_from_draft(self):
        html = self.html.replace('<div class="input-specification">',
                                 '<div><p>Duplicate values are allowed.</p></div><div class="input-specification">')
        corrected = {**FIELDS, "constraints": FIELDS["constraints"] + '\n\nDuplicate values are allowed.'}
        with patch.object(restatements, "_chat", side_effect=[
            (model_content(), "draft-model"), (model_content(corrected), "review-model")
        ]) as chat:
            result, model = restatements.generate(html)
        self.assertIn('Duplicate values are allowed.', result)
        self.assertEqual(model, 'review-model')
        review = chat.call_args.args[0]
        self.assertIn('Duplicate values are allowed.', review)
        self.assertIn(model_content(), review)
        self.assertIn('Review the draft', review)

    def test_diagrams_reach_prompt_and_are_retained(self):
        html = self.html.replace('<div class="input-specification">',
                                 '<div><img src="https://example.com/graph.png" alt="Graph with five nodes"></div>'
                                 '<div class="input-specification">')
        with patch.object(restatements, "_chat", return_value=(model_content(), "test")) as chat:
            result, _ = restatements.generate(html)
        self.assertIn("Graph with five nodes", chat.call_args.args[0])
        self.assertIn("https://example.com/graph.png", chat.call_args.args[0])
        self.assertEqual(BeautifulSoup(result, "html.parser").img["src"], "https://example.com/graph.png")

    def test_tables_in_preserved_contract_sections_are_not_duplicated(self):
        html = self.html.replace('<div class="sample-tests">',
                                 '<div><div class="section-title">Interaction</div>'
                                 '<table><tr><td>Exact command rule</td></tr></table></div>'
                                 '<div class="sample-tests">')
        result, _ = self.generate(html=html)
        self.assertEqual(len(BeautifulSoup(result, "html.parser").select("table")), 1)
        self.assertIn("Exact command rule", result)

    def test_interactive_contract_and_merged_command_tables_survive_exactly(self):
        page = (Path(__file__).parent / "fixtures" / "codeforces_2109_c1.html").read_text()
        html = extract_statement(page, 2109, "C1", "https://codeforces.me/problemset/problem/2109/C1")
        fields = {**FIELDS, "task": "Interactive problem: make the unknown integer equal to the target.", "output": ""}
        with patch.object(restatements, "_chat", return_value=(model_content(fields), "test")) as chat:
            result, _ = restatements.generate(html)
        before, after = BeautifulSoup(html, "html.parser"), BeautifulSoup(result, "html.parser")
        self.assertEqual([str(table) for table in before.select("table")], [str(table) for table in after.select("table")])
        interaction = next(node.parent for node in before.select(".section-title") if node.get_text() == "Interaction")
        self.assertIn(str(interaction), result)
        self.assertIn('"-1"', after.get_text())
        self.assertIn("does not count", after.get_text())
        self.assertIn("flush", after.get_text())
        self.assertIn("Command | Constraint | Result", chat.call_args.args[0])


class RestatementApiTests(unittest.TestCase):
    def setUp(self):
        self.html = render_statement(PAYLOAD, 2049, "C")
        self.digest = statements.statement_hash(self.html)
        self.row = {"status": "done", "content_html": "<div>Pure task</div>",
                    "statement_hash": self.digest, "version": restatements.RESTATEMENT_VERSION,
                    "updated_ts": 100}
        self.client = TestClient(server.app)

    def request(self):
        return self.client.post("/api/restate?contest_id=2049&index=C")

    def test_current_cache_returns_without_model_or_lock(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
            stack.enter_context(patch.object(db, "connect"))
            stack.enter_context(patch.object(db, "get_restatement", return_value=self.row))
            claim = stack.enter_context(patch.object(db, "claim_restatement"))
            generate = stack.enter_context(patch.object(restatements, "generate"))
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["restatement"]["html"], self.row["content_html"])
        claim.assert_not_called()
        generate.assert_not_called()

    def test_source_or_prompt_change_regenerates(self):
        for change in ({"statement_hash": "old"}, {"version": 0}):
            with self.subTest(change=change), ExitStack() as stack:
                stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
                stack.enter_context(patch.object(db, "connect"))
                stack.enter_context(patch.object(db, "get_restatement", return_value={**self.row, **change}))
                claim = stack.enter_context(patch.object(db, "claim_restatement", return_value={"updated_ts": 200}))
                generate = stack.enter_context(patch.object(restatements, "generate", return_value=("Safe HTML", "test")))
                finish = stack.enter_context(patch.object(db, "finish_restatement", return_value=self.row))
                response = self.request()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(claim.call_args.args[3:5], (self.digest, restatements.RESTATEMENT_VERSION))
            generate.assert_called_once_with(self.html)
            self.assertEqual(finish.call_args.args[3:6], (200, "Safe HTML", "test"))

    def test_concurrent_request_returns_pending_without_duplicate_generation(self):
        pending = {**self.row, "status": "pending"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
            stack.enter_context(patch.object(db, "connect"))
            stack.enter_context(patch.object(db, "get_restatement", return_value=pending))
            stack.enter_context(patch.object(db, "claim_restatement", return_value=None))
            generate = stack.enter_context(patch.object(restatements, "generate"))
            response = self.request()
        self.assertEqual(response.json()["restatement"]["status"], "pending")
        self.assertIsNone(response.json()["restatement"]["html"])
        generate.assert_not_called()

    def test_failed_generation_releases_its_lock_and_returns_readable_error(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
            stack.enter_context(patch.object(db, "connect"))
            stack.enter_context(patch.object(db, "get_restatement", return_value=None))
            stack.enter_context(patch.object(db, "claim_restatement", return_value={"updated_ts": 200}))
            stack.enter_context(patch.object(restatements, "generate", side_effect=solutions.SolutionUnavailable("Model unavailable")))
            release = stack.enter_context(patch.object(db, "release_restatement"))
            response = self.request()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Model unavailable")
        self.assertEqual(release.call_args.args[1:], (2049, "C", 200))

    def test_invalid_ids_fail_before_statement_or_model_access(self):
        with patch.object(server, "get_problem_html") as statement:
            for query in ("contest_id=0&index=A", "contest_id=-1&index=A", "contest_id=1&index=abc"):
                with self.subTest(query=query):
                    self.assertEqual(self.client.post(f"/api/restate?{query}").status_code, 422)
        statement.assert_not_called()


if __name__ == "__main__":
    unittest.main()
