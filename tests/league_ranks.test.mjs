import assert from 'node:assert/strict';
import test from 'node:test';
import { CF_RATING_COUNTS, LEAGUE_RANK_COUNTS, RANK_DISTRIBUTION_SOURCE } from '../pwa-frontend/src/rankDistributions.ts';
import { codeforcesTopPercent, leagueEquivalent, leagueEquivalentRange, leagueRankAtPercentile, LEAGUE_PERCENTILES } from '../pwa-frontend/src/leagueRanks.ts';

test('snapshot totals and all 31 League divisions agree with the saved source', () => {
  assert.equal(CF_RATING_COUNTS.reduce((sum, [, n]) => sum + n, 0), RANK_DISTRIBUTION_SOURCE.codeforcesPlayers);
  assert.equal(LEAGUE_RANK_COUNTS.reduce((sum, [, n]) => sum + n, 0), RANK_DISTRIBUTION_SOURCE.leaguePlayers);
  assert.equal(LEAGUE_RANK_COUNTS.length, 31);
  assert.deepEqual(LEAGUE_RANK_COUNTS.slice(0, 3).map(([name]) => name), ['Challenger', 'Grandmaster', 'Master']);
  assert.equal(LEAGUE_PERCENTILES.at(-1).topPercent, 100);
  assert.equal(RANK_DISTRIBUTION_SOURCE.leaguePopulation, 'North America Ranked Solo/Duo');
});

test('CF percentiles count every tied rating and preserve gaps and rounding', () => {
  const ratings = [-1000, 0, 799, 800, 1200, 1337, 1399.49, 1399.5, 1675, 2300, 2999, 3300, 4200];
  for (const elo of ratings) {
    const above = CF_RATING_COUNTS.filter(([r]) => r >= Math.round(elo)).reduce((sum, [, n]) => sum + n, 0);
    assert.equal(codeforcesTopPercent(elo), 100 * above / RANK_DISTRIBUTION_SOURCE.codeforcesPlayers);
  }
  let previous = 100;
  for (let elo = -20; elo <= 4300; elo++) {
    const top = codeforcesTopPercent(elo);
    assert.ok(top >= 0 && top <= previous, `${elo}: ${top}`);
    previous = top;
  }
});

test('League divisions use cumulative player shares with the correct direction at every boundary', () => {
  for (let i = 0; i < LEAGUE_PERCENTILES.length; i++) {
    const rank = LEAGUE_PERCENTILES[i];
    assert.equal(leagueRankAtPercentile(rank.topPercent), rank.label);
    if (i + 1 < LEAGUE_PERCENTILES.length) {
      assert.equal(leagueRankAtPercentile(rank.topPercent + 1e-8), LEAGUE_PERCENTILES[i + 1].label);
    }
  }
  assert.equal(leagueRankAtPercentile(0), 'Challenger');
  assert.equal(leagueRankAtPercentile(100), 'Iron IV');
});

test('the dated snapshot produces useful equivalents and ranges without inventing apex subdivisions', () => {
  assert.equal(leagueEquivalent(1337).label, 'Platinum III');
  assert.equal(leagueEquivalent(1337).topLabel, '22.6%');
  assert.equal(leagueEquivalent(1353).label, 'Platinum II');
  assert.equal(leagueEquivalentRange(1300, 1349), 'Platinum III → Platinum II');
  assert.equal(leagueEquivalentRange(1600, 1899), 'Emerald II → Diamond II');
  assert.equal(leagueEquivalent(2300).label, 'Master');
  assert.equal(leagueEquivalentRange(3300, null), 'Challenger');
  assert.match(leagueEquivalent(4200).topLabel, /^<0\.\d+%$/);
});
