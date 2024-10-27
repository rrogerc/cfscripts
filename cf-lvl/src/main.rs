use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::HashSet;
use std::error::Error;

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Problem {
    contestId: u32,
    index: String,
    rating: u32,
}

fn main() -> Result<(), Box<dyn Error>> {
    let client = Client::new();

    // Fetch data
    let rated_problems = fetch_problem_set(&client)?;
    let div2_contests = fetch_contests(&client)?;
    let passed_problems = fetch_user_submissions(&client, "Exonerate")?;

    let passed_problems_set: HashSet<(u32, String)> = passed_problems
        .into_iter()
        .map(|problem| (problem.contestId, problem.index.clone()))
        .collect();

    // Filter rated_problems to include only those in div2_contests and not in passed_problems
    let mut filtered_problems: Vec<Problem> = rated_problems
        .into_iter()
        .filter(|problem| {
            div2_contests.contains(&problem.contestId) // Ensure it's in a Div. 2 contest
                && !passed_problems_set.contains(&(problem.contestId, problem.index.clone()))
            // Exclude if already passed
        })
        .collect();

    filtered_problems.sort_by(|a, b| b.contestId.cmp(&a.contestId));

    // Find and display the first problem with a rating of 800
    if let Some(problem) = filtered_problems.iter().find(|p| p.rating == 800) {
        println!("First problem with rating 800: {:?}", problem);
    } else {
        println!("No problem with rating 800 found.");
    }
    Ok(())
}

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Contest {
    id: u32,
    name: String,
}

#[derive(Deserialize, Debug)]
struct ApiResponse<T> {
    //status: String,
    result: T,
}

#[derive(Deserialize, Debug)]
struct UnratedProblem {
    contestId: u32,
    index: String,
    rating: Option<u32>,
}

#[derive(Deserialize, Debug)]
struct Submission {
    problem: UnratedProblem,
    verdict: Option<String>,
}

// Function to get the problem set
fn fetch_problem_set(client: &Client) -> Result<Vec<Problem>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/problemset.problems";
    let response: ApiResponse<serde_json::Value> = client.get(url).send()?.json()?;
    let problems: Vec<UnratedProblem> =
        serde_json::from_value(response.result["problems"].clone())?;

    let rated_problems: Vec<Problem> = problems
        .into_iter()
        .filter_map(|unrated_problem| {
            unrated_problem.rating.map(|rating| Problem {
                contestId: unrated_problem.contestId,
                index: unrated_problem.index,
                rating,
            })
        })
        .collect();

    Ok(rated_problems)
}

// Function to get contest list
fn fetch_contests(client: &Client) -> Result<HashSet<u32>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/contest.list";
    let response: ApiResponse<Vec<Contest>> = client.get(url).send()?.json()?;

    let contest_ids: HashSet<u32> = response
        .result
        .into_iter()
        .filter(|contest| contest.name.contains("Div. 2") && !contest.name.contains("Div. 1"))
        .map(|contest| contest.id)
        .collect();

    Ok(contest_ids)
}

// Function to get submissions for a user
fn fetch_user_submissions(
    client: &Client,
    handle: &str,
) -> Result<HashSet<Problem>, Box<dyn Error>> {
    let url = format!("https://codeforces.com/api/user.status?handle={}", handle);
    let response: ApiResponse<Vec<Submission>> = client.get(&url).send()?.json()?;

    let ok_rated_problems: HashSet<Problem> = response
        .result // Access the vector of `Submission`s from the `ApiResponse`
        .into_iter()
        .filter_map(|submission| {
            // Check if the verdict is `Some("OK")` and the rating is `Some`
            if submission.verdict.as_deref() == Some("OK") {
                submission.problem.rating.map(|rating| Problem {
                    contestId: submission.problem.contestId,
                    index: submission.problem.index.clone(),
                    rating,
                })
            } else {
                None // Exclude non-OK or unrated problems
            }
        })
        .collect();

    Ok(ok_rated_problems)
}
