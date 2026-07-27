# StashApp to NFO Converter

A command-line tool that converts StashApp JSON metadata files into Kodi/Jellyfin compatible NFO files, extracts images, and generates image galleries or animated previews from video files.

## Features

- **Multiple Data Types**: Supports StashApp scenes, performers, and galleries
- **Auto-Detection**: Automatically detects the type of StashApp data
- **Kodi/Jellyfin Compatible**: Generates properly formatted NFO files with UTF-8 encoding
- **Field Mapping**: Maps StashApp fields to appropriate NFO XML tags
- **Base64 Image Extraction**: Decodes and saves embedded images from StashApp JSON
- **Direct API Integration**: Connects directly to your local StashApp instance
- **Video Gallery Generator**: Extracts still frames or creates animated GIF/WebP previews from video files
- **Error Handling**: Comprehensive error handling for invalid files and operations

## Installation

Requires Python 3.6+. Install dependencies with:

```bash
pip install stashapp-tools opencv-python-headless Pillow
```

---

## Project Config File — `stash-tools.toml`

Once you've made a few galleries, GIFs, or clearlogos the way you like, you can save those settings permanently instead of retyping them. All three tools automatically read a file called **`stash-tools.toml`** in the project folder.

**Priority order:** command line > config file > built-in defaults. Anything you type on the command line always wins.

The included `stash-tools.toml` documents every available setting, grouped into clearly separated sections:

| Section | Used by | Controls |
|---|---|---|
| `[output]` | `video_gallery.py` | Output folder and filename prefix |
| `[gallery]` | `video_gallery.py` | Frame count/interval, format, quality, size, start/end range |
| `[animation]` | `video_gallery.py --animate` | Animated format, frame duration, looping |
| `[clearlogo]` | `clearlogo.py` | Font, colour, canvas size, padding, title filtering |
| `[nfo]` | `stash_to_nfo.py` | Pretty-printing, image extraction, overwrite, encoding |
| `[stash_api]` | `stash_to_nfo.py` | StashApp server host, port, scheme, API key |

Every setting ships commented out (a `#` in front). Remove the `#` to activate one:

```toml
[gallery]
count = 24
format = "webp"
size = "50%"

[clearlogo]
font = "anton"
filter_years = true
```

With that saved, `python video_gallery.py movie.mp4` needs no extra options — and `python video_gallery.py movie.mp4 --count 10` still overrides the saved count for that one run.

You can also keep several configs (say, one per show) and pick one with `--config`:

```bash
python video_gallery.py movie.mp4 --config myshow.toml
```

### Checking Your Config File

Two helper scripts keep the config system healthy — both print what's wrong and exit with code 1 on failure, so they're safe to use in scripts too.

**1. Validate your filled-in config** — run this after editing `stash-tools.toml` to catch typos, wrong value types, and out-of-range values before they cause confusing errors mid-run:

```bash
# Check the default stash-tools.toml
make validate-config
# ...or any other config file
make validate-config FILE=myshow.toml
# ...or call the script directly
python scripts/validate_config.py myshow.toml
```

Example output for a broken file:

```
myshow.toml: 3 problem(s) found:

  - [gallery] quality: should be a whole number, but got '85'
  - [clearlogo] font: 'arial' is not one of: "bebas", "anton", "montserrat"
  - [gallery]: both 'count' and 'interval' are set - pick one (if you keep both, count wins)
```

**2. Check config coverage** — mainly for anyone changing the code: verifies that every command-line option either has a matching config option or is deliberately command-line only, and that the sample `stash-tools.toml` documents every setting. Run it after adding, renaming, or removing an option:

```bash
make check-config
# ...or directly
python scripts/check_config_coverage.py
```

---

## NFO Converter — `stash_to_nfo.py`

