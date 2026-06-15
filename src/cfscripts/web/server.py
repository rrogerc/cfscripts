from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from cfscripts.core.picker import get_problem_by_level
from cfscripts.core.scraper import get_problem_html
from cfscripts.lib.api import CACHE_NONE

app = FastAPI()

# Allow CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/pick")
def pick_problem(handle: str, level: int):
    try:
        # Filter out problems the user has already solved. Fetch submissions
        # fresh (CACHE_NONE) so a problem just AC'd is excluded on the next pick
        # instead of lingering until the short cache expires.
        best = get_problem_by_level(handle, level, use_solved=True, solved_cache=CACHE_NONE)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if best is None:
        raise HTTPException(status_code=404, detail=f"No problem found for level {level}")

    html_content = get_problem_html(best["contestId"], best["index"])

    return {
        "problem": best,
        "html": html_content
    }
