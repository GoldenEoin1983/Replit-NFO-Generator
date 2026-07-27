"""
Converters: StashApp data -> NFO-ready dictionaries.

WHAT THIS FILE DOES
-------------------
This is the middle step of the pipeline. It takes the raw StashApp data
(from a JSON file or the API) and reshapes it into a simple dictionary
that nfo_generator.py can turn into XML.

Key jobs:
- Rename fields (StashApp 'details' -> NFO 'plot', 'tags' -> 'genres', ...)
- Convert values (5-star rating -> 0-10 scale, seconds -> minutes)
- Normalise dates into YYYY-MM-DD (the format Kodi/Jellyfin expect,
  see https://kodi.wiki/view/NFO_files/Movies)
- Decode base64 images embedded in the JSON and save them as image files
  named the way Kodi/Jellyfin look for artwork (poster/fanart,
  see https://kodi.wiki/view/Artwork_types)
"""

import base64
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar


class StashToNfoConverter:
    """Reshapes StashApp dictionaries into NFO-compatible dictionaries."""

    def __init__(self):
        """Set up the converter. extracted_images records what we saved."""
        self.extracted_images: list[dict[str, str | int]] = []

    def convert(self, stash_data: dict[str, Any],
                data_type: str) -> dict[str, Any]:
        """
        Convert StashApp data to an NFO-ready dictionary.

        Args:
            stash_data: Parsed StashApp JSON data
            data_type: 'scene', 'performer', or 'gallery'

        Returns:
            Dictionary ready for NfoGenerator
        """
        if data_type == 'scene':
            return self._convert_scene(stash_data)
        if data_type == 'performer':
            return self._convert_performer(stash_data)
        if data_type == 'gallery':
            return self._convert_gallery(stash_data)
        raise ValueError(f"Unsupported data type: {data_type}")

    # ------------------------------------------------------------------
    # Shared helpers for scene + gallery (they map almost identically)
    # ------------------------------------------------------------------
    def _convert_common_media(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Map the fields that scenes and galleries share:
        title, plot, date/year, studio, unique ID, tags, and performers.
        """
        nfo_data: dict[str, Any] = {
            'title': data.get('title', ''),
            'originaltitle': data.get('title', ''),
            'plot': data.get('details', ''),  # StashApp 'details' = NFO 'plot'
            'studio': data.get('studio', ''),
        }

        # Dates: NFO wants YYYY-MM-DD for <premiered>, plus a <year> tag
        date_str = data.get('date')
        if date_str:
            nfo_data['premiered'] = self._convert_date(date_str)
            try:
                # The first 4 characters of a normalised date are the year
                nfo_data['year'] = int(date_str[:4])
            except (ValueError, TypeError):
                pass  # non-numeric year - just skip the <year> tag

        # The StashApp URL doubles as a unique identifier so media centers
        # can tell entries apart even when titles match
        url = data.get('url')
        if url:
            nfo_data['uniqueid'] = {'type': 'stash', 'value': url, 'default': True}

        # StashApp 'tags' map to NFO genres
        tags = data.get('tags', [])
        if isinstance(tags, list):
            nfo_data['genres'] = tags

        # StashApp 'performers' map to NFO actors
        performers = data.get('performers', [])
        if isinstance(performers, list):
            nfo_data['actors'] = self._convert_performers_to_actors(performers)

        return nfo_data

    def _convert_scene(self, scene_data: dict[str, Any]) -> dict[str, Any]:
        """Convert a StashApp scene to Kodi/Jellyfin movie NFO fields."""
        nfo_data = self._convert_common_media(scene_data)

        # Rating: StashApp uses 1-5 stars; NFO <userrating> is 0-10
        # (see https://kodi.wiki/view/NFO_files/Movies)
        rating = scene_data.get('rating')
        try:
            nfo_data['userrating'] = float(rating) * 2 if rating is not None else 0
        except (ValueError, TypeError):
            nfo_data['userrating'] = 0

        # Runtime: StashApp stores duration in seconds; NFO wants minutes
        file_info = scene_data.get('file', {})
        if isinstance(file_info, dict):
            duration = file_info.get('duration')
            if duration:
                try:
                    nfo_data['runtime'] = int(float(duration) / 60)
                except (ValueError, TypeError):
                    pass  # unreadable duration - skip the <runtime> tag

        return nfo_data

    def _convert_gallery(self, gallery_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a StashApp gallery (image collection) to NFO fields.
        Galleries reuse the movie layout since NFO has no gallery type.
        """
        nfo_data = self._convert_common_media(gallery_data)
        nfo_data['media_type'] = 'gallery'  # marker for downstream tools
        return nfo_data

    # ------------------------------------------------------------------
    # Performer conversion
    # ------------------------------------------------------------------

    # (StashApp field, human-readable label) pairs used to build the
    # biography text block, in display order.
    _BIO_FIELDS: ClassVar[list[tuple[str, str]]] = [
        ('gender', 'Gender'),
        ('ethnicity', 'Ethnicity'),
        ('country', 'Country'),
        ('height', 'Height'),
        ('measurements', 'Measurements'),
        ('eye_color', 'Eye Color'),
        ('career_length', 'Career Length'),
        ('tattoos', 'Tattoos'),
        ('piercings', 'Piercings'),
    ]

    def _convert_performer(self, performer_data: dict[str, Any]) -> dict[str, Any]:
        """Convert a StashApp performer to actor NFO fields."""
        nfo_data: dict[str, Any] = {
            'name': performer_data.get('name', ''),
            'biography': self._build_performer_biography(performer_data),
        }

        birthdate = performer_data.get('birthdate')
        if birthdate:
            nfo_data['birthdate'] = self._convert_date(birthdate)

        # Extra attributes kept as individual fields too, so the generator
        # can write them as their own XML elements.
        # Note: career_length appears only in the biography text, not here,
        # so the actor NFO keeps its original set of XML elements.
        nfo_data['details'] = {
            key: performer_data.get(key, '')
            for key, _ in self._BIO_FIELDS
            if key != 'career_length'
        }
        nfo_data['details']['aliases'] = performer_data.get('aliases', [])

        # Social/web links
        nfo_data['social'] = {
            'url': performer_data.get('url', ''),
            'twitter': performer_data.get('twitter', ''),
            'instagram': performer_data.get('instagram', ''),
        }

        return nfo_data

    def _build_performer_biography(self, performer_data: dict[str, Any]) -> str:
        """
        Build a readable "Label: value" biography block from whatever
        performer fields are present. Empty fields are skipped.
        """
        bio_parts = [
            f"{label}: {performer_data[key]}"
            for key, label in self._BIO_FIELDS
            if performer_data.get(key)
        ]

        # Aliases are a list, so they get special "join" treatment
        aliases = performer_data.get('aliases', [])
        if aliases and isinstance(aliases, list):
            bio_parts.append(f"Aliases: {', '.join(aliases)}")

        return '\n'.join(bio_parts)

    # ------------------------------------------------------------------
    # Small shared utilities
    # ------------------------------------------------------------------
    def _convert_performers_to_actors(
            self, performers: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Turn the performers list into NFO actor entries.
        StashApp sometimes stores performers as plain name strings and
        sometimes as dictionaries - both are handled here.
        The 'order' number controls the display order in the media center.
        """
        actors = []
        for i, performer in enumerate(performers):
            actor: dict[str, Any] = {'order': i}
            if isinstance(performer, str):
                actor['name'] = performer
                actor['role'] = ''
            elif isinstance(performer, dict):
                actor['name'] = performer.get('name', '')
                actor['role'] = performer.get('role', '')
            else:
                continue  # unknown shape - skip it
            actors.append(actor)
        return actors

    def _convert_date(self, date_str: str) -> str:
        """
        Normalise a date string to YYYY-MM-DD (the NFO standard).

        Tries several common formats; if none match, the original string
        is returned unchanged rather than losing the information.
        """
        if not date_str:
            return ''

        date_formats = [
            '%Y-%m-%d',            # 2023-12-25
            '%Y-%m-%dT%H:%M:%S',   # 2023-12-25T10:30:00
            '%Y-%m-%dT%H:%M:%S%z', # 2023-12-25T10:30:00Z
            '%d/%m/%Y',            # 25/12/2023
            '%m/%d/%Y',            # 12/25/2023
            '%d-%m-%Y',            # 25-12-2023
            '%m-%d-%Y',            # 12-25-2023
        ]

        for fmt in date_formats:
            try:
                # We only care about the date part, so anything after 'T'
                # (the time) is cut off before parsing
                dt = datetime.strptime(  # noqa: DTZ007
                    date_str.split('T')[0],
                    fmt.split('T')[0])
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue  # try the next format

        return date_str  # unknown format - keep the original

    # ------------------------------------------------------------------
    # Image extraction (base64 -> real image files)
    # ------------------------------------------------------------------
    def extract_images(self, stash_data: dict[str, Any], output_path: Path) -> list[str]:
        """
        Find base64-encoded images in the StashApp data and save them as
        real image files next to the NFO.

        Filenames follow the Kodi/Jellyfin local artwork conventions
        (poster.jpg, fanart.jpg) so the media center picks them up
        automatically. See:
        - https://kodi.wiki/view/Artwork_types
        - https://jellyfin.org/docs/general/server/media/movies/ (images)

        Args:
            stash_data: Parsed StashApp JSON data
            output_path: Path of the NFO file (images go in the same folder)

        Returns:
            List of image filenames that were saved
        """
        self.extracted_images.clear()
        saved_images = []

        # Which StashApp fields may hold images, and what artwork type
        # each one becomes
        image_fields = {
            'cover': 'poster',     # Cover image -> poster
            'image': 'thumb',      # Generic image -> thumbnail
            'poster': 'poster',    # Poster image -> poster
            'thumbnail': 'thumb',  # Thumbnail -> thumbnail
            'fanart': 'fanart',    # Fanart -> fanart (background art)
        }

        output_dir = output_path.parent
        base_name = output_path.stem  # filename without the .nfo extension

        for field_name, image_type in image_fields.items():
            image_data = stash_data.get(field_name)
            if isinstance(image_data, str) and image_data:
                saved_file = self._save_base64_image(
                    image_data, output_dir, base_name, image_type)
                if saved_file:
                    saved_images.append(saved_file)

        return saved_images

    def _save_base64_image(self, image_data: str, output_dir: Path,
                           base_name: str, image_type: str) -> str | None:
        """
        Decode one base64 image string and write it to disk.

        Returns the saved filename, or None if anything went wrong
        (a bad image should not stop the whole conversion).
        """
        try:
            # Browsers/APIs often prefix images with "data:image/jpeg;base64,"
            # - everything before the comma is metadata we don't need
            if image_data.startswith('data:'):
                image_data = image_data.split(',', 1)[1]

            image_bytes = base64.b64decode(image_data)

            # Look at the first few bytes to work out jpg/png/gif/webp
            image_format = self._detect_image_format(image_bytes)
            if not image_format:
                return None

            # Posters and fanart use the standard Kodi/Jellyfin filenames;
            # other images are prefixed with the NFO's name
            if image_type in ('poster', 'fanart'):
                filename = f"{image_type}.{image_format}"
            else:
                filename = f"{base_name}-{image_type}.{image_format}"

            image_path = output_dir / filename
            with open(image_path, 'wb') as f:
                f.write(image_bytes)

            # Remember what we saved (useful for verbose output)
            self.extracted_images.append({
                'type': image_type,
                'filename': filename,
                'size': len(image_bytes),
            })

            return filename

        except Exception:  # noqa: BLE001
            # A corrupt image shouldn't crash the conversion - skip it
            return None

    def _detect_image_format(self, image_bytes: bytes) -> str | None:
        """
        Identify the image format from its "magic bytes" - the first few
        bytes of every image file that identify its type.
        """
        if not image_bytes:
            return None

        if image_bytes.startswith(b'\xff\xd8\xff'):
            return 'jpg'
        if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        if image_bytes.startswith((b'GIF87a', b'GIF89a')):
            return 'gif'
        if image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
            return 'webp'
        if image_bytes.startswith(b'BM'):
            return 'bmp'

        # Unknown header - assume jpg, the most common case
        return 'jpg'
