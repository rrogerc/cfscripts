from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from cfscripts.core.picker import get_problem_by_level
from cfscripts.core.scraper import get_problem_html, find_ac_cpp_submission, get_submission_source

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
        best = get_problem_by_level(handle, level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if best is None:
        raise HTTPException(status_code=404, detail=f"No problem found for level {level}")

    html_content = get_problem_html(best["contestId"], best["index"])

    return {
        "problem": best,
        "html": html_content
    }


@app.get("/api/solution")
def get_solution(contestId: int, index: str):
    sub_meta = find_ac_cpp_submission(contestId, index)
    if sub_meta is None:
        raise HTTPException(status_code=404, detail="No accepted C++ solution found")

    source = get_submission_source(contestId, sub_meta['submissionId'])
    if source is None:
        raise HTTPException(status_code=502, detail="Failed to scrape submission source")

    return {
        "source": source,
        "language": sub_meta['language'],
        "submissionId": sub_meta['submissionId'],
        "authorHandle": sub_meta['authorHandle'],
    }
