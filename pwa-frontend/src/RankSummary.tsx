import { Shield } from 'lucide-react';
import { ratingColorClass } from './colors';
import { rankedRank, RANK_TIERS, SUBDIVISIONS } from './ranks';
import { leagueEquivalent, leagueEquivalentRange, RANK_DISTRIBUTION_SOURCE } from './leagueRanks';

export function RankSummary({ elo, compact = false }: { elo: number; compact?: boolean }) {
  const rank = rankedRank(elo);
  const color = ratingColorClass(rank.rating);
  const league = leagueEquivalent(rank.rating);
  const nextText = rank.next
    ? `${rank.next.min - rank.rating} Elo to ${rank.next.label} · ${rank.next.min} Elo`
    : 'Highest subdivision reached';

  if (compact) {
    return (
      <div aria-label="Your ranked rank" className="space-y-1 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className={`flex items-center gap-1.5 min-w-0 font-semibold ${color}`}>
            <Shield aria-hidden="true" className="w-3.5 h-3.5 shrink-0" />
            <span>{rank.label}</span>
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400 tabular-nums shrink-0">
            {rank.rating} Elo
          </span>
        </div>
        <p aria-label="League of Legends equivalent" className="text-xs text-slate-500 dark:text-slate-400">
          League NA: ≈ {league.label} · CF top {league.topLabel}
        </p>
      </div>
    );
  }

  return (
    <section aria-label="Your ranked rank" className="space-y-3">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">
          Your rank
        </p>
        <h2 className={`flex items-center justify-center gap-2 text-2xl sm:text-3xl font-extrabold ${color}`}>
          <Shield aria-hidden="true" className="w-6 h-6 shrink-0" />
          <span>{rank.label}</span>
        </h2>
        <p className="mt-2 text-slate-900 dark:text-white">
          <span className="text-4xl font-extrabold tabular-nums">{rank.rating}</span>
          <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">Elo</span>
        </p>
      </div>

      <div aria-label="League of Legends equivalent" className="w-fit max-w-full mx-auto rounded-xl bg-slate-100 dark:bg-slate-900/50 px-4 py-2">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">≈ {league.label} in League</p>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">CF top {league.topLabel} · NA Solo/Duo</p>
      </div>

      <div className="max-w-sm mx-auto space-y-2">
        <div
          role="progressbar"
          aria-label="Progress through your rank tier"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(((rank.subdivision + rank.progress) / 4) * 100)}
          aria-valuetext={`${rank.label}. ${nextText}`}
          className={`grid grid-cols-4 gap-1.5 ${color}`}
        >
          {SUBDIVISIONS.map((division, i) => (
            <div key={division} aria-hidden="true">
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className="h-full rounded-full bg-current transition-[width] duration-300 motion-reduce:transition-none"
                  style={{ width: `${i < rank.subdivision ? 100 : i === rank.subdivision ? rank.progress * 100 : 0}%` }}
                />
              </div>
              <p className={`mt-1 text-xs ${i === rank.subdivision ? 'font-bold' : 'text-slate-500 dark:text-slate-400'}`}>
                {division}{i === rank.subdivision && <span className="sr-only"> · current</span>}
              </p>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">{rank.range} Elo in this subdivision</p>
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{nextText}</p>
      </div>

      <details className="text-left text-xs text-slate-500 dark:text-slate-400">
        <summary className="w-fit mx-auto cursor-pointer rounded px-2 py-1 hover:text-slate-800 dark:hover:text-slate-200 focus-visible:outline-2 focus-visible:outline-blue-500">
          Rank ladder
        </summary>
        <div className="mt-2 rounded-xl border border-slate-200 dark:border-slate-700 p-3 space-y-3">
          <p>
            Your ranked Elo determines your rank. We use{' '}
            <a href="https://codeforces.com/blog/entry/142495" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
              Codeforces titles
            </a>{' '}
            with four CF Picker subdivisions: IV → III → II → I, then the next tier.
            Each tier is split evenly. Legendary Grandmaster advances every 100 Elo, with I at 3300+.
          </p>
          <p>
            League equivalents match the percentile of the same rating among{' '}
            {RANK_DISTRIBUTION_SOURCE.codeforcesPlayers.toLocaleString('en-US')} active Codeforces users
            to North America Solo/Duo. These are approximate comparisons of relative standing.
            A tier can span several League divisions.
          </p>
          <p>
            Snapshot: <time dateTime={RANK_DISTRIBUTION_SOURCE.date}>{RANK_DISTRIBUTION_SOURCE.date}</time>
            {' · '}
            <a href={RANK_DISTRIBUTION_SOURCE.codeforcesUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">Codeforces data</a>
            {' · '}
            <a href={RANK_DISTRIBUTION_SOURCE.leagueUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">League data</a>
            <span className="block mt-1">Codeforces activity: a rated contest in the past month.</span>
          </p>
          <dl className="space-y-1">
            {RANK_TIERS.map((tier, i) => {
              const nextTier = RANK_TIERS[i + 1];
              const step = nextTier ? (nextTier.min - tier.min) / 4 : 100;
              const lower = i === 0 ? Number.MIN_SAFE_INTEGER : tier.min;
              return (
                <div key={tier.name} className={`rounded-lg px-2 py-2 ${i === rank.tierIndex ? 'bg-slate-100 dark:bg-slate-700/60' : ''}`}>
                  <dt className={`font-semibold ${ratingColorClass(tier.min)}`}>
                    {tier.name}{i === rank.tierIndex && <span className="sr-only"> · your current tier</span>}
                  </dt>
                  <dd>
                    <p className="mt-0.5 tabular-nums">
                      {i === 0 ? 'Below 1200' : nextTier ? `${tier.min}–${nextTier.min - 1}` : `${tier.min}+`} Elo
                    </p>
                    <p aria-label={`${tier.name} League equivalent`} className="mt-1 text-slate-700 dark:text-slate-200">
                      League ≈ {leagueEquivalentRange(lower, nextTier ? nextTier.min - 1 : null)}
                    </p>
                    <details className="mt-1.5">
                      <summary className="w-fit cursor-pointer rounded py-1 hover:text-slate-800 dark:hover:text-slate-200 focus-visible:outline-2 focus-visible:outline-blue-500">
                        IV–I subdivisions
                      </summary>
                      <ol aria-label={`${tier.name} subdivisions`} className="mt-1 space-y-1 border-l border-slate-300 dark:border-slate-600 pl-2">
                        {SUBDIVISIONS.map((division, d) => {
                          const min = tier.min + d * step;
                          const max = !nextTier && d === 3 ? null : min + step - 1;
                          const current = i === rank.tierIndex && d === rank.subdivision;
                          const range = i === 0 && d === 0 ? `Below ${min + step}` : max == null ? `${min}+` : `${min}–${max}`;
                          return (
                            <li key={division} aria-current={current ? 'step' : undefined} className={`rounded p-1.5 ${current ? 'bg-white dark:bg-slate-800' : ''}`}>
                              <p className="flex justify-between gap-2">
                                <span className={`font-semibold ${ratingColorClass(tier.min)}`}>{division}{current && ' · You'}</span>
                                <span className="tabular-nums">{range} Elo</span>
                              </p>
                              <p className="mt-0.5 text-slate-700 dark:text-slate-200">
                                League ≈ {leagueEquivalentRange(i === 0 && d === 0 ? lower : min, max)}
                              </p>
                            </li>
                          );
                        })}
                      </ol>
                    </details>
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      </details>
    </section>
  );
}
