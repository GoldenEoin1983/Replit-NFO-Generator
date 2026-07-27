"""
StashApp JSON parsers.

WHAT THIS FILE DOES
-------------------
StashApp can export its metadata (scenes, performers, galleries) as JSON
files. This module reads those files and works out what kind of data is
inside, so the rest of the program knows how to convert it.

Think of it as the "front door" of the converter:
    1. parse_file()  - opens and reads the JSON file
    2. detect_type() - looks at the fields to guess scene/performer/gallery
    3. validate_*()  - quick sanity checks before converting
"""

import json
from pathlib import Path
from typing import Any


class StashParser:
    """Reads StashApp JSON files and figures out what type of data they hold."""

    def parse_file(self, file_path: str | Path) -> dict[str, Any]:
        """
        Open a JSON file and return its contents as a Python dictionary.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data as a dictionary

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
        """
        # 'utf-8' encoding ensures international characters read correctly
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def detect_type(self, data: dict[str, Any]) -> str:
        """
        Guess whether the data describes a scene, performer, or gallery.

        The trick: each type has "fingerprint" fields that the others don't.
        - Scenes have a 'file' section with video details (duration, codec...)
        - Performers have personal fields like 'gender' or 'birthdate'
        - Galleries have a 'folder' or linked 'scenes' list

        Args:
            data: Parsed JSON data

        Returns:
            One of: 'scene', 'performer', 'gallery', or 'unknown'
        """
        # A 'file' dictionary (with duration, codec, etc.) means it's a scene
        if isinstance(data.get('file'), dict):
            return 'scene'

        # Personal attributes only appear on performers
        if any(key in data for key in ['gender', 'birthdate', 'ethnicity', 'measurements']):
            return 'performer'

        # Galleries point at a folder of images and usually list performers
        if any(key in data for key in ['folder', 'scenes']) and 'performers' in data:
            return 'gallery'

        # Fall back to 'scene' if it at least looks like media metadata
        if any(key in data for key in ['title', 'studio', 'tags', 'performers']):
            return 'scene'

        return 'unknown'

    def validate_scene_data(self, data: dict[str, Any]) -> bool:
        """A usable scene needs at least a title or file information."""
        return 'title' in data or 'file' in data

    def validate_performer_data(self, data: dict[str, Any]) -> bool:
        """A usable performer needs at least a name."""
        return 'name' in data

    def validate_gallery_data(self, data: dict[str, Any]) -> bool:
        """A usable gallery needs at least a title or folder information."""
        return 'title' in data or 'folder' in data
