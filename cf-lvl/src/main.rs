use reqwest::blocking::Client;
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, ACCEPT_LANGUAGE, REFERER, USER_AGENT};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::collections::HashSet;
use std::env;
use std::error::Error;
use std::process;
use std::thread;
use std::time::Duration;

const CUTOFF_TS: u64 = 1672531200; // 2023-01-01 00:00:00 UTC
const CODEFORCES_HANDLE: &str = "Exonerate";
const ATCODER_HANDLE: &str = "Exonerate";
const ATCODER_SLEEP_BETWEEN_CALLS: Duration = Duration::from_secs(1);

#[derive(Debug, Clone, Copy)]
enum Platform {
    Codeforces,
    AtCoder,
}

impl Platform {
    fn from_str(value: &str) -> Result<Self, String> {
        let normalized = value.to_lowercase();
        match normalized.as_str() {
            "cf" | "codeforces" => Ok(Platform::Codeforces),
            "ac" | "atcoder" => Ok(Platform::AtCoder),
            _ => Err(format!(
                "Unrecognized platform '{}'. Use 'codeforces' or 'atcoder'.",
                value
            )),
        }
    }
}

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Problem {
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: u32,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().skip(1).collect();

    if args.is_empty() {
        print_usage();
        process::exit(1);
    }

    let (platform, level_arg) = if args.len() == 1 {
        (Platform::Codeforces, &args[0])
    } else {
        let platform = Platform::from_str(&args[0]).unwrap_or_else(|err| {
            println!("{}", err);
            process::exit(1);
        });
        (platform, &args[1])
    };

    let mut headers = HeaderMap::new();
    headers.insert(
        USER_AGENT,
        HeaderValue::from_static(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 cf-lvl/0.2",
        ),
    );
    headers.insert(
        ACCEPT,
        HeaderValue::from_static("application/json, text/plain, */*"),
    );
    headers.insert(ACCEPT_LANGUAGE, HeaderValue::from_static("en-US,en;q=0.9"));
    headers.insert(
        REFERER,
        HeaderValue::from_static("https://kenkoooo.com/atcoder/"),
    );

    let client = Client::builder().default_headers(headers).build()?;

    match platform {
        Platform::Codeforces => {
            let level: u32 = level_arg.parse().unwrap_or_else(|_| {
                println!(
                    "Error: Could not parse the provided level. Please provide a valid integer."
                );
                process::exit(1);
            });
            run_codeforces(&client, level)
        }
        Platform::AtCoder => run_atcoder(&client, level_arg),
    }
}

fn print_usage() {
    println!(
        "Problem Picker\n\
        Usage:\n\
          cf-lvl [level]               # Codeforces (default)\n\
          cf-lvl atcoder [index]       # AtCoder ABC\n\
        Levels map to problem ratings (level * 100) on Codeforces.\n\
        For AtCoder, provide the task letter (a, b, c, ...)."
    );
}

