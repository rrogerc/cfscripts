import unittest
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from requests import Response
from requests.exceptions import Timeout

from cfscripts.core import statements as provider
from cfscripts.web import db, server, statements


PROBLEM = {"contestId": 2049, "index": "C", "name": "Test Problem", "rating": 1300}
PAYLOAD = {
    "status": 200,
    "template": "problem.show",
    "data": {"problem": {
        "pid": "CF2049C", "type": "CF",
        "contenu": {"description": "A translated statement that must not be used"},
        "content": {
            "locale": "en", "name": "Test Problem", "background": "",
            "description": r"Find $ a_1 + a_2 $ where $ a_i \le 10^9 $.",
            "formatI": r"Read $ n $ ($ 1 \le n \le 100 $) — the length.",
            "formatO": "Print the answer.", "hint": "A **sample explanation**.",
        },
        "limits": {"time": [2000], "memory": [256000]},
        "samples": [["\n2\n1  2\n", "3\n"], ["<literal>\n", "&\n"]],
        "tags": ["spoiler"],
    }},
}


def response(status=200, payload=PAYLOAD):
    result = Response()
    result.status_code = status
    html = provider.render_statement(payload, 2049, "C")
    result._content = ("<html><head><title>Problem - 2049C - Codeforces</title></head>"
                       f"<body>{html}</body></html>").encode()
    result.encoding = "utf-8"
    return result


