// Codeforces title boundaries. Subdivisions are specific to CF Picker.
// https://codeforces.com/blog/entry/142495
export const RANK_TIERS = [
  { name: 'Newbie', min: 0 },
  { name: 'Pupil', min: 1200 },
  { name: 'Specialist', min: 1400 },
  { name: 'Expert', min: 1600 },
  { name: 'Candidate Master', min: 1900 },
  { name: 'Master', min: 2100 },
  { name: 'International Master', min: 2300 },
  { name: 'Grandmaster', min: 2400 },
  { name: 'International Grandmaster', min: 2600 },
  { name: 'Legendary Grandmaster', min: 3000 },
] as const;

export const SUBDIVISIONS = ['IV', 'III', 'II', 'I'] as const;

export function rankedRank(elo: number) {
  // Match the whole-number Elo already displayed throughout Ranked.
  const rating = Math.round(elo);
  const tierIndex = Math.max(0, RANK_TIERS.findLastIndex(tier => rating >= tier.min));
  const tier = RANK_TIERS[tierIndex];
  const nextTier = RANK_TIERS[tierIndex + 1];
  // Bounded tiers split evenly. Legendary is open-ended: 100 Elo per
  // subdivision, with Legendary Grandmaster I continuing above 3300.
  const step = nextTier ? (nextTier.min - tier.min) / 4 : 100;
  const subdivision = Math.min(3, Math.max(0, Math.floor((rating - tier.min) / step)));
  const min = tier.min + subdivision * step;
  const next = subdivision < 3
    ? { label: `${tier.name} ${SUBDIVISIONS[subdivision + 1]}`, min: min + step }
    : nextTier ? { label: `${nextTier.name} IV`, min: nextTier.min } : null;
  const label = `${tier.name} ${SUBDIVISIONS[subdivision]}`;
  const range = tierIndex === 0 && subdivision === 0
    ? `Below ${min + step}`
    : next ? `${min}–${next.min - 1}` : `${min}+`;
  const progress = next ? Math.min(1, Math.max(0, (rating - min) / step)) : 1;

  return { rating, label, tierIndex, subdivision, min, next, range, progress };
}
