# CfScripts - Codeforces & AtCoder CLI tools

A collection of competitive programming tools for [Codeforces](https://codeforces.com) and [AtCoder](https://atcoder.jp), using the [Codeforces API](https://codeforces.com/apiHelp) and the [Kenkoooo AtCoder API](https://github.com/kenkoooo/AtCoderProblems).

![Preview](cfscripts_final.gif)

## Commands

| Command | Description |
|---------|-------------|
| `cfscripts whatif` | What if virtual/unofficial participations were official? Simulates rating history. |
| `cfscripts vperf` | Calculate rank/delta/performance of recent contest participations. |
| `cfscripts unsolved` | Find unsolved problems from contests you've participated in. |
| `cfscripts account` | Cumulative AC count since each date. |
| `cfscripts dailyacs` | Problems solved per day with ratings. |
| `cfscripts rangerank` | Your rank among nearby-rated contestants in a contest. |
| `cfscripts pick` | Pick an unsolved Codeforces Div. 2 problem by rating level or index. |
| `cfscripts dist` | Rating distribution of Div. 2 problems. |
| `cfscripts stats` | Solved problem stats by rating (bar chart). |
| `cfscripts atcpick` | Pick an unsolved AtCoder ABC problem by task letter. |

Run `cfscripts --help` or `cfscripts <command> --help` for full usage details.

## Installation

Clone and install as a Python package:

```bash
git clone https://github.com/rrogerc/cfscripts.git
cd cfscripts
pip install -e .
```

Then run:

```bash
cfscripts --help
```

## Configuration

Create a `.cfscripts.json` file in your project directory (or any parent directory):

```json
{
    "handle": "YourCodeforcesHandle",
    "cpp_dir": "~/competitive/Codeforces"
}
```

- `handle` (required): Your Codeforces username.
- `cpp_dir` (optional): Directory for C++ file stubs created by `pick`.

The handle can also be overridden per-invocation with `--handle`.

## Development

### Prerequisites

- Python >= 3.9
- `pip`

### Directory Structure

```
src/cfscripts/
    cli.py              # CLI entry point (argparse)
    config.py           # .cfscripts.json loader
    lib/                # Codeforces/AtCoder API clients, rating calculator
    scripts/            # Individual command implementations
devtools/               # PyInstaller build scripts
```

### Building

Build a standalone executable with PyInstaller:

```bash
pip install pyinstaller
./devtools/build.sh
```

The `bin/` directory will contain the `cfscripts` executable.

## Credits

Originally created by William Bille Meyling (cf: [WillTheBill](https://codeforces.com/profile/WillTheBill), github: [willthbill](https://github.com/willthbill)).
