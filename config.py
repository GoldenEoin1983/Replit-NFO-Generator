"""
Project configuration loader.

WHAT THIS FILE DOES
-------------------
Lets you save your favourite settings once in a config file
('stash-tools.toml') instead of typing the same command-line options
every time. Once you've made a few galleries or GIFs the way you like,
put those values in the config and every future run uses them.

HOW SETTINGS WIN
----------------
The order of priority (highest first) is:
    1. Options typed on the command line   (always win)
    2. Values in the config file           (your saved preferences)
    3. Built-in defaults                   (used when nothing else is set)

The config file uses TOML - a simple "key = value" format grouped into
[sections], designed to be easy for humans to read and edit.
TOML basics: https://toml.io/en/
"""

import sys
import tomllib  # built into Python 3.11+ for reading TOML files
from pathlib import Path
from typing import Any

# The filename we look for in the current folder when --config isn't given
DEFAULT_CONFIG_NAME = "stash-tools.toml"


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Load the TOML config file and return it as a nested dictionary.

    Args:
        config_path: Explicit path from --config, or None to auto-detect
                     'stash-tools.toml' in the current folder.

    Returns:
        The parsed config, e.g. {'gallery': {'format': 'webp', ...}, ...}.
        Returns an empty dict when no config file exists (that's fine -
        the tools just use their built-in defaults).

    Exits with an error message if the file was named explicitly but is
    missing, or if the TOML has a syntax mistake.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            # The user asked for a specific file - missing is an error
            print(f"Error: config file not found: {path}", file=sys.stderr)
            sys.exit(1)
    else:
        path = Path(DEFAULT_CONFIG_NAME)
        if not path.exists():
            return {}  # no config file - not a problem

    try:
        with open(path, 'rb') as f:  # tomllib needs binary mode
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(f"Error: could not read '{path}': {e}", file=sys.stderr)
        print("Check the file for typos - every line should look like "
              "key = value under a [section] heading.", file=sys.stderr)
        sys.exit(1)


def get_section(config: dict[str, Any], section: str) -> dict[str, Any]:
    """
    Return one [section] of the config as a flat dictionary.

    Args:
        config: The full config from load_config()
        section: Section name, e.g. 'gallery' or 'clearlogo'

    Returns:
        The section's key/value pairs, or {} if the section is absent.
    """
    data = config.get(section, {})
    return data if isinstance(data, dict) else {}


def check_config_types(section_data: dict[str, Any],
                       types: dict[str, type],
                       section_name: str) -> dict[str, Any]:
    """
    Make sure each config value has the type the tool expects, with a
    friendly error message when it doesn't.

    For example quality = "85" (text, because of the quotes) instead of
    quality = 85 (a number) would otherwise crash later with a confusing
    error deep inside the program.

    Whole numbers are quietly accepted where decimals are expected
    (interval = 30 works the same as interval = 30.0).

    Args:
        section_data: Key/value pairs from one config section
        types: Expected Python type for each key (int, float, bool, str)
        section_name: Used in error messages, e.g. 'gallery'

    Returns:
        The (possibly int->float converted) key/value pairs.
    """
    type_names = {int: "a whole number", float: "a number",
                  bool: "true or false", str: "text in quotes"}
    checked = {}
    for key, value in section_data.items():
        expected = types.get(key)
        if expected is None:
            checked[key] = value
            continue
        # TOML reads 30 as int; promote it when the tool wants a float
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        # In Python, True/False also count as ints - don't allow that mixup
        bad_bool = expected is not bool and isinstance(value, bool)
        if bad_bool or not isinstance(value, expected):
            print(f"Error: config [{section_name}] '{key}' should be "
                  f"{type_names.get(expected, expected.__name__)}, "
                  f"but got: {value!r}", file=sys.stderr)
            sys.exit(1)
        checked[key] = value
    return checked


def apply_config_defaults(parser, section_data: dict[str, Any],
                          allowed_keys: set[str],
                          types: dict[str, type] | None = None,
                          section_name: str = "") -> None:
    """
    Feed config values into an argparse parser as its new defaults.

    Because they're only *defaults*, anything typed on the command line
    still overrides them - which gives us the priority order described
    at the top of this file.

    Args:
        parser: The argparse.ArgumentParser to update
        section_data: Key/value pairs from one config section
        allowed_keys: Which keys this tool understands (typos in the
                      config are reported instead of silently ignored)
        types: Optional expected type per key (checked with a friendly
               error instead of a crash later)
        section_name: Section name for error messages
    """
    unknown = set(section_data) - allowed_keys
    if unknown:
        print(f"Warning: ignoring unknown config option(s): "
              f"{', '.join(sorted(unknown))}", file=sys.stderr)

    defaults = {key: value for key, value in section_data.items()
                if key in allowed_keys}
    if types:
        defaults = check_config_types(defaults, types, section_name)
    if defaults:
        parser.set_defaults(**defaults)
