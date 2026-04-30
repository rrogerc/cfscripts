import cloudscraper
from bs4 import BeautifulSoup

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
