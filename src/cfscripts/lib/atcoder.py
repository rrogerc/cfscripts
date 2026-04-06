import time
import requests

_THROTTLE_SECONDS = 1.0
_last_request_time = 0.0

_HEADERS = {
    "User-Agent": "cfscripts/0.1 (competitive programming tools)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://kenkoooo.com/atcoder/",
}


def _throttled_get(url):
    """GET with 1-second throttle between requests. Returns parsed JSON."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _THROTTLE_SECONDS:
        time.sleep(_THROTTLE_SECONDS - elapsed)
    response = requests.get(url, headers=_HEADERS)
    response.raise_for_status()
    _last_request_time = time.time()
    return response.json()


def get_abc_contest_ids():
    """Fetch all ABC contest IDs from kenkoooo contests.json."""
    url = "https://kenkoooo.com/atcoder/resources/contests.json"
    contests = _throttled_get(url)
    return {c["id"] for c in contests if c["id"].lower().startswith("abc")}


def get_problems():
    """Fetch all AtCoder problems from kenkoooo problems.json."""
    url = "https://kenkoooo.com/atcoder/resources/problems.json"
    return _throttled_get(url)


def get_user_accepted_problems(handle):
    """Fetch all AC'd problem IDs via paginated submissions API."""
    from_second = 0
    accepted = set()
    handle_lower = handle.lower()
    while True:
        url = (
            "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"
            "?user={}&from_second={}".format(handle_lower, from_second)
        )
        submissions = _throttled_get(url)
        if not submissions:
            break
        max_epoch = from_second
        for sub in submissions:
            if sub["result"] == "AC":
                accepted.add(sub["problem_id"])
            if sub["epoch_second"] > max_epoch:
                max_epoch = sub["epoch_second"]
        if max_epoch == from_second:
            break
        from_second = max_epoch + 1
    return accepted
