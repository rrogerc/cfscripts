use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::HashSet;
use std::error::Error;

const CUTOFF_TS: u64 = 1672531200; // 2023-01-01 00:00:00 UTC
const CODEFORCES_HANDLE: &str = "Exonerate";

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Problem {
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: u32,
}

#[derive(Debug, Deserialize)]
struct Contest {
    id: u32,
    name: String,
    #[serde(rename = "startTimeSeconds")]
    start_time_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
struct ApiResponse<T> {
    result: T,
}

#[derive(Debug, Deserialize)]
struct Submission {
    problem: UnratedProblem,
    verdict: Option<String>,
}

#[derive(Debug, Deserialize)]
struct UnratedProblem {
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: Option<u32>,
}

pub fn run(client: &Client, level: u32) -> Result<(), Box<dyn Error>> {
    if level < 8 || level > 32 {
        println!("Error: Level must be an integer between 8 and 32 inclusive.");
        return Ok(());
    }

    let rated_problems = fetch_problem_set(client)?;
    let div2_contests = fetch_contests(client)?;
    let passed_problems = fetch_user_submissions(client)?;

    let solved: HashSet<(u32, String)> = passed_problems
        .into_iter()
        .map(|problem| (problem.contest_id, problem.index.clone()))
        .collect();

    let mut filtered: Vec<Problem> = rated_problems
        .into_iter()
        .filter(|problem| {
            div2_contests.contains(&problem.contest_id)
                && !solved.contains(&(problem.contest_id, problem.index.clone()))
        })
        .collect();

    filtered.sort_by(|a, b| b.contest_id.cmp(&a.contest_id));

    if let Some(problem) = filtered.iter().find(|p| p.rating == level * 100) {
        let url = format!(
            "https://codeforces.com/contest/{}/problem/{}",
            problem.contest_id, problem.index
        );

        if webbrowser::open(&url).is_ok() {
            println!("Opening problem");
        } else {
            println!("Failed to open problem");
        }
    } else {
        println!(
            "No problem with rating {} found (Level {}).",
            level * 100,
            level
        );
    }

    Ok(())
}

fn fetch_problem_set(client: &Client) -> Result<Vec<Problem>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/problemset.problems";
    let response: ApiResponse<serde_json::Value> = client.get(url).send()?.json()?;
    let problems: Vec<UnratedProblem> =
        serde_json::from_value(response.result["problems"].clone())?;

    Ok(problems
        .into_iter()
        .filter_map(|problem| {
            problem.rating.map(|rating| Problem {
                contest_id: problem.contest_id,
                index: problem.index,
                rating,
            })
        })
        .collect())
}

fn fetch_contests(client: &Client) -> Result<HashSet<u32>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/contest.list";
    let response: ApiResponse<Vec<Contest>> = client.get(url).send()?.json()?;

    Ok(response
        .result
        .into_iter()
        .filter(|contest| {
            contest.name.contains("Div. 2")
                && !contest.name.contains("Div. 1")
                && contest
                    .start_time_seconds
                    .map(|ts| ts < CUTOFF_TS)
                    .unwrap_or(false)
        })
        .map(|contest| contest.id)
        .collect())
}

fn fetch_user_submissions(client: &Client) -> Result<HashSet<Problem>, Box<dyn Error>> {
    let url = format!(
        "https://codeforces.com/api/user.status?handle={}",
        CODEFORCES_HANDLE
    );
    let response: ApiResponse<Vec<Submission>> = client.get(&url).send()?.json()?;

    Ok(response
        .result
        .into_iter()
        .filter_map(|submission| {
            if submission.verdict.as_deref() == Some("OK") {
                submission.problem.rating.map(|rating| Problem {
                    contest_id: submission.problem.contest_id,
                    index: submission.problem.index.clone(),
                    rating,
                })
            } else {
                None
            }
        })
        .collect())
}
