from .api import get_results, CACHE_LONG

def get_problems():
    url="https://codeforces.com/api/problemset.problems"
    result = get_results(url, CACHE_LONG)
    return result["problems"]
