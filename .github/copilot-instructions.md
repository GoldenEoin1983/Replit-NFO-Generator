# GitHub Copilot Instructions — StashApp Media Toolkit

> Full agent instructions are in **`AGENTS.md`** at the repo root. Read that file first.

## Quick reference for Copilot

### Project structure
- `stash_to_nfo.py` — NFO converter CLI (entry point)
- `parsers.py` / `converters.py` / `nfo_generator.py` — NFO conversion pipeline
- `stash_api.py` — StashApp GraphQL API client
- `video_gallery.py` — standalone video frame extractor and animator
- `clearlogo.py` — standalone clearlogo PNG generator
- `fonts/` — cached TTF files, do not edit

### Language and style
- Python 3.11+, type hints required
- `argparse` for all CLIs — use argument groups for organisation
- `pathlib.Path` for all file paths internally
- Errors: print to `sys.stderr`, call `sys.exit(1)` for fatal failures
- Docstrings: Google style (Args / Returns)
- No test framework — validate with `--verbose` flag and manual runs

### Key constraints
- NFO XML tag names must remain Kodi/Jellyfin compatible — check both before changing
- Do not break the three-tool standalone structure (no shared state between scripts)
- StashApp GraphQL IDs must be passed as `str` even when stored as `int`
- GIF animation requires palette-mode conversion before saving (Pillow limitation)
