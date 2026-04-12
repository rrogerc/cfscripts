import requests
from bs4 import BeautifulSoup

def get_problem_html(contest_id, index):
    """Fetch and extract the problem statement HTML from Codeforces."""
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    problem_statement = soup.find('div', class_='problem-statement')
    
    if not problem_statement:
        return "<p>Error: Could not extract problem statement from Codeforces.</p>"
        
    return str(problem_statement)
