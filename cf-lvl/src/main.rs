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

    let platform_arg = match args.next() {
        Some(arg) => arg,
        None => {
            print_usage();
            process::exit(1);
        }
    };

    if matches!(platform_arg.as_str(), "-h" | "--help" | "help") {
        print_usage();
        return Ok(());
    }

    // Collect remaining arguments to support flags like --level
    let rest: Vec<String> = args.collect();

    let platform = match Platform::from_arg(&platform_arg) {
        Ok(p) => p,
        Err(msg) => {
            println!("{}", msg);
            print_usage();
            process::exit(1);
        }
    };

    let client = build_client()?;

    match platform {
        Platform::Codeforces => {
            if rest.is_empty() {
                print_usage();
                process::exit(1);
            }

            // Patterns supported:
            //   cf-lvl codeforces <letter>
            //   cf-lvl codeforces --level <num>
            //   cf-lvl codeforces -l <num>
            //   cf-lvl codeforces <num> --level
            let is_flag = |s: &str| s == "--level" || s == "-l";

            if is_flag(&rest[0]) {
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
            } else if rest.len() >= 2 && is_flag(&rest[1]) {
                let level: u32 = rest[0].parse().unwrap_or_else(|_| {
                    println!(
                        "Error: Could not parse the provided level. Please provide a valid integer."
                    );
                    process::exit(1);
                });
                cf::run_level(&client, level)
            } else {
                // Default to index letter mode
                cf::run_index(&client, &rest[0])
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
          cf-lvl codeforces [index]         # Codeforces Div. 2 by index\n\
          cf-lvl atcoder [index]             # AtCoder ABC\n\
          cf-lvl codeforces --level [level]  # Codeforces by rating level (x100)\n\
        Notes:\n\
          - For Codeforces, default is the problem index letter (A, B, C, ...).\n\
          - Use --level (or -l) to select by Codeforces rating level (level * 100), minumum 800.\n\
          - For AtCoder, provide the task letter (a, b, c, ...)."
    );
}
