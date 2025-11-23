mod atcoder;
mod codeforces;
mod utils;

use crate::atcoder as atc;
use crate::codeforces as cf;
use crate::utils::build_client;
use std::env;
use std::error::Error;
use std::process;

enum Platform {
    Codeforces,
    AtCoder,
}

impl Platform {
    fn from_arg(value: &str) -> Result<Self, String> {
        match value.to_ascii_lowercase().as_str() {
            "cf" | "codeforces" => Ok(Platform::Codeforces),
            "ac" | "atcoder" => Ok(Platform::AtCoder),
            other => Err(format!(
                "Unrecognized platform '{other}'. Use 'codeforces' or 'atcoder'."
            )),
        }
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);

    let first_arg = match args.next() {
        Some(arg) => arg,
        None => {
            print_usage();
            process::exit(1);
        }
    };

    if matches!(first_arg.as_str(), "-h" | "--help" | "help") {
        print_usage();
        return Ok(());
    }

    // If the first arg is a known platform, use it; otherwise default to Codeforces and keep the arg.
    let (platform, rest): (Platform, Vec<String>) = match Platform::from_arg(&first_arg) {
        Ok(p) => (p, args.collect()),
        Err(_) => {
            let mut collected: Vec<String> = Vec::new();
            collected.push(first_arg);
            collected.extend(args);
            (Platform::Codeforces, collected)
        }
    };

    let client = build_client()?;

    match platform {
        Platform::Codeforces => {
            if rest.is_empty() {
                print_usage();
                process::exit(1);
            }

            let is_index_flag = |s: &str| s == "--index" || s == "-i";
            let is_level_flag = |s: &str| s == "--level" || s == "-l";

            if matches!(rest[0].as_str(), "dist" | "distribution" | "stats") {
                cf::run_distribution(&client)
            } else if rest.len() >= 2 && is_index_flag(&rest[0]) {
                cf::run_index(&client, &rest[1])
            } else if rest.len() >= 2 && is_index_flag(&rest[1]) {
                cf::run_index(&client, &rest[0])
            } else if rest.len() >= 2 && is_level_flag(&rest[0]) {
                if rest.len() < 2 {
                    println!("Error: Missing level after {}.", rest[0]);
                    process::exit(1);
                }
                let level: u32 = rest[1].parse().unwrap_or_else(|_| {
                    println!(
                        "Error: Could not parse the provided level. Please provide a valid integer."
                    );
                    process::exit(1);
                });
                cf::run_level(&client, level)
            } else if rest.len() >= 2 && is_level_flag(&rest[1]) {
                let level: u32 = rest[0].parse().unwrap_or_else(|_| {
                    println!(
                        "Error: Could not parse the provided level. Please provide a valid integer."
                    );
                    process::exit(1);
                });
                cf::run_level(&client, level)
            } else {
                // Default to level mode
                let level: u32 = rest[0].parse().unwrap_or_else(|_| {
                    println!(
                        "Error: Could not parse the provided level. Please provide a valid integer."
                    );
                    process::exit(1);
                });
                cf::run_level(&client, level)
            }
        }
        Platform::AtCoder => {
            if rest.is_empty() {
                print_usage();
                process::exit(1);
            }
            atc::run(&client, &rest[0])
        }
    }
}

fn print_usage() {
    println!(
        "Problem Picker\n\
        Usage:\n\
          cf-lvl [level]                     # Codeforces Div. 2 by level (x100), default platform\n\
          cf-lvl --index [letter]            # Codeforces Div. 2 by index (A, B, C, ...)\n\
          cf-lvl dist                        # Rating distribution of Codeforces Div. 2 problems\n\
          cf-lvl atcoder [index]             # AtCoder ABC (explicit platform)\n\
          cf-lvl codeforces ...              # Optional explicit Codeforces platform prefix\n\
        Notes:\n\
          - Codeforces default is level mode; provide level 8-32 (rating = level * 100), minimum 800.\n\
          - Use --index (or -i) to select by Codeforces problem index letter (A, B, C, ...).\n\
          - For AtCoder, provide the task letter (a, b, c, ...)."
    );
}
