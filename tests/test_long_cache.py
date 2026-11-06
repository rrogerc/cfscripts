import io
import json
import tempfile
import unittest
from collections import OrderedDict
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import requests
from requests_cache.backends.filesystem import FileCache
from requests_cache.policy.expiration import get_url_expiration
from urllib3.response import HTTPResponse

from cfscripts.lib import api, atcoder, contests, rating


class FakeCodeforces(requests.adapters.BaseAdapter):
    """Answers contest.standings and contest.ratingChanges, counting calls."""

    def __init__(self):
        super().__init__()
        self.phase = "SYSTEM_TEST"
        self.rating_changes = []
        self.calls = 0

    def send(self, request, **kwargs):
        self.calls += 1
        if "contest.standings" in request.url:
            result = {"contest": {"id": 2049, "phase": self.phase}, "problems": [], "rows": []}
        else:
            result = self.rating_changes
        body = json.dumps({"status": "OK", "result": result}).encode()
        raw = HTTPResponse(body=io.BytesIO(body), status=200, preload_content=False,
                           headers={"Content-Type": "application/json"}, request_url=request.url)
        return requests.adapters.HTTPAdapter().build_response(request, raw)

    def close(self):
        pass


class LongCacheExpiryTests(unittest.TestCase):
    def test_growing_lists_expire_but_per_contest_data_stays_cached(self):
        rules = api._long_session.settings.urls_expire_after
        list_urls = []

        def fake_codeforces(url, cache_type):
            list_urls.append(url)
            return {"problems": []}

        def fake_kenkoooo(url, cache_type):
            list_urls.append(url)
            return []

        # Record the URLs the pickers' list fetchers really request.
        with patch.object(contests, "get_results", side_effect=fake_codeforces), \
             patch.object(atcoder, "_throttled_get", side_effect=fake_kenkoooo):
            contests.get_problems()
            atcoder.get_problems()
            atcoder.get_abc_contest_ids()

        self.assertEqual(len(list_urls), 3)
        for url in list_urls:
            self.assertEqual(get_url_expiration(url, rules), timedelta(hours=1), url)
        for url in (
            "https://codeforces.com/api/contest.ratingChanges?contestId=2049",
            "https://codeforces.com/api/contest.standings?contestId=2049",
        ):
            self.assertIsNone(get_url_expiration(url, rules), url)


class LongCacheKeepsOnlyFinalResultsTests(unittest.TestCase):
    def setUp(self):
        # The real session, settings, and invalidation, with a scratch cache
        # directory and a fake Codeforces instead of the network.
        self.codeforces = FakeCodeforces()
        session = api._long_session
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        cache = FileCache(Path(scratch.name) / "long")
        cache._settings = session.settings
        self.addCleanup(cache.close)
        for patcher in (
            patch.object(session, "cache", cache),
            patch.object(session, "adapters", OrderedDict()),
            patch.object(api, "sleep"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        session.mount("https://", self.codeforces)

    def test_standings_are_kept_only_once_the_contest_finishes(self):
        contests.get_contest_and_standings(2049)
        contests.get_contest_and_standings(2049)
        self.assertEqual(self.codeforces.calls, 2)

        self.codeforces.phase = "FINISHED"
        contests.get_contest_and_standings(2049)
        contests.get_contest_and_standings(2049)
        self.assertEqual(self.codeforces.calls, 3)

    def test_rating_changes_are_kept_only_once_published(self):
        rating.get_rating_changes_for_contest(2049)
        rating.get_rating_changes_for_contest(2049)
        self.assertEqual(self.codeforces.calls, 2)

        self.codeforces.rating_changes = [{"handle": "Exonerate", "oldRating": 1500, "newRating": 1520}]
        rating.get_rating_changes_for_contest(2049)
        rating.get_rating_changes_for_contest(2049)
        self.assertEqual(self.codeforces.calls, 3)


if __name__ == "__main__":
    unittest.main()
