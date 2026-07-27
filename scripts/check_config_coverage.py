#!/usr/bin/env python3
"""
Config coverage checker.

WHAT THIS FILE DOES
-------------------
Makes sure the config file system stays in sync with the command-line
options of all three tools. It answers four questions:

    1. Does every command-line option have a matching config option
       (or a documented reason why it is command-line only)?
    2. Does every config option the tools understand actually match a
       real command-line option (no leftovers after a rename)?
    3. Is every config option shown in the sample 'stash-tools.toml',
       in the RIGHT [section], so users can discover it?
    4. Does the validator's schema (scripts/validate_config.py) agree
       with the tools - same sections, same keys, same types?

Run it any time you add, rename, or remove a command-line option:

    python scripts/check_config_coverage.py

It prints what is wrong and exits with code 1 on failure, 0 when all
is well - so scripts and agents can rely on the exit code.

HOW IT WORKS
------------
It reads each tool's source code with Python's 'ast' module (a safe way
to inspect code without running it) and collects every add_argument()
call plus the _*_CONFIG_TYPES dictionaries. It then cross-checks those
against the sample config and the validator's SCHEMA.
"""

import ast
import re
import sys
from pathlib import Path

# Make imports work no matter where the script is run from
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_config import SCHEMA  # import works thanks to the path setup above

# ---------------------------------------------------------------------------
# What we EXPECT to be command-line only (with the reason why).
# If you add a new option that should NOT go in the config file,
# add it here with a short reason. Anything not listed here and not
# in the config is reported as a gap.
# ---------------------------------------------------------------------------
CLI_ONLY = {
    "stash_to_nfo.py": {
        "input_file":  "positional input path - different every run",
        "output_file": "positional output path - different every run",
        "stash_id":    "one-off lookup value - different every run",
        "search":      "one-off search text - different every run",
        "type":        "auto-detect works; forcing a type is a one-off fix",
        "verbose":     "debugging switch, not a saved preference",
        "config":      "points at the config file itself",
    },
    "video_gallery.py": {
        "video":       "positional input path - different every run",
        "start_time":  "exact timestamps are per-video, not a preference",
        "end_time":    "exact timestamps are per-video, not a preference",
        "animate":     "mode switch that decides which config section applies",
        "verbose":     "debugging switch, not a saved preference",
        "config":      "points at the config file itself",
    },
    "clearlogo.py": {
        "title":       "positional title text - different every run",
        "output":      "output filename is derived from the title",
        "verbose":     "debugging switch, not a saved preference",
        "config":      "points at the config file itself",
    },
}

# Which config section each _*_CONFIG_TYPES dictionary feeds.
# (Must match the get_section(...) calls in the tools.)
DICT_TO_SECTION = {
    "_NFO_CONFIG_TYPES":       "nfo",
    "_API_CONFIG_TYPES":       "stash_api",
    "_OUTPUT_CONFIG_TYPES":    "output",
    "_GALLERY_CONFIG_TYPES":   "gallery",
    "_ANIMATION_CONFIG_TYPES": "animation",
    "_CLEARLOGO_CONFIG_TYPES": "clearlogo",
}

SAMPLE_CONFIG = ROOT / "stash-tools.toml"


def collect_cli_options(source: str) -> set[str]:
    """
    Find every add_argument() call in a tool's source code and return
    the option names as argparse "dest" names (dashes -> underscores).

    E.g. --frame-duration becomes 'frame_duration', and a positional
    argument like "video" stays 'video'.
    """
    dests = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # We only care about calls that look like: something.add_argument(...)
        is_add_arg = (isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute)
                      and node.func.attr == "add_argument")
        if not is_add_arg:
            continue
        names = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not names:
            continue
        # Prefer the long form (--frame-duration) over short (-f)
        long_names = [n for n in names if n.startswith("--")]
        if long_names:
            dests.add(long_names[0].lstrip("-").replace("-", "_"))
        elif not names[0].startswith("-"):
            dests.add(names[0])  # positional argument
    return dests


def collect_config_dicts(source: str) -> dict[str, dict[str, str]]:
    """
    Find every _*_CONFIG_TYPES dictionary in a tool's source code.

    Returns {dict_name: {option_key: type_name}}, e.g.
    {'_GALLERY_CONFIG_TYPES': {'count': 'int', 'interval': 'float', ...}}
    """
    found = {}
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            named_types_dict = (isinstance(target, ast.Name)
                                and target.id.endswith("_CONFIG_TYPES")
                                and isinstance(node.value, ast.Dict))
            if not named_types_dict:
                continue
            entries = {}
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                    entries[k.value] = v.id  # e.g. 'count' -> 'int'
            found[target.id] = entries
    return found


