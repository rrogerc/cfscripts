use crate::utils;
use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::HashSet;
use std::error::Error;
use std::thread;
use std::time::Duration;

const CUTOFF_TS: u64 = 1672531200; // 2023-01-01 00:00:00 UTC
const ATCODER_HANDLE: &str = "Exonerate";
const API_THROTTLE: Duration = Duration::from_secs(1);

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

pub fn run(client: &Client, index_input: &str) -> Result<(), Box<dyn Error>> {
    let task_letter = normalize_index(index_input)?;

    let abc_contests = fetch_abc_contests(client)?;
    let problems = fetch_problems(client)?;
    let solved = fetch_user_submissions(client)?;

    let mut candidates: Vec<AtcoderProblem> = problems
        .into_iter()
        .filter(|problem| {
            abc_contests.contains(&problem.contest_id)
                && problem_index(&problem.id)
                    .map(|idx| idx == task_letter)
                    .unwrap_or(false)
        })
        .collect();

    candidates.sort_by(|a, b| {
        contest_number(&b.contest_id)
            .cmp(&contest_number(&a.contest_id))
            .then_with(|| a.id.cmp(&b.id))
    });

    if let Some(problem) = candidates
        .into_iter()
        .find(|problem| !solved.contains(&problem.id))
    {
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
            task_letter.to_ascii_uppercase()
        );
    }

    Ok(())
}

fn normalize_index(input: &str) -> Result<String, Box<dyn Error>> {
    let trimmed = input.trim().to_ascii_lowercase();

    if trimmed.len() != 1 || !trimmed.chars().all(|c| c.is_ascii_alphabetic()) {
        return Err("Problem index must be a single letter (e.g., a, b, c).".into());
    }

    Ok(trimmed)
}

fn fetch_abc_contests(client: &Client) -> Result<HashSet<String>, Box<dyn Error>> {
    let url = "https://kenkoooo.com/atcoder/resources/contests.json";
    throttle();
    let contests: Vec<AtcoderContest> = utils::fetch_json(client, url, "contests.json")?;

    Ok(contests
        .into_iter()
        .filter(|contest| {
            contest.id.to_lowercase().starts_with("abc")
                && contest
                    .start_epoch_second
                    .map(|ts| ts < CUTOFF_TS)
                    .unwrap_or(false)
        })
        .map(|contest| contest.id)
        .collect())
}

fn fetch_problems(client: &Client) -> Result<Vec<AtcoderProblem>, Box<dyn Error>> {
    let url = "https://kenkoooo.com/atcoder/resources/problems.json";
    throttle();
    utils::fetch_json(client, url, "problems.json")
}

fn fetch_user_submissions(client: &Client) -> Result<HashSet<String>, Box<dyn Error>> {
    let mut from_second: u64 = 0;
    let handle = ATCODER_HANDLE.to_ascii_lowercase();
    let mut accepted = HashSet::new();

    loop {
        let url = format!(
            "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={}&from_second={}",
            handle,
            from_second
        );

        throttle();
        let submissions: Vec<AtcoderSubmission> =
            utils::fetch_json(client, &url, "results")?;

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

fn throttle() {
    thread::sleep(API_THROTTLE);
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
