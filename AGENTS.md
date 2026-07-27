# Agent Instructions — StashApp Media Toolkit

This file provides authoritative guidance for AI coding agents (Codex, Claude, Qwen, Copilot, ChatGPT, etc.) working on this repository.

---

## What This Project Is

A Python command-line toolkit that works alongside a self-hosted [StashApp](https://stashapp.cc) media server. It has three independent tools:

| Tool | Script | Purpose |
|---|---|---|
| NFO Converter | `stash_to_nfo.py` | Converts StashApp metadata → Kodi/Jellyfin NFO files |
| Video Gallery | `video_gallery.py` | Extracts still frames or animated GIF/WebP from video files |
| ClearLogo | `clearlogo.py` | Generates transparent clearlogo PNGs from media titles |

---

## Repository Layout

```
stash_to_nfo.py       # NFO converter — CLI entry point
parsers.py            # JSON file parsing and StashApp type auto-detection
converters.py         # StashApp field → NFO field mapping; base64 image extraction
nfo_generator.py      # XML / NFO file generation (Kodi/Jellyfin format)
stash_api.py          # StashApp GraphQL API client (wraps stashapp-tools)

video_gallery.py      # Standalone video frame extractor and animator

clearlogo.py          # Standalone clearlogo PNG generator

fonts/                # Cached TTF fonts downloaded from Google Fonts
  bebas.ttf           #   Bebas Neue Regular
  anton.ttf           #   Anton Regular
  montserrat.ttf      #   Montserrat ExtraBold

example_output.nfo    # Sample NFO output (real data, not a mock)
README.md             # User-facing documentation
pyproject.toml        # Project metadata and dependencies
```

**Do not edit files in `fonts/`.** They are downloaded automatically by `clearlogo.py` if missing.

---

## Dependencies

Python **3.11+** is required.

```bash
pip install stashapp-tools opencv-python-headless Pillow
```

- `stashapp-tools` — GraphQL client for StashApp's API (used in `stash_api.py`)
- `opencv-python-headless` — video decoding (used in `video_gallery.py`)
- `Pillow` — image processing, animated GIF/WebP output, clearlogo rendering

No other third-party dependencies. All other imports are Python standard library.

---

## Running the Tools

```bash
# NFO conversion — file input
python stash_to_nfo.py scene.json
python stash_to_nfo.py scene.json output.nfo --pretty --extract-images

# NFO conversion — live StashApp API
python stash_to_nfo.py --stash-id 42
python stash_to_nfo.py --search "movie title" --stash-api-key YOUR_KEY

# Video gallery — still frames
python video_gallery.py movie.mp4 --count 24 --format jpg
python video_gallery.py movie.mp4 --interval 30 --size 1280x720 --output ./frames

# Video gallery — animated output
python video_gallery.py movie.mp4 --count 16 --format gif --animate --frame-duration 400
python video_gallery.py movie.mp4 --interval 30 --format webp --animate --frame-duration 600

# ClearLogo
python clearlogo.py "Chef At Home"
python clearlogo.py "Chef At Home (2020)" --filter-years --font bebas
python clearlogo.py "Actor Name: The Movie" --filter-actors "Actor Name" --color black
```

All scripts support `--help` and `--verbose` / `-v`.

---

## Architecture and Conventions

### General

- **Python 3.11+** with type hints throughout.
- Each script is self-contained and runnable independently — no shared state between tools.
- Every script has a `main()` function that is the `if __name__ == "__main__"` entry point.
- CLI is built with `argparse` using argument groups for logical organisation.
- Fatal errors print to `sys.stderr` and call `sys.exit(1)`.
- Non-fatal issues print a `Warning:` prefixed message to `sys.stderr` and continue.
- `--verbose` / `-v` is present on all three tools for detailed progress output.

### NFO Converter (`stash_to_nfo.py` + supporting modules)

- `StashParser` (in `parsers.py`) auto-detects whether JSON data is a scene, performer, or gallery by inspecting field presence.
- `StashToNfoConverter` (in `converters.py`) maps StashApp field names to NFO XML tag names. Rating scale is converted 1–5 → 0–10. Base64 image extraction decodes embedded images and saves them alongside the NFO.
- `NfoGenerator` (in `nfo_generator.py`) builds the XML tree using `xml.etree.ElementTree` and optionally pretty-prints via `xml.dom.minidom`.
- `StashApiClient` (in `stash_api.py`) wraps `stashapi.stashapp.StashInterface`. Use `call_GQL()` for queries not covered by the library's helper methods.
- NFO format targets **Kodi and Jellyfin**. Do not deviate from their expected XML tag names without checking compatibility against both.

### Video Gallery (`video_gallery.py`)

- `VideoGalleryGenerator` class owns all frame extraction logic. `generate()` saves individual stills; `animate()` produces a single animated file.
- Frame extraction uses OpenCV (`cv2`); image saving and animated assembly use Pillow.
- GIF output converts frames to palette mode (256 colours) before saving — this is required for correct GIF encoding.
- Animated WebP is preferred over GIF: better quality and significantly smaller file sizes.
- The `--size` argument accepts either `WxH` (e.g. `1280x720`) or a percentage (e.g. `50%`). Parsed by `parse_size()`.
- The `--start-time` / `--end-time` arguments accept `SS`, `MM:SS`, or `HH:MM:SS`. Parsed by `parse_time()`.

### ClearLogo (`clearlogo.py`)

- Clearlogo standard canvas: **800 × 310 px**, transparent background, PNG output.
- Three available fonts: `bebas` (Bebas Neue), `anton` (Anton), `montserrat` (Montserrat ExtraBold). Font files are cached in `fonts/`.
- `_best_wrap()` finds the largest font size that fits the work area (canvas minus padding), trying both single-line and two-line splits.
- `clean_title()` strips years/dates and actor names. After actor removal it iteratively strips orphaned connector words ("and", "&", "starring", etc.) and punctuation.
- Font auto-download: `clearlogo.py` will download missing font TTFs from Google Fonts API at runtime if `fonts/<name>.ttf` is not present.

---

## Code Style

- **No comments** unless they explain a non-obvious decision. Code should be self-documenting through clear naming.
- Docstrings use Google style (Args / Returns blocks).
- `clamp(value, lo, hi)` is a local utility used in `video_gallery.py` — do not replace it with `max(lo, min(hi, value))` inline; keep it readable.
- Prefer explicit error messages that name the problematic value (e.g. `f"Unknown font '{font_key}'. Choose from: ..."`) over generic ones.
- All file output paths are `pathlib.Path` objects internally, even if the user supplies a string.

---

## What Not to Change

- **NFO XML tag names and structure** — must remain compatible with Kodi and Jellyfin.
- **`fonts/` directory contents** — auto-managed; do not rename or convert font files.
- **`example_output.nfo`** — real output used as a reference sample; update it if the NFO format changes.
- **`stash_api.py` GQL queries** — these are validated against the StashApp schema; changes need to be tested against a live instance.

---

## Testing

There is no automated test suite. Validate changes manually:

```bash
# NFO converter — use the bundled test asset
python stash_to_nfo.py attached_assets/Chef-At-Home.*.json --pretty -v

# Video gallery — needs a real video file
python video_gallery.py /path/to/video.mp4 --count 5 --format jpg -v
python video_gallery.py /path/to/video.mp4 --count 5 --format webp --animate -v

# ClearLogo — no external files needed
python clearlogo.py "Test Title (2020)" --filter-years --font bebas -v
python clearlogo.py "Actor One and Actor Two: The Movie" --filter-actors "Actor One,Actor Two" -v
```

---

## StashApp API Notes

- StashApp runs locally, typically at `http://localhost:9999`.
- Authentication: API key (preferred) or username + password.
- The `stashapp-tools` library provides `StashInterface`. For queries the library does not cover (e.g. `findGallery`), use `self.stash.call_GQL(query, variables)`.
- StashApp IDs are integers in Python but must be passed as strings to the GraphQL API (`str(id)`).