Converts StashApp metadata to Kodi/Jellyfin NFO files. The output follows the Kodi movie NFO layout [[K4]](#references), which Jellyfin also reads [[J3]](#references).

### Basic Usage

```bash
# Convert a scene JSON file
python stash_to_nfo.py scene.json

# Specify output file
python stash_to_nfo.py scene.json output.nfo

# Convert performer data
python stash_to_nfo.py --type performer performer.json

# Convert gallery data
python stash_to_nfo.py --type gallery gallery.json

# Extract embedded images alongside the NFO
python stash_to_nfo.py scene.json --extract-images --pretty

# Query your StashApp directly by ID
python stash_to_nfo.py --stash-id 42 --stash-api-key YOUR_KEY

# Search your StashApp and convert the first result
python stash_to_nfo.py --search "movie title" --extract-images
```

### Options

| Option | Description |
|---|---|
| `--type` | Force type: `scene`, `performer`, `gallery`, or `auto` (default) |
| `--pretty` | Format the XML with indentation |
| `--extract-images` | Decode and save any base64 images found in the JSON, plus actor pictures (see below) |
| `--genre-tags` | Comma-separated tag names or ID numbers to write as `<genre>` instead of `<tag>` (see below) |
| `--genre-parent-tag` | A parent tag (name or ID) whose child tags all count as genres |
| `--overwrite` | Overwrite existing files without prompting |
| `--verbose` / `-v` | Show detailed output |
| `--stash-id N` | Fetch data directly from StashApp by ID |
| `--search TEXT` | Search StashApp and convert the first result |
| `--stash-host` | StashApp hostname (default: `localhost`) |
| `--stash-port` | StashApp port (default: `9999`) |
| `--stash-api-key` | API key for StashApp authentication |

### Choosing Which Tags Become Genres

By default every StashApp tag is written as **both** `<genre>` and `<tag>` in the NFO, so it shows up in either filter menu of your media center. If you'd rather keep genres tidy, you can name which tags count as genres — everything else then stays a plain `<tag>`.

Two ways to do it (they can be combined):

- **List them directly** — tag names and/or StashApp tag ID numbers, comma-separated. Names are matched ignoring upper/lower case.

  ```bash
  python stash_to_nfo.py scene.json --genre-tags "Action,Comedy,42"
  ```

- **Name one parent tag** — if your genre tags in Stash are all filed under a parent tag (say, one called `Genres`), just name that parent (or its ID) and every child tag counts as a genre. The children are looked up in your StashApp, so this needs the server connection settings — in file mode the tool connects briefly just for that lookup, and if it can't, it warns you and still writes the NFO.

  ```bash
  python stash_to_nfo.py --stash-id 42 --genre-parent-tag "Genres"
  ```

Both settings can also be saved in `stash-tools.toml` under `[nfo]` as `genre_tags` and `genre_parent_tag`, so you never have to type them again.

### Actor Profile Pictures (Kodi `.actors` folder)

When you run with `--extract-images` on a scene or gallery, performer profile pictures from Stash are also saved into a **`.actors`** folder next to the NFO — exactly where Kodi looks for local actor portraits [[K6]](#references). Files follow Kodi's naming rule: spaces in the performer's name become underscores, e.g. `William_Seed.jpg`.

Pictures come from two places:

- **JSON exports** — a base64 `image` embedded in the performer entry (JSON exports that only list performer *names* have no pictures, so nothing is saved).
- **API mode** (`--stash-id` / `--search`) — the performer's `image_path` URL, downloaded straight from your running StashApp (your `--stash-api-key` is used automatically if given). For safety, downloads only happen in API mode and only from the Stash host you connected to — a JSON file can never make the tool contact other servers.

```bash
# NFO + poster/fanart + actor portraits in .actors/
python stash_to_nfo.py --stash-id 42 --extract-images --stash-api-key YOURKEY
```

Note: Jellyfin doesn't read the `.actors` folder; it manages actor images through its own metadata system.

---

## Video Gallery Generator — `video_gallery.py`

Extracts frames from a video file as individual still images, or combines them into an **animated GIF** or **animated WebP** preview.

### Still Image Examples

```bash
# 24 JPG frames spread evenly across the whole video
python video_gallery.py movie.mp4 --count 24

# One frame every 30 seconds, saved as PNG
python video_gallery.py movie.mp4 --interval 30 --format png

# 12 WebP frames from the middle section (skip first/last 20%)
python video_gallery.py movie.mp4 --count 12 --start 20 --end 80 --format webp

# 10 frames from a specific time window
python video_gallery.py movie.mp4 --count 10 --start-time 0:05:00 --end-time 0:45:00

# Half-size JPGs saved to a separate folder
python video_gallery.py movie.mp4 --interval 60 --size 50% --output ./gallery
```

### Animated GIF / WebP Examples

```bash
# Animated GIF — 16 frames, each shown for 400ms
python video_gallery.py movie.mp4 --count 16 --format gif --animate --frame-duration 400

# Animated WebP — one frame every 30s, 600ms per frame, half-size
python video_gallery.py movie.mp4 --interval 30 --format webp --animate --frame-duration 600 --size 50%

# Animated WebP skipping intro and credits, looping 3 times
python video_gallery.py movie.mp4 --count 12 --format webp --animate --start 5 --end 95 --loop 3

# Animated GIF from a specific time range
python video_gallery.py movie.mp4 --count 10 --format gif --animate --start-time 5:00 --end-time 20:00
```

### All Options

| Option | Description |
|---|---|
| `--count N` / `-n N` | Extract exactly N frames, evenly spaced |
| `--interval SECS` / `-i SECS` | One frame every N seconds |
| `--start PERCENT` | Start at this % of the video (default: 0) |
| `--end PERCENT` | End at this % of the video (default: 100) |
| `--start-time TIME` | Start at a timestamp: `90`, `1:30`, or `0:01:30` |
| `--end-time TIME` | End at a timestamp |
| `--format FORMAT` | `jpg`, `png`, `webp` for stills; `gif` or `webp` for animated |
| `--quality 1-100` | Quality for jpg/webp (default: 85, ignored for png/gif) |
| `--size SIZE` | Resize: `1920x1080` or `50%` |
| `--animate` | Combine frames into one animated file (requires `gif` or `webp` format) |
| `--frame-duration MS` | How long each frame shows in the animation, in milliseconds (default: 500) |
| `--loop N` | Times to loop animation; `0` = loop forever (default: 0) |
| `--output DIR` | Output directory (default: same folder as the video) |
| `--prefix NAME` | Filename prefix (default: video filename) |
| `--verbose` / `-v` | Show detailed progress |

---

## Animated Images — Kodi & Jellyfin Guide

> Sources for the statements in this section are listed under [References](#references) below. If a Kodi or Jellyfin update changes any of this behaviour, check those links first.

### Jellyfin

Jellyfin has **full native support** for both animated GIF and animated WebP across all official clients (Web, Android, Desktop). Animated images work as posters, backdrops, and thumbnails with no extra configuration needed. [[J1]](#references)

**Recommended for Jellyfin:** Animated WebP — better quality and much smaller file sizes than GIF.

### Kodi

Kodi supports animated GIF and animated WebP, but behaviour depends on which **skin** you are using.

- **Animated GIF**: Supported in the core engine, but many skins (including the default *Estuary*) only display the first frame as a static image in list views. Animated playback is more reliable in full-screen fanart views. [[K1]](#references)
- **Animated WebP**: Supported from **Kodi 19 (Matrix)** onwards. Requires skin support for the animation to play. Kodi 20 (Nexus) and later have the most reliable WebP handling. [[K2]](#references)
- **Older Kodi (pre-19)**: WebP is not supported. Use GIF or static images instead. [[K2]](#references)

**Recommended for Kodi:** Keep animated images as supplementary fanart rather than primary posters, to ensure compatibility across skins and devices.

### Format Comparison

| | Animated GIF | Animated WebP |
|---|---|---|
| **Jellyfin support** | Full | Full |
| **Kodi 20+ support** | Full (skin-dependent) | Full (skin-dependent) |
| **Kodi 19 support** | Full (skin-dependent) | Partial |
| **Kodi pre-19** | Full (skin-dependent) | Not supported |
| **Color depth** | 256 colours per frame | Full colour (24-bit) |
| **File size** | Large | Much smaller |
| **Transparency** | Limited (1-bit) | Full alpha |

### Size Recommendations

These sizes match the artwork standards used by the Kodi and Jellyfin communities (originating from the fanart.tv / TheMovieDB guidelines): [[K3]](#references) [[J2]](#references)

| Artwork type | Recommended size | Aspect ratio | Notes |
|---|---|---|---|
| **Poster** | 1000 × 1500 px | 2:3 | Main library image |
| **Fanart / Backdrop** | 1920 × 1080 px | 16:9 | Background image |
| **Thumbnail** | 1280 × 720 px | 16:9 | Scene/episode preview |

For animated images, **smaller sizes are strongly recommended** to keep file sizes manageable. A 1920×1080 animated GIF with 20 frames can easily exceed 50 MB, which will slow down your media centre UI — especially on low-power devices like a Raspberry Pi.

**Practical size guidance for animations:**

| Use case | Suggested `--size` |
|---|---|
| Fast/responsive UI | `640x360` or `50%` |
| Balanced quality | `1280x720` or `75%` |
| High quality (fast machine) | `1920x1080` |

### Number of Frames

The number of frames directly affects file size and how smooth the animation looks.

| Frame count | Result |
|---|---|
| **6–10** | Very small file; works well as a quick slideshow preview |
| **12–20** | Good balance — recommended for most use cases |
| **20–30** | Smooth animation; larger file, best used with WebP |
| **30+** | Very large file; may cause UI lag on slower hardware |

**Tip:** Animated WebP can handle more frames at a reasonable file size compared to GIF.

### Frame Duration

`--frame-duration` controls how long each frame is displayed, in **milliseconds**.

| Duration | Effect |
|---|---|
| `100–200 ms` | Fast motion preview (~5–10 fps) |
| `300–500 ms` | Natural-feeling slideshow — **recommended default** |
| `600–1000 ms` | Slow slideshow, good for reading titles or detail |
| `1000+ ms` | Very slow; one frame per second or slower |

**Example:** `--count 12 --frame-duration 400` gives a 4.8-second animation that loops continuously.

### Performance Notes

- **Animated WebP is always preferable to GIF** when Jellyfin or a modern Kodi version is your target. It produces dramatically smaller files at equal or better quality.
- Large animated files can make your media centre UI feel sluggish, particularly on embedded or older devices.
- If you experience slowdowns, reduce `--size` first, then reduce `--count`.
- For Kodi, consider placing animated images in the `extrafanart` folder as supplementary artwork rather than replacing the primary poster, so the library still loads quickly.

---

## References

Fact-check sources for the Kodi/Jellyfin statements in this document. If a server update changes behaviour, these are the pages to re-check.

### Kodi sources

| Ref | Topic | Link |
|---|---|---|
| K1 | Artwork types & how skins display them | https://kodi.wiki/view/Artwork_types |
| K2 | Kodi 19 (Matrix) changelog — image handling / WebP era | https://kodi.wiki/view/Kodi_v19_(Matrix)_changelog |
| K3 | Artwork size guidelines | https://kodi.wiki/view/Artwork_types#Artwork_size |
| K4 | Movie NFO file specification | https://kodi.wiki/view/NFO_files/Movies |
| K5 | NFO files overview (all types) | https://kodi.wiki/view/NFO_files |
| K6 | Actor artwork — the `.actors` folder convention | https://kodi.wiki/view/Artwork_types#actor |

### Jellyfin sources

| Ref | Topic | Link |
|---|---|---|
| J1 | Image/artwork handling in Jellyfin | https://jellyfin.org/docs/general/server/media/movies/ |
| J2 | Jellyfin metadata & image documentation | https://jellyfin.org/docs/general/server/metadata/ |
| J3 | NFO metadata support in Jellyfin | https://jellyfin.org/docs/general/server/metadata/nfo/ |

### Related standards

| Topic | Link |
|---|---|
| fanart.tv artwork guidelines (community sizing standards) | https://fanart.tv/artwork-guidelines/ |
| StashApp documentation | https://docs.stashapp.cc/ |
| Animated WebP format specification | https://developers.google.com/speed/webp/docs/riff_container |
