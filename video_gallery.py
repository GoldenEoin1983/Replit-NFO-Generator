#!/usr/bin/env python3
"""
Video Gallery Generator

Extracts frames from a video file and saves them as individual images
or combines them into an animated GIF or animated WebP preview.

HOW IT WORKS
------------
1. OpenCV (cv2) opens the video and jumps to specific timestamps
2. Each grabbed frame is converted to a Pillow image (optionally resized)
3. Frames are saved as separate files (generate) or stitched into one
   animated file (animate)

You choose WHICH frames with either:
- --count N     -> N frames spread evenly across the chosen range, or
- --interval S  -> one frame every S seconds

and WHERE to sample with percentages (--start/--end) or exact
timestamps (--start-time/--end-time).
"""

import argparse
import sys
from pathlib import Path
from typing import ClassVar


def parse_size(size_str: str):
    """
    Parse size string into (width, height) tuple or percentage float.

    Accepts:
        - "1920x1080" -> (1920, 1080)
        - "50%"       -> 0.5
    """
    if "%" in size_str:
        percent = float(size_str.replace("%", "").strip()) / 100.0
        if not 0 < percent <= 1:
            raise argparse.ArgumentTypeError("Percentage must be between 1% and 100%")
        return percent
    elif "x" in size_str.lower():
        parts = size_str.lower().split("x")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("Size must be in format WxH, e.g. 1920x1080")
        try:
            w, h = int(parts[0]), int(parts[1])
        except ValueError:
            raise argparse.ArgumentTypeError("Size dimensions must be integers, e.g. 1920x1080")
        if w <= 0 or h <= 0:
            raise argparse.ArgumentTypeError("Size dimensions must be positive")
        return (w, h)
    else:
        raise argparse.ArgumentTypeError(
            "Size must be WxH (e.g. 1920x1080) or a percentage (e.g. 50%)"
        )


def parse_time(time_str: str) -> float:
    """
    Parse a time string into seconds.

    Accepts:
        - "90"      -> 90.0
        - "1:30"    -> 90.0
        - "0:01:30" -> 90.0
    """
    parts = time_str.strip().split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid time format '{time_str}'. Use seconds (90), MM:SS (1:30), or HH:MM:SS (0:01:30)"
        )


def clamp(value, lo, hi):
    """Keep a value within the range [lo, hi]."""
    return max(lo, min(hi, value))


