import unittest
from datetime import timedelta
from unittest.mock import patch

from requests_cache.policy.expiration import get_url_expiration

from cfscripts.lib import api, atcoder, contests


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


if __name__ == "__main__":
    unittest.main()
