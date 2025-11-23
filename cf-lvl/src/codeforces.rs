use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::{BTreeMap, HashSet};
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

const CODEFORCES_HANDLE: &str = "Exonerate";
const CODEFORCES_CPP_DIR: &str = "/Users/rogerchen/Developer/competitive/Codeforces";

#[derive(Debug, Deserialize, Eq, PartialEq, Hash)]
struct Problem {
    #[serde(rename = "contestId")]
    contest_id: u32,
    index: String,
    rating: u32,
    name: String,
}

#[derive(Debug, Deserialize)]
struct Contest {
    id: u32,
    name: String,
}

#[derive(Debug, Deserialize)]
struct ApiResponse<T> {
    result: T,
}

#[derive(Debug, Deserialize)]
struct ProblemsetResult {
    problems: Vec<UnratedProblem>,
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
    name: String,
    rating: Option<u32>,
}

pub fn run_level(client: &Client, level: u32) -> Result<(), Box<dyn Error>> {
    if level < 8 || level > 32 {
        println!("Error: Level must be an integer between 8 and 32 inclusive.");
        return Ok(());
    }

    let rated_problems = fetch_problem_set(client)?;
    let div2_contests = fetch_contests(client)?;
    let passed_problems = fetch_user_submissions(client)?;

    let solved: HashSet<(u32, String)> = passed_problems
        .into_iter()
        .map(|problem| (problem.contest_id, problem.index))
        .collect();

    // Single-pass selection of the latest qualifying problem
    let target_rating = level * 100;
    let mut best: Option<Problem> = None;
    for p in rated_problems.into_iter() {
        if p.rating != target_rating {
            continue;
        }
        if !div2_contests.contains(&p.contest_id) {
            continue;
        }
        if solved.contains(&(p.contest_id, p.index.clone())) {
            continue;
        }

        match &best {
            Some(cur) if cur.contest_id >= p.contest_id => {}
            _ => best = Some(p),
        }
    }

    if let Some(problem) = best {
        let url = format!(
            "https://codeforces.com/problemset/problem/{}/{}",
            problem.contest_id, problem.index
        );

        if let Err(err) = create_cpp_stub(&problem) {
            eprintln!("Warning: could not create starter file: {}", err);
        }

        if webbrowser::open(&url).is_ok() {
            println!(
                "Opening Codeforces Div. 2 problem: contest {} problem {} (rating {})",
                problem.contest_id,
                problem.index,
                problem.rating
            );
        } else {
            println!("Failed to open problem");
        }
    } else {
        println!(
            "No problem with rating {} found (Level {}).",
            target_rating,
            level
        );
    }

    Ok(())
}

pub fn run_distribution(client: &Client) -> Result<(), Box<dyn Error>> {
    let rated_problems = fetch_problem_set(client)?;
    let div2_contests = fetch_contests(client)?;

    let mut distribution: BTreeMap<u32, u32> = BTreeMap::new();

    for problem in rated_problems.into_iter() {
        if div2_contests.contains(&problem.contest_id) {
            *distribution.entry(problem.rating).or_insert(0) += 1;
        }
    }

    if distribution.is_empty() {
        println!("No rated Codeforces Div. 2 problems found.");
    } else {
        println!("Rating distribution for Codeforces Div. 2 problems:");
        let mut total: u32 = 0;
        for (rating, count) in &distribution {
            println!("  {}: {}", rating, count);
            total += *count;
        }
        println!("Total problems: {}", total);
    }

    Ok(())
}

pub fn run_index(client: &Client, index_input: &str) -> Result<(), Box<dyn Error>> {
    let letter = normalize_index(index_input)?;

    let rated_problems = fetch_problem_set(client)?;
    let div2_contests = fetch_contests(client)?;
    let passed_problems = fetch_user_submissions(client)?;

    let solved: HashSet<(u32, String)> = passed_problems
        .into_iter()
        .map(|problem| (problem.contest_id, problem.index))
        .collect();

    // Pick the latest Div. 2 problem matching the index letter and unsolved
    let mut best: Option<Problem> = None;
    for p in rated_problems.into_iter() {
        if !div2_contests.contains(&p.contest_id) {
            continue;
        }

        let mut chars = p.index.chars();
        let starts_with_letter = chars
            .next()
            .map(|c| c.to_ascii_uppercase() == letter)
            .unwrap_or(false);
        if !starts_with_letter {
            continue;
        }

        if solved.contains(&(p.contest_id, p.index.clone())) {
            continue;
        }

        match &best {
            Some(cur) if cur.contest_id >= p.contest_id => {}
            _ => best = Some(p),
        }
    }

    if let Some(problem) = best {
        let url = format!(
            "https://codeforces.com/problemset/problem/{}/{}",
            problem.contest_id, problem.index
        );

        if let Err(err) = create_cpp_stub(&problem) {
            eprintln!("Warning: could not create starter file: {}", err);
        }

        if webbrowser::open(&url).is_ok() {
            println!(
                "Opening Codeforces Div. 2 contest {} problem {}",
                problem.contest_id, problem.index
            );
        } else {
            println!("Failed to open problem");
        }
    } else {
        println!(
            "No unsolved Codeforces Div. 2 '{}' problem found.",
            letter
        );
    }

    Ok(())
}

fn normalize_index(input: &str) -> Result<char, Box<dyn Error>> {
    let trimmed = input.trim();
    if trimmed.len() != 1 || !trimmed.chars().all(|c| c.is_ascii_alphabetic()) {
        return Err("Problem index must be a single letter (e.g., A, B, C).".into());
    }
    Ok(trimmed.chars().next().unwrap().to_ascii_uppercase())
}

fn fetch_problem_set(client: &Client) -> Result<Vec<Problem>, Box<dyn Error>> {
    let url = "https://codeforces.com/api/problemset.problems";
    let response: ApiResponse<ProblemsetResult> = client.get(url).send()?.json()?;
    let problems: Vec<UnratedProblem> = response.result.problems;

    Ok(problems
        .into_iter()
        .filter_map(|problem| {
            problem.rating.map(|rating| Problem {
                contest_id: problem.contest_id,
                index: problem.index,
                name: problem.name,
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
            contest.name.contains("Div. 2") && !contest.name.contains("Div. 1")
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
                    name: submission.problem.name.clone(),
                    rating,
                })
            } else {
                None
            }
        })
        .collect())
}

fn create_cpp_stub(problem: &Problem) -> Result<PathBuf, Box<dyn Error>> {
    fs::create_dir_all(CODEFORCES_CPP_DIR)?;

    let file_name = format!("{}.cpp", sanitize_filename(&problem.name));
    let path = PathBuf::from(CODEFORCES_CPP_DIR).join(file_name);

    if path.exists() {
        return Ok(path);
    }

    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)?;

    let starter = r#"#include <iostream>

void solve();

int main() {
    int count_test_cases;

    std::cin >> count_test_cases;

    while (count_test_cases--) {
        solve();
    }
}

void solve() {
}
"#;

    file.write_all(starter.as_bytes())?;
    println!("Created starter file at {}", path.display());
    Ok(path)
}

fn sanitize_filename(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .map(|c| {
            if c == '/' || c == '\\' {
                '-'
            } else if c.is_control() {
                ' '
            } else {
                c
            }
        })
        .collect();

    let trimmed = cleaned.trim();
    if trimmed.is_empty() {
        "problem".to_string()
    } else {
        trimmed.to_string()
    }
}