class VideoGalleryGenerator:
    """Extracts frames from a video and saves them as images or animations."""

    STILL_FORMATS: ClassVar[dict[str, tuple[str, str]]] = {
        "jpg":  (".jpg",  "JPEG"),
        "jpeg": (".jpg",  "JPEG"),
        "png":  (".png",  "PNG"),
        "webp": (".webp", "WEBP"),
    }

    ANIM_FORMATS: ClassVar[dict[str, tuple[str, str]]] = {
        "gif":  (".gif",  "GIF"),
        "webp": (".webp", "WEBP"),
    }

    def __init__(self, video_path: str, output_dir: str | None = None, prefix: str | None = None,
                 fmt: str = "jpg", quality: int = 85, size=None, verbose: bool = False):
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.output_dir = Path(output_dir) if output_dir else self.video_path.parent
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.prefix = prefix or self.video_path.stem
        self.fmt = fmt.lower()
        self.quality = clamp(quality, 1, 100)
        self.size = size
        self.verbose = verbose

    def _log(self, msg: str):
        """Print progress messages, but only when --verbose is on."""
        if self.verbose:
            print(msg)

    def _open_video(self):
        """Open the video with OpenCV; returns (capture object, cv2 module)."""
        try:
            import cv2
        except ImportError:
            raise RuntimeError(
                "opencv-python-headless is required. Run: pip install opencv-python-headless"
            )
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self.video_path}")
        return cap, cv2

    def _build_timestamps(self, cap, cv2,
                          count, interval,
                          start_percent, end_percent,
                          start_time, end_time):
        """
        Work out the exact timestamps (in seconds) to grab frames at.

        Exact times (--start-time/--end-time) win over percentages;
        then either --count spreads frames evenly across the range, or
        --interval steps through it in fixed jumps.
        """
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        if duration <= 0:
            raise RuntimeError("Could not determine video duration")

        self._log(f"Video: {self.video_path.name}")
        self._log(f"Duration: {duration:.1f}s  |  FPS: {fps:.2f}  |  Frames: {total_frames}")

        t_start = clamp(start_time if start_time is not None else duration * (start_percent / 100.0),
                        0, duration)
        t_end   = clamp(end_time   if end_time   is not None else duration * (end_percent   / 100.0),
                        0, duration)

        if t_start >= t_end:
            raise ValueError(
                f"Start time ({t_start:.1f}s) must be less than end time ({t_end:.1f}s)"
            )

        span = t_end - t_start
        self._log(f"Extracting from {t_start:.1f}s to {t_end:.1f}s  (span: {span:.1f}s)")

        if count is not None and count > 0:
            timestamps = ([t_start + span / 2] if count == 1
                          else [t_start + i * (span / (count - 1)) for i in range(count)])
        elif interval is not None and interval > 0:
            timestamps, t = [], t_start
            while t <= t_end:
                timestamps.append(t)
                t += interval
        else:
            raise ValueError("Either --count or --interval must be provided")

        self._log(f"Targeting {len(timestamps)} frame(s)")
        return fps, total_frames, timestamps

    def _read_frame(self, cap, cv2, ts, fps, total_frames, idx):
        """
        Jump to timestamp `ts`, grab that frame, and return it as a
        Pillow image (resized if --size was given). Returns None if the
        frame couldn't be read.
        """
        from PIL import Image
        frame_num = clamp(int(ts * fps), 0, total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            self._log(f"  [{idx:04d}] Warning: could not read frame at {ts:.1f}s, skipping")
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        if self.size is not None:
            orig_w, orig_h = img.size
            new_size = self.size if isinstance(self.size, tuple) else (
                int(orig_w * self.size), int(orig_h * self.size)
            )
            img = img.resize(new_size, Image.LANCZOS)
            self._log(f"  Resized {orig_w}x{orig_h} -> {new_size[0]}x{new_size[1]}")
        return img

    # ------------------------------------------------------------------
    # Public: still images
    # ------------------------------------------------------------------
    def generate(self, count: int | None = None, interval: float | None = None,
                 start_percent: float = 0.0, end_percent: float = 100.0,
                 start_time: float | None = None, end_time: float | None = None) -> list:
        """
        Extract frames and save as individual image files.

        Returns:
            List of file paths that were saved.
        """
        if self.fmt not in self.STILL_FORMATS:
            raise ValueError(
                f"Format '{self.fmt}' is not supported for still images. "
                f"Choose from: {', '.join(self.STILL_FORMATS)}"
            )

        try:
            from PIL import Image  # noqa: F401 (imported inside for cleaner error)
        except ImportError:
            raise RuntimeError("Pillow is required. Run: pip install Pillow")

        cap, cv2 = self._open_video()
        try:
            fps, total_frames, timestamps = self._build_timestamps(
                cap, cv2, count, interval,
                start_percent, end_percent, start_time, end_time
            )

            ext, pil_format = self.STILL_FORMATS[self.fmt]
            save_kwargs = {}
            if pil_format == "JPEG":
                save_kwargs = {"quality": self.quality, "optimize": True}
            elif pil_format == "WEBP":
                save_kwargs = {"quality": self.quality, "method": 4}

            saved_files = []
            for idx, ts in enumerate(timestamps, start=1):
                img = self._read_frame(cap, cv2, ts, fps, total_frames, idx)
                if img is None:
                    continue
                filename = f"{self.prefix}_{idx:04d}{ext}"
                out_path = self.output_dir / filename
                img.save(out_path, format=pil_format, **save_kwargs)
                saved_files.append(str(out_path))
                self._log(f"  [{idx:04d}] t={ts:.1f}s -> {filename}")
        finally:
            cap.release()

        return saved_files

    # ------------------------------------------------------------------
    # Public: animated GIF or animated WebP
    # ------------------------------------------------------------------
    def animate(self, count: int | None = None, interval: float | None = None,
                start_percent: float = 0.0, end_percent: float = 100.0,
                start_time: float | None = None, end_time: float | None = None,
                frame_duration: int = 500, loop: int = 0) -> str:
        """
        Extract frames and combine them into a single animated GIF or animated WebP.

        Args:
            count:          Number of frames (mutually exclusive with interval)
            interval:       One frame every N seconds (mutually exclusive with count)
            start_percent:  Start at this % of total duration (0-100)
            end_percent:    End at this % of total duration (0-100)
            start_time:     Absolute start time in seconds (overrides start_percent)
            end_time:       Absolute end time in seconds (overrides end_percent)
            frame_duration: How long each frame is shown, in milliseconds (default: 500)
            loop:           0 = loop forever, N = loop N times (GIF/WebP)

        Returns:
            Path to the saved animated file.
        """
        if self.fmt not in self.ANIM_FORMATS:
            raise ValueError(
                f"Format '{self.fmt}' is not supported for animation. "
                f"Choose from: gif, webp"
            )

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            raise RuntimeError("Pillow is required. Run: pip install Pillow")

        cap, cv2 = self._open_video()
        try:
            fps, total_frames, timestamps = self._build_timestamps(
                cap, cv2, count, interval,
                start_percent, end_percent, start_time, end_time
            )

            frames = []
            for idx, ts in enumerate(timestamps, start=1):
                img = self._read_frame(cap, cv2, ts, fps, total_frames, idx)
                if img is not None:
                    frames.append(img)
                    self._log(f"  [{idx:04d}] t={ts:.1f}s captured")
        finally:
            cap.release()

        if not frames:
            raise RuntimeError("No frames could be read from the video")

        ext, pil_format = self.ANIM_FORMATS[self.fmt]
        out_filename = f"{self.prefix}_animated{ext}"
        out_path = self.output_dir / out_filename

        first = frames[0]
        rest  = frames[1:]

        self._log(f"Combining {len(frames)} frame(s) into {out_filename} "
                  f"({frame_duration}ms per frame)")

        if pil_format == "GIF":
            # GIF: convert to palette mode for smaller file sizes
            palette_frames = [f.convert("P", palette=1, dither=0) for f in frames]
            palette_frames[0].save(
                out_path,
                format="GIF",
                save_all=True,
                append_images=palette_frames[1:],
                duration=frame_duration,
                loop=loop,
                optimize=True,
            )
        elif pil_format == "WEBP":
            first.save(
                out_path,
                format="WEBP",
                save_all=True,
                append_images=rest,
                duration=frame_duration,
                loop=loop,
                quality=self.quality,
                method=4,
            )

        return str(out_path)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main():
    """Read command-line options, validate them, and run the generator."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract frames from a video file and save them as still images "
            "or combine them into an animated GIF or animated WebP."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 24 JPG frames spread evenly across the whole video
  %(prog)s movie.mp4 --count 24

  # One frame every 30 seconds, saved as PNG
  %(prog)s movie.mp4 --interval 30 --format png

  # 12 WebP frames from the middle 20%%-80%% of the video
  %(prog)s movie.mp4 --count 12 --start 20 --end 80 --format webp --quality 90

  # 10 frames from a specific time range
  %(prog)s movie.mp4 --count 10 --start-time 0:05:00 --end-time 0:45:00

  # Animated GIF — 16 frames, each shown for 400ms, skipping first/last 5%%
  %(prog)s movie.mp4 --count 16 --format gif --animate --frame-duration 400 --start 5 --end 95

  # Animated WebP — one frame every 30s, 600ms per frame, half-size
  %(prog)s movie.mp4 --interval 30 --format webp --animate --frame-duration 600 --size 50%%

  # Half-size JPGs, one every 60 seconds, saved to a separate folder
  %(prog)s movie.mp4 --interval 60 --size 50%% --output ./gallery

  # Full HD frames, skipping intro and credits
  %(prog)s movie.mp4 --count 20 --start 5 --end 95 --size 1920x1080
        """
    )

    parser.add_argument("video", help="Path to the input video file")

    # --- Sampling: count OR interval ---
    sample_group = parser.add_mutually_exclusive_group(required=True)
    sample_group.add_argument(
        "--count", "-n", type=int, metavar="N",
        help="Number of frames to extract, spread evenly across the chosen range"
    )
    sample_group.add_argument(
        "--interval", "-i", type=float, metavar="SECONDS",
        help="Extract one frame every N seconds"
    )

    # --- Percent-based range ---
    pct_group = parser.add_argument_group(
        "Percent-based range",
        "Define the portion of the video to sample using percentages (0-100). "
        "Ignored if --start-time / --end-time are used."
    )
    pct_group.add_argument(
        "--start", "-s", type=float, default=0.0, metavar="PERCENT",
        help="Start sampling at this %% of total duration (default: 0)"
    )
    pct_group.add_argument(
        "--end", "-e", type=float, default=100.0, metavar="PERCENT",
        help="Stop sampling at this %% of total duration (default: 100)"
    )

    # --- Absolute time range ---
    time_group = parser.add_argument_group(
        "Absolute time range",
        "Override the percent range with exact timestamps. "
        "Accepts seconds (90), MM:SS (1:30), or HH:MM:SS (0:01:30)."
    )
    time_group.add_argument(
        "--start-time", type=parse_time, metavar="TIME",
        help="Start sampling at this timestamp (overrides --start)"
    )
    time_group.add_argument(
        "--end-time", type=parse_time, metavar="TIME",
        help="Stop sampling at this timestamp (overrides --end)"
    )

    # --- Image / animation options ---
    img_group = parser.add_argument_group("Image and animation options")
    img_group.add_argument(
        "--format", "-f",
        choices=["jpg", "png", "webp", "gif"],
        default="jpg", metavar="FORMAT",
        help="Output format: jpg, png, webp (stills) or gif, webp (animated). (default: jpg)"
    )
    img_group.add_argument(
        "--quality", "-q", type=int, default=85, metavar="1-100",
        help="Image quality for jpg/webp, 1-100 (default: 85, ignored for png/gif)"
    )
    img_group.add_argument(
        "--size", type=parse_size, metavar="SIZE",
        help="Output size as WxH pixels (e.g. 1920x1080) or a percentage (e.g. 50%%)"
    )
    img_group.add_argument(
        "--animate", action="store_true",
        help="Combine frames into a single animated file (requires --format gif or webp)"
    )
    img_group.add_argument(
        "--frame-duration", type=int, default=500, metavar="MS",
        help="How long each frame is shown in the animation, in milliseconds (default: 500)"
    )
    img_group.add_argument(
        "--loop", type=int, default=0, metavar="N",
        help="Number of times the animation loops; 0 = loop forever (default: 0)"
    )

    # --- Output options ---
    out_group = parser.add_argument_group("Output options")
    out_group.add_argument(
        "--output", "-o", metavar="DIR",
        help="Output directory (default: same folder as the video)"
    )
    out_group.add_argument(
        "--prefix", metavar="NAME",
        help="Filename prefix for saved files (default: video filename)"
    )
    out_group.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed progress information"
    )

    args = parser.parse_args()

    # --- Validation ---
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    if not 0 <= args.start <= 100:
        parser.error("--start must be between 0 and 100")
    if not 0 <= args.end <= 100:
        parser.error("--end must be between 0 and 100")
    if args.start_time is None and args.end_time is None and args.start >= args.end:
        parser.error("--start must be less than --end")
    if args.frame_duration < 1:
        parser.error("--frame-duration must be at least 1 millisecond")
    if args.animate and args.format not in ("gif", "webp"):
        parser.error("--animate requires --format gif or --format webp")
    if not args.animate and args.format == "gif":
        parser.error("gif output requires --animate (GIF is only supported as an animated format)")

    # --- Run ---
    try:
        generator = VideoGalleryGenerator(
            video_path=args.video,
            output_dir=args.output,
            prefix=args.prefix,
            fmt=args.format,
            quality=args.quality,
            size=args.size,
            verbose=args.verbose
        )

        if args.animate:
            out_path = generator.animate(
                count=args.count,
                interval=args.interval,
                start_percent=args.start,
                end_percent=args.end,
                start_time=args.start_time,
                end_time=args.end_time,
                frame_duration=args.frame_duration,
                loop=args.loop,
            )
            print(f"Saved animated file: '{out_path}'")
        else:
            saved = generator.generate(
                count=args.count,
                interval=args.interval,
                start_percent=args.start,
                end_percent=args.end,
                start_time=args.start_time,
                end_time=args.end_time,
            )
            print(f"Saved {len(saved)} image(s) to '{generator.output_dir}'")
            if args.verbose:
                for f in saved:
                    print(f"  {f}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