class StatementProviderTests(unittest.TestCase):
    def test_uses_complete_original_english_html(self):
        with patch.object(provider.requests, "get", return_value=response()) as get:
            statement = provider.fetch_statement(2049, "C")
        self.assertEqual(get.call_args.args[0], "https://codeforces.me/problemset/problem/2049/C?locale=en")
        self.assertEqual(get.call_args.kwargs["headers"]["Accept"], "text/html")
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 15))
        self.assertEqual(statement.source_url, get.call_args.args[0])
        self.assertIn("Test Problem", statement.html)
        self.assertNotIn("translated", statement.html)
        self.assertNotIn("spoiler", statement.html)

    def test_preserves_math_limits_samples_and_existing_statement_structure(self):
        html = provider.render_statement(PAYLOAD, 2049, "C")
        soup = BeautifulSoup(html, "html.parser")
        self.assertIn(r"$$$a_i \le 10^9$$$", soup.get_text())
        self.assertIsNone(soup.find("em"))
        self.assertIn("2 seconds", soup.select_one(".time-limit").get_text())
        self.assertIn("256 megabytes", soup.select_one(".memory-limit").get_text())
        self.assertTrue(soup.select_one(".input-specification > p"))
        self.assertTrue(soup.select_one(".output-specification > p"))
        samples = soup.select(".sample-test .input pre")
        self.assertEqual([s.get_text() for s in samples], [s[0] for s in PAYLOAD["data"]["problem"]["samples"]])
        self.assertEqual(soup.select_one(".note strong").get_text(), "sample explanation")

    def test_display_math_and_images_are_preserved(self):
        payload = deepcopy(PAYLOAD)
        payload["data"]["problem"]["content"]["description"] += (
            "\n\n$$x_1 < x_2$$\n\n![Diagram](https://example.com/diagram.png)"
        )
        html = provider.render_statement(payload, 2049, "C")
        soup = BeautifulSoup(html, "html.parser")
        self.assertIn(r"\[x_1 < x_2\]", soup.get_text())
        self.assertEqual(soup.img["src"], "https://example.com/diagram.png")

    def test_untrusted_content_cannot_inject_html(self):
        payload = deepcopy(PAYLOAD)
        content = payload["data"]["problem"]["content"]
        content["name"] = '<img src="x" onerror="alert(1)">'
        content["description"] = '<script>alert(1)</script>\n\n[click](javascript:alert(1))'
        soup = BeautifulSoup(provider.render_statement(payload, 2049, "C"), "html.parser")
        self.assertIsNone(soup.find("script"))
        self.assertIsNone(soup.find("img"))
        self.assertIsNone(soup.find("a"))

    def test_incorrect_or_incomplete_provider_data_is_rejected(self):
        for field, value in [("pid", "CF1A"), ("type", "P"), ("samples", []), ("limits", {})]:
            payload = deepcopy(PAYLOAD)
            payload["data"]["problem"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                provider.render_statement(payload, 2049, "C")
        for field, value in [("locale", "zh-CN"), ("description", ""), ("formatI", None)]:
            payload = deepcopy(PAYLOAD)
            payload["data"]["problem"]["content"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                provider.render_statement(payload, 2049, "C")

    def test_transport_errors_and_challenge_pages_are_readable_errors(self):
        challenge = response()
        challenge._content = b"<html>Please verify your browser</html>"
        for result in [response(403), response(429), challenge, Timeout()]:
            with self.subTest(result=result), patch.object(provider.requests, "get", side_effect=[result]):
                with self.assertRaisesRegex(provider.ProblemUnavailable, "problem statement"):
                    provider.fetch_statement(2049, "C")


class StatementCacheTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(db, "connect"))
        self.cached = stack.enter_context(patch.object(db, "get_statement", return_value=None))
        self.save = stack.enter_context(patch.object(db, "save_statement"))
        self.fetch = stack.enter_context(patch.object(statements, "fetch_statement"))
        self.statement = provider.Statement("<div>Saved statement</div>", "https://www.luogu.com.cn/problem/CF2049C")
        self.fetch.return_value = self.statement

    def test_cache_hit_needs_no_provider_even_during_an_outage(self):
        self.cached.return_value = {"html": self.statement.html}
        self.fetch.side_effect = provider.ProblemUnavailable("Provider offline")
        self.assertEqual(statements.get_problem_html(2049, "C"), self.statement.html)
        self.fetch.assert_not_called()

    def test_first_load_is_persisted_before_it_is_returned(self):
        self.assertEqual(statements.get_problem_html(2049, "C"), self.statement.html)
        self.save.assert_called_once()
        self.assertEqual(self.save.call_args.args[1:5], (2049, "C", self.statement.html, self.statement.source_url))

    def test_failed_refresh_does_not_replace_a_good_cached_statement(self):
        self.cached.return_value = {"html": self.statement.html}
        self.fetch.side_effect = provider.ProblemUnavailable("Provider offline")
        with self.assertRaises(provider.ProblemUnavailable):
            statements.get_problem_html(2049, "C", refresh=True)
        self.save.assert_not_called()
        self.assertEqual(statements.get_problem_html(2049, "C"), self.statement.html)


class RankedQueueTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(db, "connect"))
        stack.enter_context(patch.object(server, "_ranked_snapshot", return_value={
            "elo": 1337, "seeded": False, "wins": 0, "losses": 2,
            "server_now": 1000, "active": None, "history": [],
        }))
        stack.enter_context(patch.object(db, "fetch_matches", return_value=[]))
        stack.enter_context(patch.object(server.ranked, "pick_ranked_problem", return_value=PROBLEM))
        self.cached = stack.enter_context(patch.object(db, "get_statement", return_value=None))
        self.save = stack.enter_context(patch.object(db, "save_statement"))
        self.insert = stack.enter_context(patch.object(db, "insert_match"))
        self.insert.return_value = {"id": 5, "contest_id": 2049, "problem_index": "C",
                                   "problem_name": "Test Problem", "start_ts": 2000, "deadline_ts": 3800}

    def test_unavailable_statement_does_not_start_match_or_write_bad_cache(self):
        with patch.object(provider.requests, "get", return_value=response(503)):
            result = self.client.post("/api/ranked/queue?handle=Exonerate")
        self.assertEqual(result.status_code, 502)
        self.assertIn("problem statement", result.json()["detail"])
        self.insert.assert_not_called()
        self.save.assert_not_called()

    def test_match_can_start_from_persistent_cache_while_provider_is_down(self):
        self.cached.return_value = {"html": "<div>Cached problem</div>"}
        with patch.object(provider.requests, "get", side_effect=AssertionError("Network must not be used")):
            result = self.client.post("/api/ranked/queue?handle=Exonerate")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["html"], self.cached.return_value["html"])
        self.insert.assert_called_once()

    def test_statement_is_saved_before_full_match_clock_starts(self):
        events = []

        def get(*args, **kwargs):
            events.append("fetch_statement")
            return response()

        def clock():
            events.append("start_clock")
            return 2000

        self.save.side_effect = lambda *args: events.append("save_statement")
        with patch.object(provider.requests, "get", side_effect=get), patch.object(server, "time", side_effect=clock):
            result = self.client.post("/api/ranked/queue?handle=Exonerate")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["server_now"], 2000)
        self.assertNotIn("problem_rating", result.json()["active"])
        self.assertEqual(self.insert.call_args.args[3:5], (2000, 3800))
        self.assertEqual(events, ["fetch_statement", "save_statement", "start_clock"])

    def test_cache_write_failure_does_not_start_a_match(self):
        self.save.side_effect = RuntimeError("Database write failed")
        with patch.object(provider.requests, "get", return_value=response()):
            result = TestClient(server.app, raise_server_exceptions=False).post("/api/ranked/queue?handle=Exonerate")
        self.assertEqual(result.status_code, 500)
        self.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
