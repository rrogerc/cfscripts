from urllib.parse import quote_plus

from .api import get_results, invalidate, CACHE_SHORT, CACHE_LONG

class RatingTracker:
    def __init__(self, handle):
        self.handle = handle
        rating_changes = get_rating_changes_for_user(self.handle)
        self.ratings = [
            (int(rt["ratingUpdateTimeSeconds"]), int(rt["newRating"]))
            for rt in rating_changes
        ]
        self.ratings.sort()

    def get_rating_at_time(self, sec):
        if len(self.ratings) == 0: return 1500
        if sec < self.ratings[0][0]: return 1500
        for i in range(len(self.ratings) - 1):
            if self.ratings[i][0] <= sec < self.ratings[i+1][0]:
                return self.ratings[i][1]
        return self.ratings[-1][1]

def get_rating_changes_for_contest(contest_id):
    url = "https://codeforces.com/api/contest.ratingChanges?contestId={}".format(
        quote_plus(str(contest_id))
    )
    result = get_results(url, CACHE_LONG)
    if not result:
        # The API transiently returns empty rating changes for some contests.
        # Never let an empty response sit in the long cache, or the contest
        # would permanently look unrated to every later call.
        invalidate(url, CACHE_LONG)
    return result

def get_rating_changes_for_user(handle):
    url = "https://codeforces.com/api/user.rating?handle={}".format(
        quote_plus(str(handle)),
    )
    return get_results(url, CACHE_SHORT)

def get_ratedlist():
    url = "https://codeforces.com/api/user.ratedList?activeOnly=true&includeRetired=false"
    return get_results(url, CACHE_SHORT)
