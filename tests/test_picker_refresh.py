import unittest
from unittest.mock import call, patch

from fastapi.testclient import TestClient

from cfscripts.core import picker
from cfscripts.lib import submissions
from cfscripts.lib.api import CACHE_NONE
from cfscripts.web import server


class PickerRefreshTests(unittest.TestCase):
    def test_each_pick_checks_fresh_submissions_and_skips_a_newly_accepted_problem(self):
        problems = [
            {"contestId": 2050, "index": "C", "name": "Just solved", "rating": 1500},
            {"contestId": 2049, "index": "C", "name": "Next problem", "rating": 1500},
        ]
        accepted = {"verdict": "OK", "problem": {"contestId": 2050, "index": "C"}}
        client = TestClient(server.app)
        with patch.object(picker, "get_rated_problems", return_value=problems), \
             patch.object(picker, "get_div2_contest_ids", return_value={2049, 2050}), \
             patch.object(submissions, "get_submissions", side_effect=[[], [accepted]]) as checks, \
             patch.object(server, "get_problem_html", return_value="<div>Statement</div>"):
            first = client.get("/api/pick?handle=Exonerate&level=15")
            second = client.get("/api/pick?handle=Exonerate&level=15")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["problem"]["contestId"], 2050)
        self.assertEqual(second.json()["problem"]["contestId"], 2049)
        self.assertEqual(checks.call_args_list, [call("Exonerate", CACHE_NONE), call("Exonerate", CACHE_NONE)])


if __name__ == "__main__":
    unittest.main()
