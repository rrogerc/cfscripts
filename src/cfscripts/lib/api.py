from time import sleep
import json
from requests_cache.session import CachedSession
import requests_cache
import requests as req

from . import printer

_long_session = CachedSession(
    'cf-cache-long',
    backend='filesystem',
    use_temp=True,
    match_headers=True,
)

_short_session = CachedSession(
    'cf-cache-short',
    backend='filesystem',
    use_temp=True,
    match_headers=True,
    expire_after=120,
)

CACHE_NONE = 0
CACHE_SHORT = 1
CACHE_LONG = 2

MAX_RETRIES = 10

class NoRatingChangesError(Exception):
    pass

class ApiError(Exception):
    pass

def get_results(url, cache_type=CACHE_NONE):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            res = None
            if cache_type == CACHE_NONE:
                with requests_cache.disabled():
                    res = req.get(url)
            elif cache_type == CACHE_SHORT:
                res = _short_session.get(url)
            else:
                res = _long_session.get(url)
        except (req.exceptions.ConnectionError, req.exceptions.ChunkedEncodingError, req.exceptions.Timeout) as e:
            last_error = e
            delay = min(0.5 * 2 ** attempt, 30)
            printer.log("connection error, retrying in {:.1f}s...".format(delay))
            sleep(delay)
            continue

        from_cache = getattr(res, 'from_cache', False)

        try:
            content = json.loads(res.content)
        except json.decoder.JSONDecodeError:
            last_error = "malformed JSON response"
            delay = min(0.5 * 2 ** attempt, 30)
            printer.log("bad response, retrying in {:.1f}s...".format(delay))
            sleep(delay)
            continue

        if not from_cache:
            printer.log("fetching {} {}".format(content["status"], url))
            sleep(0.2)

        if content["status"] == "OK":
            return content["result"]

        # Non-OK response served from cache is likely stale — delete and retry fresh
        if from_cache:
            try:
                if cache_type == CACHE_SHORT:
                    _short_session.cache.delete(urls=[url])
                else:
                    _long_session.cache.delete(urls=[url])
            except Exception:
                pass
            continue

        if content.get("comment") == "contestId: Rating changes are unavailable for this contest":
            raise NoRatingChangesError(url)

        last_error = content.get("comment", "unknown API error")
        delay = min(0.5 * 2 ** attempt, 30)
        printer.log("API error: {}, retrying in {:.1f}s...".format(last_error, delay))
        sleep(delay)

    raise ApiError("Failed after {} retries for {}: {}".format(MAX_RETRIES, url, last_error))