def sample_config_sections(text: str) -> dict[str, set[str]]:
    """
    Return every option name mentioned in the sample stash-tools.toml,
    grouped by the [section] it appears under. Commented-out entries
    count too (that's how the sample shows available options).
    """
    sections: dict[str, set[str]] = {}
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        header = re.match(r"^\[([a-z_]+)\]$", stripped)
        if header:
            current = header.group(1)
            sections.setdefault(current, set())
            continue
        # Match lines like:  key = value   or   #key = value
        m = re.match(r"^#?\s*([a-z_]+)\s*=", stripped)
        if m and current:
            sections[current].add(m.group(1))
    return sections


def main() -> int:
    problems = []
    sample = sample_config_sections(SAMPLE_CONFIG.read_text(encoding="utf-8"))

    # Collected across all tools, for the validator-schema comparison:
    # {section: {key: type_name}}
    tool_schema: dict[str, dict[str, str]] = {}

    for tool, cli_only in CLI_ONLY.items():
        source = (ROOT / tool).read_text(encoding="utf-8")
        cli_opts = collect_cli_options(source)
        config_dicts = collect_config_dicts(source)

        config_keys = set()
        for dict_name, entries in config_dicts.items():
            config_keys |= set(entries)
            section = DICT_TO_SECTION.get(dict_name)
            if section is None:
                problems.append(
                    f"{tool}: dictionary '{dict_name}' is not mapped to a "
                    f"config section (update DICT_TO_SECTION in this script)")
                continue
            tool_schema.setdefault(section, {}).update(entries)

            # 3. Every config key is shown in the sample, under the
            #    correct [section] heading
            for key in sorted(set(entries) - sample.get(section, set())):
                problems.append(
                    f"stash-tools.toml: [{section}] is missing a sample "
                    f"entry for '{key}' (used by {tool})")

        # 1. Every CLI option is either configurable or documented CLI-only
        for opt in sorted(cli_opts - config_keys - set(cli_only)):
            problems.append(
                f"{tool}: option '--{opt.replace('_', '-')}' has no config "
                f"entry and is not listed as command-line only")

        # 2. Every config key matches a real CLI option (catch renames)
        for key in sorted(config_keys - cli_opts):
            problems.append(
                f"{tool}: config option '{key}' has no matching "
                f"command-line option (was it renamed or removed?)")

        # CLI-only entries should still be real options (catch typos here)
        for opt in sorted(set(cli_only) - cli_opts):
            problems.append(
                f"{tool}: CLI_ONLY lists '{opt}' but no such option exists "
                f"(update CLI_ONLY in scripts/check_config_coverage.py)")

    # 4. The validator's SCHEMA must agree with the tools:
    #    same sections, same keys, same types.
    for section in sorted(set(tool_schema) - set(SCHEMA)):
        problems.append(
            f"validate_config.py: SCHEMA is missing section [{section}]")
    for section in sorted(set(SCHEMA) - set(tool_schema)):
        problems.append(
            f"validate_config.py: SCHEMA has section [{section}] "
            f"that no tool reads")
    for section in sorted(set(SCHEMA) & set(tool_schema)):
        tool_keys, schema_keys = tool_schema[section], SCHEMA[section]
        for key in sorted(set(tool_keys) - set(schema_keys)):
            problems.append(
                f"validate_config.py: SCHEMA [{section}] is missing '{key}'")
        for key in sorted(set(schema_keys) - set(tool_keys)):
            problems.append(
                f"validate_config.py: SCHEMA [{section}] has extra "
                f"key '{key}' that the tools don't understand")
        for key in sorted(set(schema_keys) & set(tool_keys)):
            schema_type = schema_keys[key]["type"].__name__
            if schema_type != tool_keys[key]:
                problems.append(
                    f"validate_config.py: SCHEMA [{section}] '{key}' is "
                    f"typed {schema_type}, but the tool expects "
                    f"{tool_keys[key]}")

    if problems:
        print("Config coverage problems found:\n")
        for p in problems:
            print(f"  - {p}")
        print(f"\n{len(problems)} problem(s). Fix the tool, the sample "
              f"config, the validator SCHEMA, or the lists in this script.")
        return 1

    print("Config coverage OK: every command-line option is configurable "
          "or documented as command-line only, the sample config and the "
          "validator schema both match the tools.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
