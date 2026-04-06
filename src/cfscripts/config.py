import json
import os
from pathlib import Path


_CONFIG_FILENAME = ".cfscripts.json"

_DEFAULTS = {
    "handle": None,
    "cpp_dir": None,
}


def _find_config_file():
    """Walk up from CWD looking for .cfscripts.json."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(cli_handle=None):
    """Load config from .cfscripts.json, with CLI overrides.

    Returns dict with keys: handle, cpp_dir.
    """
    config = dict(_DEFAULTS)

    config_path = _find_config_file()
    if config_path is not None:
        with open(config_path) as f:
            file_config = json.load(f)
        config.update(file_config)

    if cli_handle is not None:
        config["handle"] = cli_handle

    if config.get("cpp_dir"):
        config["cpp_dir"] = os.path.expanduser(config["cpp_dir"])

    if not config.get("handle"):
        print("Error: No handle configured. Set 'handle' in .cfscripts.json or use --handle.")
        raise SystemExit(1)

    return config
