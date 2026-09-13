import assert from 'node:assert/strict';
import test from 'node:test';
import { rankedRank } from '../pwa-frontend/src/ranks.ts';

test('Codeforces titles keep their real boundaries and advance IV through I', () => {
  const cases = [
    [-12, 'Newbie IV'], [299, 'Newbie IV'], [300, 'Newbie III'],
    [600, 'Newbie II'], [900, 'Newbie I'], [1199, 'Newbie I'],
    [1200, 'Pupil IV'], [1249, 'Pupil IV'], [1250, 'Pupil III'],
    [1300, 'Pupil II'], [1350, 'Pupil I'], [1399, 'Pupil I'],
    [1400, 'Specialist IV'], [1599, 'Specialist I'],
    [1600, 'Expert IV'], [1674, 'Expert IV'], [1675, 'Expert III'],
    [1750, 'Expert II'], [1825, 'Expert I'], [1899, 'Expert I'],
    [1900, 'Candidate Master IV'], [2099, 'Candidate Master I'],
    [2100, 'Master IV'], [2299, 'Master I'],
    [2300, 'International Master IV'], [2325, 'International Master III'],
    [2350, 'International Master II'], [2375, 'International Master I'],
    [2399, 'International Master I'], [2400, 'Grandmaster IV'], [2599, 'Grandmaster I'],
    [2600, 'International Grandmaster IV'], [2700, 'International Grandmaster III'],
    [2800, 'International Grandmaster II'], [2900, 'International Grandmaster I'],
    [2999, 'International Grandmaster I'], [3000, 'Legendary Grandmaster IV'],
    [3100, 'Legendary Grandmaster III'], [3200, 'Legendary Grandmaster II'],
    [3300, 'Legendary Grandmaster I'], [4200, 'Legendary Grandmaster I'],
  ];
  for (const [elo, label] of cases) assert.equal(rankedRank(elo).label, label, `${elo} Elo`);
});

test('progress and the promotion target agree with the displayed whole-number Elo', () => {
  const rank = rankedRank(1337);
  assert.equal(rank.range, '1300–1349');
  assert.equal(rank.progress, 0.74);
  assert.deepEqual(rank.next, { label: 'Pupil I', min: 1350 });
  assert.equal(rankedRank(1399.49).label, 'Pupil I');
  assert.deepEqual(rankedRank(1399.49).next, { label: 'Specialist IV', min: 1400 });
  assert.equal(rankedRank(1399.5).rating, 1400);
  assert.equal(rankedRank(1399.5).label, 'Specialist IV');
  assert.equal(rankedRank(1399.5).progress, 0);
  assert.equal(rankedRank(1398.5).label, 'Pupil I'); // Demotion uses the same boundaries.
  assert.equal(rankedRank(-12).progress, 0);
  assert.equal(rankedRank(4200).range, '3300+');
  assert.equal(rankedRank(4200).next, null);
  assert.equal(rankedRank(4200).progress, 1);
});
