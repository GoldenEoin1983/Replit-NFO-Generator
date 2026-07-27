"""
NFO XML file generator for Kodi/Jellyfin.

WHAT THIS FILE DOES
-------------------
This is the last step in the conversion pipeline. It takes the cleaned-up
dictionary produced by converters.py and turns it into an actual NFO file
(an XML text file that media centers read for titles, plots, actors, etc.).

Reference formats this output follows:
- Kodi movie NFO:   https://kodi.wiki/view/NFO_files/Movies
- Jellyfin NFO:     https://jellyfin.org/docs/general/server/metadata/nfo/

Two document shapes are produced:
- <movie> ... </movie>  for scenes and galleries
- <actor> ... </actor>  for performers
"""

import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom


class NfoGenerator:
    """Turns converted metadata dictionaries into NFO XML text."""

    def __init__(self, encoding: str = 'utf-8', pretty_print: bool = True):
        """
        Set up the generator.

        Args:
            encoding: Text encoding written into the XML header (default: utf-8)
            pretty_print: If True, indent the XML so humans can read it easily
        """
        self.encoding = encoding
        self.pretty_print = pretty_print

    def generate(self, nfo_data: dict[str, Any], data_type: str) -> str:
        """
        Build the NFO XML string for the given data type.

        Args:
            nfo_data: Converted NFO data (from StashToNfoConverter)
            data_type: 'scene', 'performer', or 'gallery'

        Returns:
            Complete XML document as a string
        """
        # Scenes and galleries both use Kodi's <movie> layout;
        # performers use the <actor> layout.
        if data_type in ('scene', 'gallery'):
            return self._generate_movie_nfo(nfo_data)
        if data_type == 'performer':
            return self._generate_actor_nfo(nfo_data)
        raise ValueError(f"Unsupported data type: {data_type}")

    def _generate_movie_nfo(self, nfo_data: dict[str, Any]) -> str:
        """
        Build a <movie> NFO document (used for scenes and galleries).

        Tag names follow the Kodi movie NFO specification:
        https://kodi.wiki/view/NFO_files/Movies
        """
        root = ET.Element('movie')

        # Always-included basics (empty string if missing)
        self._add_text_element(root, 'title', nfo_data.get('title', ''))
        self._add_text_element(root, 'originaltitle', nfo_data.get('originaltitle', ''))
        self._add_text_element(root, 'plot', nfo_data.get('plot', ''))
        self._add_text_element(root, 'userrating', str(nfo_data.get('userrating', 0)))

        # Optional simple tags - only written when we actually have a value
        for tag in ('premiered', 'year', 'studio', 'runtime'):
            value = nfo_data.get(tag)
            if value:
                self._add_text_element(root, tag, str(value))

        # <uniqueid> lets Kodi/Jellyfin tell items apart even if titles match.
        # See: https://kodi.wiki/view/NFO_files/Movies (uniqueid section)
        uniqueid_data = nfo_data.get('uniqueid')
        if uniqueid_data and isinstance(uniqueid_data, dict):
            uniqueid_elem = ET.SubElement(root, 'uniqueid')
            uniqueid_elem.set('type', uniqueid_data.get('type', 'stash'))
            if uniqueid_data.get('default'):
                uniqueid_elem.set('default', 'true')
            uniqueid_elem.text = uniqueid_data.get('value', '')

        # StashApp tags are written as both <genre> and <tag> so they show
        # up in either filter menu of the media center.
        genres = [g for g in nfo_data.get('genres', []) if g]
        for genre in genres:
            self._add_text_element(root, 'genre', genre)
        for genre in genres:
            self._add_text_element(root, 'tag', genre)

        # Each performer becomes an <actor> block with name/role/order
        for actor_data in nfo_data.get('actors', []):
            if not isinstance(actor_data, dict):
                continue
            actor_elem = ET.SubElement(root, 'actor')
            if actor_data.get('name'):
                self._add_text_element(actor_elem, 'name', actor_data['name'])
            if actor_data.get('role'):
                self._add_text_element(actor_elem, 'role', actor_data['role'])
            if actor_data.get('order') is not None:
                self._add_text_element(actor_elem, 'order', str(actor_data['order']))

        return self._format_xml(root)

    def _generate_actor_nfo(self, nfo_data: dict[str, Any]) -> str:
        """
        Build an <actor> NFO document for a performer.

        Kodi and Jellyfin read actor metadata primarily from the media NFO,
        but a standalone actor NFO stores richer detail alongside the
        performer's image folder.
        """
        root = ET.Element('actor')

        self._add_text_element(root, 'name', nfo_data.get('name', ''))

        # Optional simple fields
        for tag in ('biography', 'birthdate'):
            value = nfo_data.get(tag)
            if value:
                self._add_text_element(root, tag, value)

        # Extra details (gender, country, aliases...) and social links are
        # written as custom elements - harmless to media centers that don't
        # understand them, useful for other tools that do.
        for section in ('details', 'social'):
            data = nfo_data.get(section, {})
            if not isinstance(data, dict):
                continue
            for key, value in data.items():
                if not value:
                    continue  # skip empty values to keep the file tidy
                # Lists (e.g. aliases) become one element per item
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if item:
                        self._add_text_element(root, key, str(item))

        return self._format_xml(root)

    def _add_text_element(self, parent: ET.Element, tag: str, text: str) -> ET.Element:
        """Create a child element like <tag>text</tag> under the parent."""
        elem = ET.SubElement(parent, tag)
        elem.text = text if text else ''
        return elem

    def _format_xml(self, root: ET.Element) -> str:
        """
        Convert the XML tree to a final string, optionally pretty-printed,
        and prepend the XML declaration header.
        """
        xml_str = ET.tostring(root, encoding='unicode')

        if self.pretty_print:
            # minidom re-parses the XML and adds indentation
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.documentElement.toprettyxml(indent='  ')
            # minidom leaves blank lines behind - strip them out
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            xml_str = '\n'.join(lines)

        # The declaration tells media centers the file's encoding.
        # standalone="yes" means no external files are needed to read it.
        xml_declaration = f'<?xml version="1.0" encoding="{self.encoding}" standalone="yes" ?>'

        separator = '\n' if self.pretty_print else ''
        return f"{xml_declaration}{separator}{xml_str}"
