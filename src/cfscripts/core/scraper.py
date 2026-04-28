import cloudscraper
from bs4 import BeautifulSoup

from cfscripts.lib.api import get_results, CACHE_LONG

# Reused across requests so the Cloudflare clearance cookie is cached.
# On Vercel Fluid Compute, instances persist across invocations, so the
# JS challenge is solved once per warm instance instead of per request.
_scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)


def get_problem_html(contest_id, index):
    """Fetch and extract the problem statement HTML from Codeforces."""
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
    response = _scraper.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    problem_statement = soup.find('div', class_='problem-statement')

    if not problem_statement:
        return "<p>Error: Could not extract problem statement from Codeforces.</p>"

    return str(problem_statement)


def find_ac_cpp_submission(contest_id, index):
    """Return metadata for an accepted C++ submission for the given problem, or None."""
    url = f"https://codeforces.com/api/contest.status?contestId={contest_id}&from=1&count=1000"
    submissions = get_results(url, CACHE_LONG)

    for sub in submissions:
        if sub.get('verdict') != 'OK':
            continue
        if sub.get('problem', {}).get('index') != index:
            continue
        lang = sub.get('programmingLanguage', '')
        if 'C++' not in lang:
            continue
        members = sub.get('author', {}).get('members', [])
        handle = members[0].get('handle', 'unknown') if members else 'unknown'
        return {
            'submissionId': sub['id'],
            'authorHandle': handle,
            'language': lang,
        }
    return None


def get_submission_source(contest_id, submission_id):
    """Scrape the source code of a submission from Codeforces."""
    url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
    response = _scraper.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    pre = soup.find('pre', id='program-source-text')
    if not pre:
        return None
    return pre.get_text()
