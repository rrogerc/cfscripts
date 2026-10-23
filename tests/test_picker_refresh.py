import unittest
from unittest.mock import call, patch

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from cfscripts.core import picker
from cfscripts.core.statements import extract_atcoder_statement
from cfscripts.lib import submissions
from cfscripts.lib.api import CACHE_NONE
from cfscripts.web import server


ATCODER_PAGE = """
<html>
<head><title>C - Self-Stopping Shower</title></head>
<body>
  <div id="main-container">
    <a href="/contests/abc480">AtCoder Beginner Contest 480</a>
    <p>Time Limit: 2 sec / Memory Limit: 1024 MiB</p>
    <div id="task-statement">
      <span class="lang-en">
        <div class="part"><section>
          <h3>Problem Statement</h3>
          <p>Hot water runs for <var>K</var> seconds.</p>
          <script>alert(1)</script>
        </section></div>
        <div class="part"><section>
          <h3>Constraints</h3>
          <ul><li><var>1 \\le N \\le 2 \\times 10^5</var></li></ul>
        </section></div>
        <div class="part"><section>
          <h3>Input</h3>
          <p>Input is given from Standard Input:</p>
          <pre><var>N</var> <var>K</var>\r\n</pre>
        </section></div>
        <div class="part"><section>
          <h3>Output</h3>
          <p>Print the answer.</p>
        </section></div>
        <div class="part"><section>
          <h3>Sample Input 1</h3>
          <pre>3 4\r\n6 7 12\r\n</pre>
        </section></div>
        <div class="part"><section>
          <h3>Sample Output 1</h3>
          <pre>4\r\n</pre>
          <p>Press at <var>t = 0</var>.</p>
        </section></div>
      </span>
    </div>
  </div>
</body>
</html>
"""


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

    def test_atcoder_pick_checks_fresh_submissions_and_skips_newly_accepted_problem(self):
        problems = [
            {"id": "abc480_c", "contest_id": "abc480", "problem_index": "C", "name": "Latest C", "title": "C. Latest C"},
            {"id": "abc479_c", "contest_id": "abc479", "problem_index": "C", "name": "Previous C", "title": "C. Previous C"},
        ]
        client = TestClient(server.app)
        with patch.object(picker, "get_atcoder_problems", return_value=problems), \
             patch.object(picker, "get_abc_contest_ids", return_value={"abc479", "abc480"}), \
             patch.object(picker, "get_user_accepted_problems", side_effect=[set(), {"abc480_c"}]) as checks, \
             patch.object(server, "get_atcoder_problem_html", return_value="<div>ABC Statement</div>"):
            first = client.get("/api/atcpick?handle=Exonerate&index=c")
            second = client.get("/api/atcpick?handle=Exonerate&index=c")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["problem"]["id"], "abc480_c")
        self.assertEqual(first.json()["problem"]["contestId"], "abc480")
        self.assertEqual(first.json()["problem"]["index"], "C")
        self.assertEqual(second.json()["problem"]["id"], "abc479_c")
        self.assertEqual(checks.call_args_list, [call("Exonerate", CACHE_NONE), call("Exonerate", CACHE_NONE)])

    def test_extract_atcoder_statement_preserves_math_limits_samples_and_notes(self):
        html = extract_atcoder_statement(
            ATCODER_PAGE, "abc480", "abc480_c", "https://atcoder.jp/contests/abc480/tasks/abc480_c"
        )
        soup = BeautifulSoup(html, "html.parser")
        self.assertIsNone(soup.find("script"))
        self.assertEqual(soup.select_one(".header .title").get_text(), "C. Self-Stopping Shower")
        self.assertIn("2 sec", soup.select_one(".time-limit").get_text())
        self.assertIn("1024 MiB", soup.select_one(".memory-limit").get_text())
        self.assertIn("$$$K$$$", soup.get_text())
        self.assertIsNotNone(soup.select_one(".input-specification .atc-io-pre"))
        self.assertEqual(soup.select_one(".sample-test .input pre").get_text(), "3 4\n6 7 12\n")
        self.assertEqual(soup.select_one(".sample-test .output pre").get_text(), "4\n")
        self.assertIn("$$$t = 0$$$", soup.select_one(".note").get_text())


if __name__ == "__main__":
    unittest.main()
