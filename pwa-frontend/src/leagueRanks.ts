import { CF_RATING_COUNTS, LEAGUE_RANK_COUNTS, RANK_DISTRIBUTION_SOURCE } from './rankDistributions.ts';

export { RANK_DISTRIBUTION_SOURCE };

let cumulative = 0;
const cfCountsBelow = CF_RATING_COUNTS.map(([rating, count]) => {
  const below = cumulative;
  cumulative += count;
  return { rating, below };
});

let leagueCumulative = 0;
export const LEAGUE_PERCENTILES = LEAGUE_RANK_COUNTS.map(([label, count]) => {
  leagueCumulative += count;
  return { label, topPercent: 100 * leagueCumulative / RANK_DISTRIBUTION_SOURCE.leaguePlayers };
});

/** Share of the active CF sample rated at or above the displayed Elo.
 * Binary search preserves exact counts and ties without interpolating bins. */
export function codeforcesTopPercent(elo: number): number {
  const rating = Math.round(elo);
  let lo = 0;
  let hi = cfCountsBelow.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (cfCountsBelow[mid].rating < rating) lo = mid + 1;
    else hi = mid;
  }
  const below = cfCountsBelow[lo]?.below ?? RANK_DISTRIBUTION_SOURCE.codeforcesPlayers;
  return 100 * (RANK_DISTRIBUTION_SOURCE.codeforcesPlayers - below) / RANK_DISTRIBUTION_SOURCE.codeforcesPlayers;
}

export function leagueRankAtPercentile(topPercent: number): string {
  return (LEAGUE_PERCENTILES.find(rank => topPercent <= rank.topPercent) ?? LEAGUE_PERCENTILES.at(-1)!).label;
}

export function formatTopPercent(topPercent: number): string {
  if (topPercent === 0) {
    return `<${(100 / RANK_DISTRIBUTION_SOURCE.codeforcesPlayers).toFixed(3)}%`;
  }
  const decimals = topPercent < 0.1 ? 3 : topPercent < 1 ? 2 : 1;
  return `${Number(topPercent.toFixed(decimals))}%`;
}

export function leagueEquivalent(elo: number) {
  const topPercent = codeforcesTopPercent(elo);
  return { label: leagueRankAtPercentile(topPercent), topPercent, topLabel: formatTopPercent(topPercent) };
}

/** A whole CF band can overlap several League divisions. Show that range
 * rather than assigning every rating in a broad tier a single equivalent. */
export function leagueEquivalentRange(min: number, max: number | null) {
  const start = leagueEquivalent(min);
  const end = leagueEquivalent(max ?? Number.MAX_SAFE_INTEGER);
  return start.label === end.label ? start.label : `${start.label} → ${end.label}`;
}
