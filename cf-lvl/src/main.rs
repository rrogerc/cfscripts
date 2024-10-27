use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::HashSet;
use std::env;
use std::error::Error;
use std::process;

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Problem {
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: u32,
}

fn main() -> Result<(), Box<dyn Error>> {
    let input = env::args().nth(1).unwrap_or_else(|| {
        println!(
            "Codeforces Level\n\
            Usage: cf-lvl [level]\n\
            Where [level] is an integer between 8 and 32 inclusive \
            corresponding to a problem rating of [level] * 100.\n\
            Only problems from Div. 2 are selected."
        );
        process::exit(1);
    });

    let level: u32 = input.parse().unwrap_or_else(|_| {
        println!("Error: Could not parse the provided level. Please provide a valid integer.");
        process::exit(1);
    });

    if level < 8 || level > 32 {
        println!("Error: Level must be an integer between 8 and 32 inclusive.");
        return Ok(());
    }

    let client = Client::new();

    // Fetch data
    let rated_problems = fetch_problem_set(&client)?;
    let div2_contests = fetch_contests(&client)?;
    let passed_problems = fetch_user_submissions(&client, "Exonerate")?;

    let passed_problems_set: HashSet<(u32, String)> = passed_problems
        .into_iter()
        .map(|problem| (problem.contest_id, problem.index.clone()))
        .collect();

    // Filter rated_problems to include only those in div2_contests and not in passed_problems
    let mut filtered_problems: Vec<Problem> = rated_problems
        .into_iter()
        .filter(|problem| {
            div2_contests.contains(&problem.contest_id) // Ensure it's in a Div. 2 contest
                && !passed_problems_set.contains(&(problem.contest_id, problem.index.clone()))
        })
        .collect();

    filtered_problems.sort_by(|a, b| b.contest_id.cmp(&a.contest_id));

    if let Some(problem) = filtered_problems.iter().find(|p| p.rating == level * 100) {
        let url = format!(
            "https://codeforces.com/contest/{}/problem/{}",
            problem.contest_id, problem.index
        );

        if webbrowser::open_browser(webbrowser::Browser::Chrome, &url).is_ok() {
            println!("Opening problem");
        } else {
            println!("Failed to open problem");
        }
    } else {
        println!(
            "No problem with rating {} found(Level {}).",
            level * 100,
            level
        );
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
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: Option<u32>,
}

#[derive(Deserialize, Debug)]
struct Submission {
    problem: UnratedProblem,
    verdict: Option<String>,
}

fn fetch_problem_set(client: &Client) -> Result<Vec<Problem>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/problemset.problems";
    let response: ApiResponse<serde_json::Value> = client.get(url).send()?.json()?;
    let problems: Vec<UnratedProblem> =
        serde_json::from_value(response.result["problems"].clone())?;

    let rated_problems: Vec<Problem> = problems
        .into_iter()
        .filter_map(|unrated_problem| {
            unrated_problem.rating.map(|rating| Problem {
                contest_id: unrated_problem.contest_id,
                index: unrated_problem.index,
                rating,
            })
        })
        .collect();

    Ok(rated_problems)
}

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

fn fetch_user_submissions(
    client: &Client,
    handle: &str,
) -> Result<HashSet<Problem>, Box<dyn Error>> {
    let url = format!("https://codeforces.com/api/user.status?handle={}", handle);
    let response: ApiResponse<Vec<Submission>> = client.get(&url).send()?.json()?;

    let ok_rated_problems: HashSet<Problem> = response
        .result
        .into_iter()
        .filter_map(|submission| {
            // Check if the verdict is `Some("OK")` and the rating is `Some`
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
        .collect();

    Ok(ok_rated_problems)
}
