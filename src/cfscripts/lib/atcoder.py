import threading
import time
from urllib.parse import quote_plus

import requests
import requests_cache

from .api import ApiError, CACHE_LONG, CACHE_NONE, CACHE_SHORT, _long_session, _short_session

_THROTTLE_SECONDS = 1.0
_last_request_time = 0.0
_throttle_lock = threading.Lock()
_SUBMISSIONS_PAGE_LIMIT = 500

_HEADERS = {
    "User-Agent": "cfscripts/0.1 (competitive programming tools)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://kenkoooo.com/atcoder/",
}


def _throttled_get(url, cache_type=CACHE_NONE):
    """GET with 1-second throttle between uncached requests. Returns parsed JSON."""
    global _last_request_time
    try:
        if cache_type == CACHE_LONG:
            response = _long_session.get(url, headers=_HEADERS, timeout=(5, 15))
        elif cache_type == CACHE_SHORT:
            response = _short_session.get(url, headers=_HEADERS, timeout=(5, 15))
        else:
            with _throttle_lock:
                elapsed = time.time() - _last_request_time
                if elapsed < _THROTTLE_SECONDS:
                    time.sleep(_THROTTLE_SECONDS - elapsed)
                with requests_cache.disabled():
                    response = requests.get(url, headers=_HEADERS, timeout=(5, 15))
                _last_request_time = time.time()
        response.raise_for_status()
        if cache_type != CACHE_NONE and not getattr(response, "from_cache", False):
            with _throttle_lock:
                _last_request_time = time.time()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ApiError(f"AtCoder API request failed for {url}: {exc}") from exc


def get_abc_contest_ids(cache_type=CACHE_LONG):
    """Fetch all ABC contest IDs from kenkoooo contests.json."""
    url = "https://kenkoooo.com/atcoder/resources/contests.json"
    contests = _throttled_get(url, cache_type=cache_type)
    return {c["id"] for c in contests if c["id"].lower().startswith("abc")}


def get_problems(cache_type=CACHE_LONG):
    """Fetch all AtCoder problems from kenkoooo problems.json."""
    url = "https://kenkoooo.com/atcoder/resources/problems.json"
    return _throttled_get(url, cache_type=cache_type)


def get_user_accepted_problems(handle, cache_type=CACHE_SHORT):
    """Fetch all AC'd problem IDs via paginated submissions API."""
    from_second = 0
    accepted = set()
    handle_lower = quote_plus(str(handle).lower())
    while True:
        url = (
            "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"
            "?user={}&from_second={}".format(handle_lower, from_second)
        )
        submissions = _throttled_get(url, cache_type=cache_type)
        if not submissions:
            break
        max_epoch = from_second
        for sub in submissions:
            if sub.get("result") == "AC" and "problem_id" in sub:
                accepted.add(sub["problem_id"])
            if sub.get("epoch_second", 0) > max_epoch:
                max_epoch = sub["epoch_second"]
        if len(submissions) < _SUBMISSIONS_PAGE_LIMIT or max_epoch == from_second:
            break
        from_second = max_epoch + 1
    return accepted
