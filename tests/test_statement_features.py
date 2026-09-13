import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from cfscripts.core.scraper import NoEditorial, get_input_spec_paragraphs, get_sample_input_lines
from cfscripts.core.statements import render_statement
from cfscripts.web import db, server, solutions, statements
from test_ranked_queue import PAYLOAD


class StatementAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.html = render_statement(PAYLOAD, 2049, "C")
        self.digest = statements.statement_hash(self.html)
        self.annotation = {
            "v": solutions.LINEMAP_VERSION,
            "statement_hash": self.digest,
            "para_count": 1,
            "lines": [{"line": 3, "para": 1, "clause": 1, "kind": "array",
                       "vars": [{"tex": "a_i", "text": "array value"}],
                       "text": "The array values"}],
        }

    def row(self, annotation=None):
        return {"status": "done", "content_json": json.dumps(annotation or self.annotation)}

    def test_annotation_cache_is_bound_to_exact_statement_not_just_shape(self):
        self.assertTrue(server._linemap_current(self.row(), self.digest))
        changed = self.html.replace("Read", "First read")
        self.assertEqual(len(get_input_spec_paragraphs(changed)), 1)
        self.assertFalse(server._linemap_current(self.row(), statements.statement_hash(changed)))
        legacy = {**self.annotation, "v": 2}
        legacy.pop("statement_hash")
        self.assertFalse(server._linemap_current(self.row(legacy), self.digest))

    def test_generator_uses_same_paragraphs_and_sample_lines_as_display(self):
        self.assertEqual(get_sample_input_lines(self.html), ["", "2", "1  2"])
        with patch.object(solutions, "_chat", return_value=(json.dumps(self.annotation), "test-model")) as chat:
            result, model = solutions.generate_linemap(2049, "C", html=self.html)
        self.assertEqual(result["statement_hash"], self.digest)
        self.assertEqual(result["para_count"], 1)
        self.assertEqual(result["lines"][0]["kind"], "array")
        prompt = chat.call_args.args[0]
        self.assertIn("[3] (2 tokens) 1  2", prompt)
        self.assertIn(r"$$$a_i \le 10^9$$$", prompt)
        self.assertEqual(model, "test-model")

    def test_cached_annotations_reuse_without_another_model_call(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
            stack.enter_context(patch.object(db, "connect"))
            stack.enter_context(patch.object(db, "get_linemap", return_value=self.row()))
            chat = stack.enter_context(patch.object(solutions, "_chat", side_effect=AssertionError("No model call")))
            response = TestClient(server.app).post("/api/linemap?contest_id=2049&index=C")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["linemap"]["data"]["statement_hash"], self.digest)
        chat.assert_not_called()

    def test_old_annotations_regenerate_for_new_statement(self):
        old = {**self.annotation, "statement_hash": "previous-statement"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "get_problem_html", return_value=self.html))
            stack.enter_context(patch.object(db, "connect"))
            stack.enter_context(patch.object(db, "get_linemap", return_value=self.row(old)))
            discard = stack.enter_context(patch.object(db, "discard_linemap"))
            stack.enter_context(patch.object(db, "claim_linemap", return_value={"status": "pending"}))
            stack.enter_context(patch.object(solutions, "_chat", return_value=(json.dumps(self.annotation), "test-model")))
            finish = stack.enter_context(patch.object(db, "finish_linemap", return_value=self.row()))
            response = TestClient(server.app).post("/api/linemap?contest_id=2049&index=C")
        self.assertEqual(response.status_code, 200)
        discard.assert_called_once()
        self.assertEqual(json.loads(finish.call_args.args[3])["statement_hash"], self.digest)

    def test_solution_prompt_preserves_statement_math_and_samples(self):
        with patch.object(solutions, "get_problem_html", return_value=self.html), \
             patch.object(solutions, "get_editorial_excerpt", side_effect=NoEditorial()), \
             patch.object(solutions, "_chat", return_value=("Explanation", "test-model")) as chat:
            content, source, model = solutions.generate(2049, "C", "Test Problem")
        self.assertEqual((content, source, model), ("Explanation", None, "test-model"))
        self.assertIn(r"$$$a_i \le 10^9$$$", chat.call_args.args[0])
        self.assertIn("1  2", chat.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
