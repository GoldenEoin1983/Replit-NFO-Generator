#!/usr/bin/env python3
"""
Config file validator.

WHAT THIS FILE DOES
-------------------
Checks a filled-in 'stash-tools.toml' for mistakes BEFORE you run the
tools, and reports everything wrong in one go:

    - TOML syntax errors (missing quotes, stray characters, ...)
    - section names the tools don't know (e.g. [galery] typo)
    - option names the tools don't know (e.g. qualty = 85)
    - wrong value types (e.g. quality = "85" instead of quality = 85)
    - values outside the allowed range or choice list
      (e.g. quality = 150, font = "arial", size = "big")

Run it like this (uses ./stash-tools.toml when no file is given):

    python scripts/validate_config.py
    python scripts/validate_config.py path/to/my-config.toml

Exit code 0 means the file is valid; 1 means problems were found -
so scripts and agents can rely on the exit code.
"""

import re
import sys
import tomllib
from pathlib import Path

# Make imports work no matter where the script is run from
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# The schema: every section and option the tools understand, with the
# expected type and (where it applies) the allowed values or range.
# Kept in sync with the tools by scripts/check_config_coverage.py.
# ---------------------------------------------------------------------------
SIZE_PATTERN = re.compile(r"^(\d+x\d+|\d+(\.\d+)?%)$")   # "1920x1080" or "50%"
WXH_PATTERN = re.compile(r"^\d+x\d+$")                   # "800x310"

SCHEMA = {
    "output": {
        "output": {"type": str},
        "prefix": {"type": str},
    },
    "gallery": {
        "count":    {"type": int,   "min": 1},
        "interval": {"type": float, "min": 0.1},
        "format":   {"type": str,   "choices": ["jpg", "png", "webp"]},
        "quality":  {"type": int,   "min": 1, "max": 100},
        "size":     {"type": str,   "pattern": SIZE_PATTERN,
                     "hint": "use WxH pixels like \"1920x1080\" or a percentage like \"50%\""},
        "start":    {"type": float, "min": 0, "max": 100},
        "end":      {"type": float, "min": 0, "max": 100},
    },
    "animation": {
        "format":         {"type": str, "choices": ["gif", "webp"]},
        "frame_duration": {"type": int, "min": 1},
        "loop":           {"type": int, "min": 0},
    },
    "clearlogo": {
        "font":          {"type": str, "choices": ["bebas", "anton", "montserrat"]},
        "color":         {"type": str, "choices": ["white", "black"]},
        "size":          {"type": str, "pattern": WXH_PATTERN,
                          "hint": "use WxH pixels like \"800x310\""},
        "padding":       {"type": int, "min": 0},
        "filter_years":  {"type": bool},
        "filter_actors": {"type": str},
    },
    "nfo": {
        "pretty":         {"type": bool},
        "extract_images": {"type": bool},
        "overwrite":      {"type": bool},
        "encoding":       {"type": str, "encoding": True},
        "genre_tags":       {"type": str},
        "genre_parent_tag": {"type": str},
    },
    "stash_api": {
        "stash_host":     {"type": str},
        "stash_port":     {"type": str,
                           "hint": "port goes in quotes, e.g. stash_port = \"9999\""},
        "stash_scheme":   {"type": str, "choices": ["http", "https"]},
        "stash_api_key":  {"type": str},
        "stash_username": {"type": str},
        "stash_password": {"type": str},
    },
}

# Friendly names for types in error messages
TYPE_NAMES = {int: "a whole number", float: "a number",
              bool: "true or false", str: "text in quotes"}


def check_value(section: str, key: str, value, rule: dict) -> list[str]:
    """Check one option's value against its schema rule.

    Returns a list of problem descriptions (empty list = value is fine).
    """
    problems = []
    expected = rule["type"]
    where = f"[{section}] {key}"

    # TOML reads 30 as an int; accept it where a decimal is expected
    if expected is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)

    # In Python True/False also count as ints - don't allow that mixup
    bad_bool = expected is not bool and isinstance(value, bool)
    if bad_bool or not isinstance(value, expected):
        problems.append(f"{where}: should be {TYPE_NAMES[expected]}, "
                        f"but got {value!r}")
        return problems  # further checks need the right type first

    if "choices" in rule and value not in rule["choices"]:
        allowed = ", ".join(f'"{c}"' for c in rule["choices"])
        problems.append(f"{where}: {value!r} is not one of: {allowed}")

    if "min" in rule and value < rule["min"]:
        problems.append(f"{where}: {value} is too small (minimum {rule['min']})")
    if "max" in rule and value > rule["max"]:
        problems.append(f"{where}: {value} is too big (maximum {rule['max']})")

    if "pattern" in rule and not rule["pattern"].match(value):
        hint = rule.get("hint", "")
        problems.append(f"{where}: {value!r} has the wrong format - {hint}")

    if rule.get("encoding"):
        import codecs
        try:
            codecs.lookup(value)
        except LookupError:
            problems.append(f"{where}: {value!r} is not a known text "
                            f"encoding (try \"utf-8\")")
    return problems


def main() -> int:
    # Which file to check: the one given, or the default in this project
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "stash-tools.toml"
    if not path.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        return 1

    # Step 1: is it valid TOML at all?
    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(f"{path}: TOML syntax error: {e}", file=sys.stderr)
        print("Every setting should look like  key = value  under a "
              "[section] heading. Guide: https://toml.io/en/", file=sys.stderr)
        return 1

    problems = []

    # Step 2: check sections, option names, types, and values
    for section, data in config.items():
        if section not in SCHEMA:
            known = ", ".join(f"[{s}]" for s in SCHEMA)
            problems.append(f"[{section}]: unknown section (known: {known})")
            continue
        if not isinstance(data, dict):
            problems.append(f"[{section}]: expected a section, not a value")
            continue
        for key, value in data.items():
            rule = SCHEMA[section].get(key)
            if rule is None:
                known = ", ".join(sorted(SCHEMA[section]))
                problems.append(f"[{section}] {key}: unknown option "
                                f"(known: {known})")
                continue
            problems.extend(check_value(section, key, value, rule))

    # Step 3: cross-option sanity checks
    gallery = config.get("gallery", {})
    if isinstance(gallery, dict) and "count" in gallery and "interval" in gallery:
        problems.append("[gallery]: both 'count' and 'interval' are set - "
                        "pick one (if you keep both, count wins)")
    if isinstance(gallery, dict):
        start, end = gallery.get("start"), gallery.get("end")
        if (isinstance(start, (int, float)) and isinstance(end, (int, float))
                and not isinstance(start, bool) and not isinstance(end, bool)
                and start >= end):
            problems.append(f"[gallery]: start ({start}) must be smaller "
                            f"than end ({end})")

    # Step 4: report
    if problems:
        print(f"{path}: {len(problems)} problem(s) found:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    active = sum(len(v) for v in config.values() if isinstance(v, dict))
    print(f"{path}: valid. {active} active setting(s) in "
          f"{len(config)} section(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
