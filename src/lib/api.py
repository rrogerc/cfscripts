from time import sleep
import json
from requests_cache.session import CachedSession
import requests_cache
import requests as req

from . import printer

_long_session = CachedSession(
    'cf-cache-long',
    backend='filesystem',
    use_cache_dir=True,                # Save files in the default user cache dir
    # cache_control=True,                # Use Cache-Control headers for expiration, if available
    # ignored_parameters=['api_key'],  # TODO: use this if api is used I think
    match_headers=True,                # Match all request headers
)

_short_session = CachedSession(
    'cf-cache-short',
    backend='filesystem',
    use_cache_dir=True,                # Save files in the default user cache dir
    # cache_control=True,                # Use Cache-Control headers for expiration, if available
    # ignored_parameters=['api_key'],  # TODO: use this if api is used I think
    match_headers=True,                # Match all request headers
    expire_after=120 # 2 minutes
)

class NoRatingChangesError(Exception):
    pass

def get_results(url, cache_type=0):
    while True:
        try:
            res = None
            if cache_type == 0:
                with requests_cache.disabled():
                    res = req.get(url)
            elif cache_type == 1:
                res = _short_session.get(url)
            else:
                res = _long_session.get(url)
        except (req.exceptions.ConnectionError, req.exceptions.ChunkedEncodingError, req.exceptions.Timeout):
            sleep(0.5)
            printer.PRINT("retrying")
            sleep(0.5)
            continue

        from_cache = getattr(res, 'from_cache', False)

        try:
            content = json.loads(res.content)
        except json.decoder.JSONDecodeError:
            sleep(0.5)
            printer.PRINT("retrying")
            sleep(0.5)
            continue

        if not from_cache:
            printer.PRINT("fetching {} {}".format(content["status"], url))
            sleep(0.2)

        if content["status"] == "OK":
            return content["result"]

        # Non-OK response served from cache is likely stale — delete and retry fresh
        if from_cache:
            try:
                if cache_type == 1:
                    _short_session.cache.delete(urls=[url])
                else:
                    _long_session.cache.delete(urls=[url])
            except Exception:
                pass
            continue

        if content.get("comment") == "contestId: Rating changes are unavailable for this contest":
            raise NoRatingChangesError(url)
        else:
            sleep(0.5)
            printer.PRINT("retrying")
            sleep(0.5)