fn run_codeforces(client: &Client, level: u32) -> Result<(), Box<dyn Error>> {
    if level < 8 || level > 32 {
        println!("Error: Level must be an integer between 8 and 32 inclusive.");
        return Ok(());
    }

    // Fetch data
    let rated_problems = fetch_problem_set(client)?;
    let div2_contests = fetch_contests(client, CUTOFF_TS)?;
    let passed_problems = fetch_user_submissions(client, CODEFORCES_HANDLE)?;

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

fn run_atcoder(client: &Client, index_input: &str) -> Result<(), Box<dyn Error>> {
    let normalized_index = index_input.trim().to_ascii_lowercase();

    if normalized_index.is_empty() {
        println!("Error: Provide a problem index such as 'a', 'b', or 'c'.");
        return Ok(());
    }

    if normalized_index.len() != 1 || !normalized_index.chars().all(|c| c.is_ascii_alphabetic()) {
        println!("Error: Problem index must be a single letter (e.g., a, b, c).");
        return Ok(());
    }

    let abc_contests = fetch_atcoder_abc_contests(client, CUTOFF_TS)?;
    let problems = fetch_atcoder_problems(client)?;
    let solved = fetch_atcoder_user_submissions(client, ATCODER_HANDLE)?;

    let mut candidates: Vec<AtcoderProblem> = problems
        .into_iter()
        .filter(|problem| {
            abc_contests.contains(&problem.contest_id)
                && problem_index(&problem.id)
                    .map(|idx| idx == normalized_index)
                    .unwrap_or(false)
        })
        .collect();

    candidates.sort_by(|a, b| {
        contest_number(&b.contest_id)
            .cmp(&contest_number(&a.contest_id))
            .then_with(|| a.id.cmp(&b.id))
    });

    let problem = candidates
        .into_iter()
        .find(|problem| !solved.contains(&problem.id));

    if let Some(problem) = problem {
        let url = format!(
            "https://atcoder.jp/contests/{}/tasks/{}",
            problem.contest_id, problem.id
        );

        if webbrowser::open(&url).is_ok() {
            println!("Opening problem");
        } else {
            println!("Failed to open problem");
        }
    } else {
        println!(
            "No unsolved AtCoder ABC '{}' problem found before 2023.",
            normalized_index.to_ascii_uppercase()
        );
    }

    Ok(())
}

fn contest_number(contest_id: &str) -> u32 {
    contest_id
        .trim_start_matches(|c: char| c.is_ascii_alphabetic())
        .parse::<u32>()
        .unwrap_or(0)
}

fn problem_index(problem_id: &str) -> Option<String> {
    problem_id
        .split('_')
        .last()
        .map(|idx| idx.to_ascii_lowercase())
}

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Contest {
    id: u32,
    name: String,
    #[serde(rename = "startTimeSeconds")]
    start_time_seconds: Option<u64>,
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

#[derive(Debug, Deserialize, Clone)]
struct AtcoderContest {
    id: String,
    #[serde(rename = "start_epoch_second")]
    start_epoch_second: Option<u64>,
}

#[derive(Debug, Deserialize, Clone)]
struct AtcoderProblem {
    id: String,
    #[serde(rename = "contest_id")]
    contest_id: String,
}

#[derive(Debug, Deserialize, Clone)]
struct AtcoderSubmission {
    #[serde(rename = "problem_id")]
    problem_id: String,
    result: String,
    #[serde(rename = "epoch_second")]
    epoch_second: u64,
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

fn fetch_contests(client: &Client, cutoff_ts: u64) -> Result<HashSet<u32>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/contest.list";
    let response: ApiResponse<Vec<Contest>> = client.get(url).send()?.json()?;

    let contest_ids: HashSet<u32> = response
        .result
        .into_iter()
        .filter(|contest| {
            contest.name.contains("Div. 2")
                && !contest.name.contains("Div. 1")
                && contest
                    .start_time_seconds
                    .map(|ts| ts < cutoff_ts)
                    .unwrap_or(false)
        })
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

fn fetch_atcoder_abc_contests(
    client: &Client,
    cutoff_ts: u64,
) -> Result<HashSet<String>, Box<dyn Error>> {
    let url = "https://kenkoooo.com/atcoder/resources/contests.json";
    thread::sleep(ATCODER_SLEEP_BETWEEN_CALLS);
    let response: Vec<AtcoderContest> =
        parse_json_payload(client.get(url).send()?, "contests.json")?;

    let contests: HashSet<String> = response
        .into_iter()
        .filter(|contest| {
            contest.id.to_lowercase().starts_with("abc")
                && contest
                    .start_epoch_second
                    .map(|ts| ts < cutoff_ts)
                    .unwrap_or(false)
        })
        .map(|contest| contest.id)
        .collect();

    Ok(contests)
}

fn fetch_atcoder_problems(client: &Client) -> Result<Vec<AtcoderProblem>, Box<dyn Error>> {
    let url = "https://kenkoooo.com/atcoder/resources/problems.json";
    thread::sleep(ATCODER_SLEEP_BETWEEN_CALLS);
    let problems: Vec<AtcoderProblem> =
        parse_json_payload(client.get(url).send()?, "problems.json")?;

    Ok(problems)
}

fn fetch_atcoder_user_submissions(
    client: &Client,
    handle: &str,
) -> Result<HashSet<String>, Box<dyn Error>> {
    let canonical_handle = handle.to_lowercase();
    let mut from_second: u64 = 0;
    let mut accepted = HashSet::new();

    loop {
        let url = format!(
            "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={}&from_second={}",
            canonical_handle, from_second
        );

        // Respect API guidance to sleep between accesses.
        thread::sleep(ATCODER_SLEEP_BETWEEN_CALLS);

        let submissions: Vec<AtcoderSubmission> =
            parse_json_payload(client.get(&url).send()?, "results")?;

        if submissions.is_empty() {
            break;
        }

        let mut max_epoch = from_second;
        for submission in submissions {
            if submission.result == "AC" {
                accepted.insert(submission.problem_id.clone());
            }
            if submission.epoch_second > max_epoch {
                max_epoch = submission.epoch_second;
            }
        }

        if max_epoch == from_second {
            break;
        }

        from_second = max_epoch + 1;
    }

    Ok(accepted)
}

fn parse_json_payload<T>(
    response: reqwest::blocking::Response,
    label: &str,
) -> Result<Vec<T>, Box<dyn Error>>
where
    T: DeserializeOwned,
{
    let status = response.status();
    let text = response.text()?;

    if !status.is_success() {
        let snippet: String = text.chars().take(200).collect();
        return Err(format!(
            "Failed to fetch {}: HTTP {}. Response starts with: {}",
            label, status, snippet
        )
        .into());
    }

    let value: serde_json::Value = serde_json::from_str(&text).map_err(|err| {
        let snippet: String = text.chars().take(200).collect();
        format!(
            "Failed to parse {} as JSON: {}. Response starts with: {}",
            label, err, snippet
        )
    })?;

    let items = match value {
        serde_json::Value::Array(array) => array,
        serde_json::Value::Object(map) => map.into_iter().map(|(_, value)| value).collect(),
        _ => {
            return Err(format!(
                "Unexpected JSON payload for {}: expected array or object, got {:?}",
                label, value
            )
            .into())
        }
    };

    items
        .into_iter()
        .map(serde_json::from_value)
        .collect::<Result<Vec<T>, _>>()
        .map_err(|err| err.into())
}
