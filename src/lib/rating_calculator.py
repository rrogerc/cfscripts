# from: https://github.com/cheran-senthil/TLE/blob/master/tle/util/ranklist/rating_calculator.py

"""
Adapted from Codeforces code to recalculate ratings
by Mike Mirzayanov (mirzayanovmr@gmail.com) at https://codeforces.com/contest/1/submission/13861109
Updated to use the current rating formula.
"""

from dataclasses import dataclass

import numpy as np
from numpy.fft import fft, ifft

def intdiv(x, y):
    return -(-x // y) if x < 0 else x // y

@dataclass
class Contestant:
    party: str
    points: float
    penalty: int
    rating: int
    need_rating: int = 0
    delta: int = 0
    rank: float = 0.0
    seed: float = 0.0

class CodeforcesRatingCalculator:
    def __init__(self, standings):
        """Calculate Codeforces rating changes and seeds given contest and user information."""
        self.contestants = [Contestant(handle, points, penalty, rating)
                            for handle, points, penalty, rating in standings]
        self._precalc_seed()
        self._reassign_ranks()
        self._process()
        self._update_delta()

    def calculate_rating_changes(self):
        """Return a mapping between contestants and their corresponding delta."""
        return {contestant.party: contestant.delta for contestant in self.contestants}

    def get_seed(self, rating, me=None):
        """Get seed given a rating and user."""
        seed = self.seed[rating]
        if me:
            seed -= self.elo_win_prob[rating - me.rating]
        return seed

    def _precalc_seed(self):
        MAX = 6144

        # Precompute the ELO win probability for all possible rating differences.
        self.elo_win_prob = np.roll(1 / (1 + pow(10, np.arange(-MAX, MAX) / 400)), -MAX)

        # Compute the rating histogram.
        count = np.zeros(2 * MAX)
        for a in self.contestants:
            count[a.rating] += 1

        # Precompute the seed for all possible ratings using FFT.
        self.seed = 1 + ifft(fft(count) * fft(self.elo_win_prob)).real

    def _reassign_ranks(self):
        """Find the rank of each contestant."""
        contestants = self.contestants
        contestants.sort(key=lambda o: (-o.points, o.penalty))
        points = penalty = rank = None
        for i in reversed(range(len(contestants))):
            if contestants[i].points != points or contestants[i].penalty != penalty:
                rank = i + 1
                points = contestants[i].points
                penalty = contestants[i].penalty
            contestants[i].rank = rank

    def _process(self):
        """Process and assign approximate delta for each contestant."""
        n = len(self.contestants)
        if n == 0:
            return
        ratings = np.array([a.rating for a in self.contestants], dtype=np.int64)
        ranks = np.array([a.rank for a in self.contestants], dtype=np.float64)

        # Seed at own rating minus self-contribution: elo_win_prob[rating - rating] = elo_win_prob[0]
        seeds = self.seed[ratings] - self.elo_win_prob[0]

        mid_ranks = np.sqrt(ranks * seeds)

        # Vectorized binary search across all contestants simultaneously
        left = np.ones(n, dtype=np.int64)
        right = np.full(n, 8000, dtype=np.int64)
        for _ in range(13):  # ceil(log2(7999)) = 13 iterations
            mid = (left + right) // 2
            seed_at_mid = self.seed[mid] - self.elo_win_prob[mid - ratings]
            go_right = seed_at_mid < mid_ranks
            left = np.where(go_right, left, mid)
            right = np.where(go_right, mid, right)

        need_ratings = left

        # intdiv toward zero: -(-x // y) if x < 0 else x // y
        diff = need_ratings - ratings
        deltas = np.where(diff < 0, -(-diff // 2), diff // 2)

        # Write back to contestant objects
        for i, a in enumerate(self.contestants):
            a.seed = float(seeds[i])
            a.need_rating = int(need_ratings[i])
            a.delta = int(deltas[i])

    def _rank_to_rating(self, rank, me):
        """Binary Search to find the performance rating for a given rank."""
        left, right = 1, 8000
        while right - left > 1:
            mid = (left + right) // 2
            if self.get_seed(mid, me) < rank:
                right = mid
            else:
                left = mid
        return left

    def _update_delta(self):
        """Update the delta of each contestant."""
        contestants = self.contestants
        n = len(contestants)

        contestants.sort(key=lambda o: -o.rating)
        correction = intdiv(-sum(c.delta for c in contestants), n) - 1
        for contestant in contestants:
            contestant.delta += correction

        zero_sum_count = min(int(4 * n ** 0.5 + 0.5), n)  # Java Math.round semantics
        delta_sum = -sum(contestants[i].delta for i in range(zero_sum_count))
        correction = min(0, max(-10, intdiv(delta_sum, zero_sum_count)))
        for contestant in contestants:
            contestant.delta += correction
