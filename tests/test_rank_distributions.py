import unittest

from scripts.update_rank_distributions import cf_counts, league_counts, LEAGUE_NAMES


def league_page(region='na', names=LEAGUE_NAMES, bad_total=False):
    rows = []
    for i, name in enumerate(names):
        # The source uses numeric divisions; the UI uses Roman numerals.
        name = name.replace(' IV', ' 4').replace(' III', ' 3').replace(' II', ' 2').replace(' I', ' 1')
        total = i + 2 if bad_total else i + 1
        rows.append(f'<tr><td>{name}</td><td>1 (0.1%)</td><td>{total} (0.1%)</td></tr>')
    return (f'<select id="selectChampionRegion"><option value="{region}" selected></option></select>'
            '<table><caption>Detailed league stats</caption><tbody>' + ''.join(rows) + '</tbody></table>')


class RankDistributionImportTests(unittest.TestCase):
    def test_aggregates_cf_ratings_including_ties_without_saving_profiles(self):
        self.assertEqual(cf_counts({'status': 'OK', 'result': [
            {'rating': 1300, 'handle': 'one'}, {'rating': 1300, 'handle': 'two'}, {'rating': -5},
        ]}), [(-5, 1), (1300, 2)])

    def test_rejects_failed_or_incomplete_cf_data(self):
        for payload in [{'status': 'FAILED'}, {'status': 'OK', 'result': []},
                        {'status': 'OK', 'result': [{'rating': True}]},
                        {'status': 'OK', 'result': [{}]}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                cf_counts(payload)

    def test_uses_counts_and_all_real_league_divisions(self):
        result = league_counts(league_page())
        self.assertEqual([name for name, _ in result], LEAGUE_NAMES)
        self.assertEqual(sum(count for _, count in result), 31)

    def test_rejects_challenges_wrong_regions_missing_ranks_and_bad_totals(self):
        for html in ['<html>Verify your browser</html>', league_page(region='kr'),
                     league_page(names=LEAGUE_NAMES[:-1]), league_page(bad_total=True)]:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                league_counts(html)


if __name__ == '__main__':
    unittest.main()
