import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from cfscripts.lib.api import ApiError
from cfscripts.web import server


class ProblemTagsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_returns_tags_for_the_exact_problem(self):
        problems = [
            {"contestId": 2109, "index": "C2", "tags": ["math"]},
            {"contestId": 2110, "index": "C1", "tags": ["dp"]},
            {"contestId": 2109, "index": "C1", "tags": ["constructive algorithms", "interactive"]},
        ]
        with patch.object(server, "get_problems", return_value=problems):
            result = self.client.get("/api/tags?contest_id=2109&index=C1")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"tags": ["constructive algorithms", "interactive"]})

    def test_problem_without_tags_returns_an_empty_list(self):
        for problem in [{"contestId": 2109, "index": "C1"},
                        {"contestId": 2109, "index": "C1", "tags": []}]:
            with self.subTest(problem=problem), patch.object(server, "get_problems", return_value=[problem]):
                result = self.client.get("/api/tags?contest_id=2109&index=C1")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), {"tags": []})

    def test_unknown_problem_returns_not_found(self):
        with patch.object(server, "get_problems", return_value=[]):
            result = self.client.get("/api/tags?contest_id=2109&index=C1")
        self.assertEqual(result.status_code, 404)

    def test_api_failure_is_reported(self):
        with patch.object(server, "get_problems", side_effect=ApiError("Codeforces unavailable")):
            result = self.client.get("/api/tags?contest_id=2109&index=C1")
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()["detail"], "Codeforces unavailable")


if __name__ == "__main__":
    unittest.main()
