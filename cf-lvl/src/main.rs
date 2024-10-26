use reqwest::blocking::Client;
use serde::Deserialize;
use std::error::Error;

#[derive(Deserialize, Debug)]
struct Problem {
    contestId: u32,
    index: String,
    rating: Option<u32>,
}

#[derive(Deserialize, Debug)]
struct Contest {
    id: u32,
    name: String,
    phase: String,
}

#[derive(Deserialize, Debug)]
struct Submission {
    problem: Problem,
    verdict: Option<String>,
}

#[derive(Deserialize, Debug)]
struct ApiResponse<T> {
    status: String,
    result: T,
}

fn main() -> Result<(), Box<dyn Error>> {
    let client = Client::new();

    // Fetch problem set
    let problems = fetch_problem_set(&client)?;
    println!("Problem Set: {:?}", problems[0]);

    // Fetch contest list
    let contests = fetch_contests(&client)?;
    println!("Contests: {:?}", contests[0]);

    // Fetch submissions for a given user
    let submissions = fetch_user_submissions(&client, "Exonerate")?;
    println!("Submissions: {:?}", submissions[0]);

    Ok(())
}

// Function to get the problem set
fn fetch_problem_set(client: &Client) -> Result<Vec<Problem>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/problemset.problems";
    let response: ApiResponse<serde_json::Value> = client.get(url).send()?.json()?;
    let problems: Vec<Problem> = serde_json::from_value(response.result["problems"].clone())?;
    Ok(problems)
}

// Function to get contest list
fn fetch_contests(client: &Client) -> Result<Vec<Contest>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/contest.list";
    let response: ApiResponse<Vec<Contest>> = client.get(url).send()?.json()?;
    Ok(response.result)
}

// Function to get submissions for a user
fn fetch_user_submissions(
    client: &Client,
    handle: &str,
) -> Result<Vec<Submission>, Box<dyn Error>> {
    let url = format!("https://codeforces.com/api/user.status?handle={}", handle);
    let response: ApiResponse<Vec<Submission>> = client.get(&url).send()?.json()?;
    Ok(response.result)
}
