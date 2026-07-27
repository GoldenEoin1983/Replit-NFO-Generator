#!/usr/bin/env python3
"""
ClearLogo Generator
Creates a transparent-background text logo (clearlogo) from a media title.
Supports three fonts, white or black text, and optional title cleaning
to strip years/dates and performer names.
"""

import argparse
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Font registry
# ---------------------------------------------------------------------------
FONTS = {
    "bebas": {
        "file": "fonts/bebas.ttf",
        "label": "Bebas Neue — bold condensed, the classic clearlogo choice",
    },
    "anton": {
        "file": "fonts/anton.ttf",
        "label": "Anton — punchy condensed, slightly wider than Bebas Neue",
    },
    "montserrat": {
        "file": "fonts/montserrat.ttf",
        "label": "Montserrat ExtraBold — clean modern, streaming-platform style",
    },
}

# Standard clearlogo canvas (fanart.tv / Kodi / Jellyfin community standard)
DEFAULT_WIDTH  = 800
DEFAULT_HEIGHT = 310
DEFAULT_PAD    = 30    # px of breathing room on each side


# ---------------------------------------------------------------------------
# Title cleaning
# ---------------------------------------------------------------------------
_YEAR_PATTERNS = [
    re.compile(r'\s*[\(\[]\s*(19|20)\d{2}\s*[\)\]]'),  # (2020) or [2020]
    re.compile(r'\s*[-–,]\s*(19|20)\d{2}\b'),           # - 2020 or , 2020
    re.compile(r'\b(19|20)\d{2}\b'),                    # bare year
]

# Connector words that can be left stranded when actor names are removed
_CONNECTOR_RE = re.compile(
    r'(?:^|\s)(?:and|or|&|feat\.?|ft\.?|vs\.?|with|starring|presents?|'
    r'introduced by|presented by)(?:\s|$)',
    re.IGNORECASE,
)

# Orphaned punctuation patterns left after removals
_ORPHAN_PUNCT_RE = re.compile(r'^\s*[-–,:|]+\s*|\s*[-–,:|]+\s*$')
_DOUBLE_PUNCT_RE = re.compile(r'[-–,:|]\s*[-–,:|]+')


def _strip_edges(s: str) -> str:
    """Iteratively strip leading/trailing punctuation and stranded connectors."""
    prev = None
    while prev != s:
        prev = s
        s = _ORPHAN_PUNCT_RE.sub("", s)
        s = re.sub(r'\s+', ' ', s).strip()
        # Remove connector-only leading/trailing words
        s = re.sub(
            r'^(?:and|or|&|feat\.?|ft\.?|vs\.?|with|starring)\s+',
            '', s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r'\s+(?:and|or|&|feat\.?|ft\.?|vs\.?|with|starring)$',
            '', s, flags=re.IGNORECASE,
        )
        s = s.strip(" -–,:|")
    return s


def clean_title(title: str, filter_years: bool = False,
                filter_actors: list = None) -> str:
    """
    Return a cleaned version of the title.

    Args:
        title:          Raw title string.
        filter_years:   If True, strip year/date patterns.
        filter_actors:  List of actor/performer name strings to remove.
    """
    result = title

    if filter_years:
        for pattern in _YEAR_PATTERNS:
            result = pattern.sub("", result)

    if filter_actors:
        for name in filter_actors:
            name = name.strip()
            if name:
                result = re.sub(re.escape(name), "", result, flags=re.IGNORECASE)
        # Clean up connector words and punctuation left behind by name removals
        result = _DOUBLE_PUNCT_RE.sub(":", result)
        result = _strip_edges(result)

    # Final whitespace normalisation
    result = re.sub(r'\s+', ' ', result).strip()
    result = result.strip(" -–,:|")
    return result


