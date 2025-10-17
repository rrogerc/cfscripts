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

    let value = match args.next() {
        Some(v) => v,
        None => {
            print_usage();
            process::exit(1);
        }
    };

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
            let level: u32 = value.parse().unwrap_or_else(|_| {
                println!(
                    "Error: Could not parse the provided level. Please provide a valid integer."
                );
                process::exit(1);
            });
            cf::run(&client, level)
        }
        Platform::AtCoder => atc::run(&client, &value),
    }
}

fn print_usage() {
    println!(
        "Problem Picker\n\
        Usage:\n\
          cf-lvl codeforces [level]    # Codeforces Div. 2\n\
          cf-lvl atcoder [index]       # AtCoder ABC\n\
        Notes:\n\
          - Levels map to problem ratings (level * 100) on Codeforces.\n\
          - For AtCoder, provide the task letter (a, b, c, ...)."
    );
}
