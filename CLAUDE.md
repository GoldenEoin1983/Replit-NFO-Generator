# Claude Instructions — StashApp Media Toolkit

> Full agent instructions are in **`AGENTS.md`**. This file adds Claude-specific notes.

Read `AGENTS.md` first and completely before making any changes. Everything in that file applies here.

---

## Claude-Specific Guidance

### Tone and communication

- The user prefers **simple, everyday language** — avoid jargon when explaining changes.
- Keep explanations brief: lead with *what changed and why it matters*, not implementation details.
- When the user asks what something does, answer directly before showing code.

### Before editing

- Read the relevant source file before writing changes to it — never write from memory.
- Prefer `edit` (targeted string replacement) over rewriting an entire file unless the change is large.
- Run `python <script>.py --help` after any change to a CLI script to catch syntax errors early.

### File ownership

Each tool is self-contained. When modifying one tool:
- `stash_to_nfo.py` changes may need matching updates in `parsers.py`, `converters.py`, or `nfo_generator.py`.
- `video_gallery.py` is fully self-contained — no shared imports with other tools.
- `clearlogo.py` is fully self-contained — no shared imports with other tools.

### Testing after changes

```bash
# Quick smoke test for each tool
python stash_to_nfo.py attached_assets/Chef-At-Home.*.json --pretty -v
python video_gallery.py --help
python clearlogo.py "Test Title" --font bebas -v
```

### Things Claude should not do here

- Do not add a testing framework without being asked.
- Do not introduce async/await patterns — all tools are synchronous CLI scripts.
- Do not add a `setup.py` or convert to a package structure without being asked.
- Do not add logging infrastructure — the `--verbose` flag and `print()` to stderr is the current pattern.
