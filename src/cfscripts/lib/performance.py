from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

from .rating import RatingTracker, get_rating_changes_for_contest, get_ratedlist
from .api import NoRatingChangesError, ApiError
from .contests import get_contest_and_standings
from .rating_calculator import CodeforcesRatingCalculator

ContestantEntry = namedtuple("ContestantEntry", ["handle", "points", "penalty", "rating"])
_UNSET = float("inf")

class UserPerformanceCalculator:

    def __init__(self, handle):
        self.handle = handle
        self.rating_tracker = RatingTracker(self.handle)

    def prefetch(self, contest_ids, max_workers=3):
        """Pre-fetch standings and rating changes for all contests in parallel to populate cache."""
        def fetch_one(contest_id):
            try:
                get_contest_and_standings(contest_id)
            except Exception:
                pass
            try:
                get_rating_changes_for_contest(contest_id)
            except NoRatingChangesError:
                pass
            except Exception:
                pass
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(fetch_one, contest_ids))

    def get_performance(self, contest_id, current_rating=None):
        try:
            contest, standings = get_contest_and_standings(contest_id)
        except ApiError:
            return {
                "contest_id" : contest_id,
                "contest_name" : "contest {}".format(contest_id),
                "handle" : self.handle,
                "points" : 0,
                "penalty" : 0,
                "rating" : 0,
                "rank" : 0,
                "delta" : "unknown",
                "performance" : "unknown",
                "participation_type" : "unknown",
                "result_status" : "api_error",
                "user_was_rated" : False,
            }
        contestants = {}
        participation_type = None
        rank = None
        for stand in standings:
            part_type = stand["party"]["participantType"]
            if part_type == "PRACTICE": continue
            members = stand["party"]["members"]
            if len(members) == 1:
                handle = members[0]["handle"]
                points = stand["points"]
                penalty = stand["penalty"]
                if part_type == "CONTESTANT":
                    if handle not in contestants:
                        contestants[handle] = ContestantEntry(handle, _UNSET, _UNSET, _UNSET)
                    contestants[handle] = contestants[handle]._replace(points=points, penalty=penalty)
                if handle == self.handle:
                    start_time = int(stand["party"]["startTimeSeconds"])
                    rating = self.rating_tracker.get_rating_at_time(start_time)
                    contestants[handle] = ContestantEntry(handle, points, penalty, rating)
                    participation_type = part_type
                    rank = stand["rank"]

        if current_rating is not None:
            contestants[self.handle] = contestants[self.handle]._replace(rating=current_rating)

        rating_changes = None
        try:
            rating_changes = get_rating_changes_for_contest(contest_id)
        except NoRatingChangesError:
            me = contestants[self.handle]
            return {
                "contest_id" : contest_id,
                "contest_name" : contest["name"],
                "handle" : self.handle,
                "points" : int(me.points),
                "penalty" : int(me.penalty),
                "rating" : int(me.rating),
                "rank" : int(rank),
                "delta" : "unknown",
                "performance" : "unknown",
                "participation_type" : participation_type.lower(),
                "result_status" : "unrated/old/unusual",
                "user_was_rated" : False,
            }

        result_status = None
        user_was_rated = False
        if len(rating_changes) == 0:
            result_status = "just_ended"
            ratings = get_ratedlist()
            for user in ratings:
                handle = user["handle"]
                if handle in contestants:
                    contestants[handle] = contestants[handle]._replace(rating=user["rating"])
            contestants = {h: c for h, c in contestants.items()
                          if h == self.handle or c.rating != _UNSET}
        else:
            result_status = "normal"
            user_was_rated = any(rt["handle"] == self.handle for rt in rating_changes)
            rated_handles = {self.handle}
            for rt in rating_changes:
                handle = rt["handle"]
                if handle not in contestants: continue
                rated_handles.add(handle)
                rating = rt["oldRating"]
                if rating == 0 and contest_id >= 1360:
                    rating = 1400
                contestants[handle] = contestants[handle]._replace(rating=rating)
            contestants = {h: c for h, c in contestants.items() if h in rated_handles}

        if current_rating is not None:
            contestants[self.handle] = contestants[self.handle]._replace(rating=current_rating)

        assert self.handle in contestants
        for handle, entry in contestants.items():
            assert entry.handle == handle
            assert entry.points != _UNSET
            assert entry.penalty != _UNSET
            assert entry.rating != _UNSET

        calculator = CodeforcesRatingCalculator(contestants.values())
        rated_contestants = calculator.contestants
        rated_contestants.sort(key=lambda con: con.rank)
        for con in rated_contestants:
            if con.party == self.handle:
                return {
                    "contest_id" : contest_id,
                    "contest_name" : contest["name"],
                    "handle" : self.handle,
                    "points" : con.points,
                    "penalty" : con.penalty,
                    "rating" : con.rating,
                    "rank" : int(rank),
                    "delta" : con.delta,
                    "performance" : con.rating + con.delta * 4,
                    "participation_type" : participation_type.lower(),
                    "result_status" : result_status,
                    "user_was_rated" : user_was_rated,
                }
        raise AssertionError("handle not found in rated contestants")
