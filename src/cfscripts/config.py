import json
import os
from pathlib import Path


_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cfscripts"
_CONFIG_PATH = _CONFIG_DIR / "config.json"


def _load():
    if _CONFIG_PATH.is_file():
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def set_config(key, value):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = _load()
    config[key] = value
    with open(_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def get_config_value(key):
    return _load().get(key)


def load_config(cli_handle=None):
    config = _load()

    if cli_handle is not None:
        config["handle"] = cli_handle

    if config.get("cpp_dir"):
        config["cpp_dir"] = str(Path(os.path.expanduser(config["cpp_dir"])))

    if not config.get("handle"):
        print("Error: Missing config. Run:")
        print("  cfscripts config handle <your_codeforces_handle>")
        raise SystemExit(1)

    return config
