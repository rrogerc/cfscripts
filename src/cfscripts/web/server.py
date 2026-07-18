from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from cfscripts.core.picker import get_problem_by_level
from cfscripts.core.scraper import get_problem_html
from cfscripts.lib.api import CACHE_NONE, ApiError
from cfscripts.lib.contests import get_participations
from cfscripts.lib.performance import UserPerformanceCalculator

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

@app.get("/api/participations")
def participations(handle: str):
    """List contests the user participated in (contestant/virtual/out-of-comp), newest first."""
    try:
        return {"participations": get_participations(handle)}
    except ApiError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/perf")
def perf(
    handle: str,
    contest_id: int,
    rating: Optional[int] = None,
    start_time: Optional[int] = None,
):
    """Rank/delta/performance for one contest.

    Optional `rating` overrides the user's rating at contest time — used by the
    client-side whatif simulation to chain contests with a simulated rating.
    Optional `start_time` (from /api/participations) picks the specific run
    when the user has several for one contest. Skips the ratedList fallback for
    just-ended contests (payload too large for serverless); those return
    delta/performance as "unknown".
    """
    try:
        calculator = UserPerformanceCalculator(handle)
        data = calculator.get_performance(
            contest_id,
            current_rating=rating,
            ratedlist_fallback=False,
            start_time=start_time,
        )
    except ApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (KeyError, TypeError, AssertionError):
        raise HTTPException(
            status_code=404,
            detail=f"No ranked result for {handle} in contest {contest_id}",
        )
    return data