# ---------------------------------------------------------------------------
# Font-size fitting
# ---------------------------------------------------------------------------
def _text_bbox(draw, text: str, font):
    """Return (width, height) of the rendered text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _best_wrap(draw, text: str, font_path: str,
               max_w: int, max_h: int,
               max_size: int = 400, min_size: int = 12):
    """
    Find the largest font size and the best line-break that fits inside
    (max_w, max_h).  Returns (ImageFont, lines_list, font_size).
    """
    from PIL import ImageFont

    words = text.split()

    def try_layout(size, lines):
        font = ImageFont.truetype(font_path, size)
        dummy_draw = _dummy_draw()
        widths  = [_text_bbox(dummy_draw, l, font)[0] for l in lines]
        heights = [_text_bbox(dummy_draw, l, font)[1] for l in lines]
        gap = max(4, size // 10)
        total_w = max(widths)
        total_h = sum(heights) + gap * (len(lines) - 1)
        return font, total_w <= max_w and total_h <= max_h, total_w, total_h

    def _dummy_draw():
        from PIL import Image, ImageDraw
        return ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    # Candidate splits: 1 line, 2 lines at each word boundary
    def candidate_splits():
        yield [text]
        if len(words) > 1:
            for i in range(1, len(words)):
                yield [" ".join(words[:i]), " ".join(words[i:])]

    best_font, best_lines, best_size = None, [text], min_size

    for size in range(max_size, min_size - 1, -2):
        for lines in candidate_splits():
            font, fits, _, _ = try_layout(size, lines)
            if fits and size > best_size:
                best_font  = font
                best_lines = lines
                best_size  = size
        if best_size == size:
            break          # found the largest fitting size for some layout

    if best_font is None:
        best_font = ImageFont.truetype(font_path, min_size)

    return best_font, best_lines, best_size


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------
def generate_clearlogo(title: str, font_key: str = "bebas",
                       color: str = "white",
                       width: int = DEFAULT_WIDTH,
                       height: int = DEFAULT_HEIGHT,
                       padding: int = DEFAULT_PAD,
                       output_path: str = None,
                       verbose: bool = False) -> str:
    """
    Render a clearlogo PNG with transparent background.

    Args:
        title:        The text to render.
        font_key:     One of 'bebas', 'anton', 'montserrat'.
        color:        'white' or 'black'.
        width:        Canvas width in pixels.
        height:       Canvas height in pixels.
        padding:      Pixel margin on each side.
        output_path:  Where to save the PNG.  Defaults to '<title>-clearlogo.png'.
        verbose:      Print progress info.

    Returns:
        Path to the saved PNG file.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow is required. Run: pip install Pillow")

    if font_key not in FONTS:
        raise ValueError(f"Unknown font '{font_key}'. Choose from: {', '.join(FONTS)}")

    font_path = Path(FONTS[font_key]["file"])
    if not font_path.exists():
        raise FileNotFoundError(
            f"Font file not found: {font_path}\n"
            f"Run the script once to auto-download fonts, or check that "
            f"'{font_path}' is present."
        )

    if color not in ("white", "black"):
        raise ValueError("color must be 'white' or 'black'")

    fill = (255, 255, 255, 255) if color == "white" else (0, 0, 0, 255)

    # Work area inside the padding
    work_w = width  - padding * 2
    work_h = height - padding * 2

    if verbose:
        print(f"Canvas:    {width} × {height} px")
        print(f"Work area: {work_w} × {work_h} px")
        print(f"Font:      {FONTS[font_key]['label']}")
        print(f"Colour:    {color}")
        print(f"Title:     '{title}'")

    # Fit text
    font, lines, size = _best_wrap(
        None, title, str(font_path),
        work_w, work_h,
        max_size=min(work_h, 400),
    )
    if verbose:
        print(f"Font size: {size} pt  |  Lines: {lines}")

    # Create transparent canvas
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Measure total block
    gap = max(4, size // 10)
    line_dims = [_text_bbox(draw, l, font) for l in lines]
    block_h = sum(h for _, h in line_dims) + gap * (len(lines) - 1)
    y = (height - block_h) // 2

    for line, (lw, lh) in zip(lines, line_dims):
        x = (width - lw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += lh + gap

    # Save
    if output_path is None:
        safe = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        output_path = f"{safe}-clearlogo.png"

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")

    if verbose:
        print(f"Saved:     {out}  ({out.stat().st_size // 1024} KB)")

    return str(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate a transparent clearlogo PNG from a media title.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Fonts available:
  bebas       — {FONTS['bebas']['label']}
  anton       — {FONTS['anton']['label']}
  montserrat  — {FONTS['montserrat']['label']}

Examples:
  # Basic usage
  %(prog)s "Chef At Home"

  # Strip the year out of the title
  %(prog)s "Chef At Home (2020)" --filter-years

  # Strip actor names from the title
  %(prog)s "William Seed and Ashton Summers: Chef At Home" --filter-actors "William Seed,Ashton Summers"

  # Black text, Anton font, saved to a specific file
  %(prog)s "Chef At Home" --color black --font anton --output ./artwork/clearlogo.png

  # All options
  %(prog)s "Chef At Home (2020)" --filter-years --font montserrat --color white --size 1000x400 --padding 40 -v
        """
    )

    parser.add_argument(
        "title",
        help="The title text to render as a clearlogo"
    )

    parser.add_argument(
        "--font",
        choices=list(FONTS.keys()),
        default="bebas",
        help="Font to use (default: bebas)"
    )

    parser.add_argument(
        "--color",
        choices=["white", "black"],
        default="white",
        help="Text colour on a transparent background (default: white)"
    )

    parser.add_argument(
        "--size",
        default=f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
        metavar="WxH",
        help=f"Canvas size in pixels (default: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT})"
    )

    parser.add_argument(
        "--padding",
        type=int,
        default=DEFAULT_PAD,
        metavar="PX",
        help=f"Margin in pixels on each side (default: {DEFAULT_PAD})"
    )

    parser.add_argument(
        "--filter-years",
        action="store_true",
        help="Strip year/date patterns (e.g. '(2020)', '- 2020') from the title"
    )

    parser.add_argument(
        "--filter-actors",
        metavar="NAMES",
        help="Comma-separated actor/performer names to remove from the title"
    )

    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Output PNG path (default: <title>-clearlogo.png in current directory)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress information"
    )

    args = parser.parse_args()

    # Parse canvas size
    size_parts = args.size.lower().split("x")
    if len(size_parts) != 2:
        parser.error("--size must be in WxH format, e.g. 800x310")
    try:
        canvas_w, canvas_h = int(size_parts[0]), int(size_parts[1])
    except ValueError:
        parser.error("--size dimensions must be integers, e.g. 800x310")
    if canvas_w <= 0 or canvas_h <= 0:
        parser.error("--size dimensions must be positive")

    # Parse actor list
    actors = []
    if args.filter_actors:
        actors = [a.strip() for a in args.filter_actors.split(",") if a.strip()]

    # Clean the title
    title = clean_title(args.title, filter_years=args.filter_years, filter_actors=actors)
    if not title:
        print("Error: title is empty after filtering. Nothing to render.", file=sys.stderr)
        sys.exit(1)

    if args.verbose and title != args.title:
        print(f"Original title: '{args.title}'")
        print(f"Cleaned title:  '{title}'")

    try:
        out = generate_clearlogo(
            title=title,
            font_key=args.font,
            color=args.color,
            width=canvas_w,
            height=canvas_h,
            padding=args.padding,
            output_path=args.output,
            verbose=args.verbose,
        )
        print(f"Clearlogo saved: {out}")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
