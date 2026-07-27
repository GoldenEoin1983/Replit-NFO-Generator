# StashApp to NFO Converter

## Overview

This is a command-line tool that converts StashApp metadata into Kodi/Jellyfin compatible NFO (XML) files. The application supports both direct StashApp API integration and JSON file processing for three types of media metadata: scenes (videos), performers (actors), and galleries (image collections). It features automatic data type detection, field mapping between StashApp and NFO formats, base64 image extraction, and generates properly formatted XML files with UTF-8 encoding for media center compatibility.

## User Preferences

Preferred communication style: Simple, everyday language.

Node.js is managed with fnm (Fast Node Manager), not the Replit Node module. Node v22 is installed via `fnm` with `fnm default 22`; binaries are symlinked into `~/workspace/.config/npm/node_global/bin` and `~/.profile` runs `fnm env` for new shells. Because the Replit Node module is removed, `node`/`npm`/`npx`/`pnpm`/`pnpx` are also symlinked into `~/workspace/.pythonlibs/bin` (the only writable folder on the default PATH) so GUI features like the Skills tab can find them; re-create these links if a Python reinstall ever clears that folder.

Prefer pnpm/pnpx over npm/npx for Node package work (enabled via corepack). Prefer uv for Python projects and environments (`pyproject.toml` + `uv.lock` are the source of truth), but always keep a `requirements.txt` in sync for pip compatibility — regenerate it with `make requirements` after dependency changes.

## System Architecture

### Core Components

**Modular Parser-Converter-Generator Pattern**: The application follows a clear separation of concerns with four main components:
- `StashParser`: Handles JSON file parsing and automatic data type detection
- `StashApiClient`: Manages direct connection to StashApp GraphQL API for real-time data retrieval
- `StashToNfoConverter`: Transforms StashApp data structures into NFO-compatible formats with base64 image extraction
- `NfoGenerator`: Creates properly formatted XML output for media centers

**Data Type Detection System**: Implements intelligent auto-detection by analyzing JSON structure and presence of specific fields (file/duration for scenes, gender/birthdate for performers, folder/scenes for galleries).

**Field Mapping Strategy**: Uses a mapping approach to convert StashApp-specific fields to standard NFO XML tags, including rating scale conversion (1-5 to 0-10) and metadata normalization.

**XML Generation Architecture**: Utilizes Python's xml.etree.ElementTree for XML creation with optional pretty-printing via minidom for human-readable output.

### Design Patterns

**Factory Pattern**: The converter and generator classes use factory-like methods to handle different data types (scene, performer, gallery) with type-specific processing logic.

**Command-Line Interface**: Built with argparse for flexible command-line operation with auto-detection capabilities and configurable output paths.

**Error Handling Strategy**: Implements comprehensive error handling for file operations, JSON parsing, and data conversion with meaningful error messages.

## External Dependencies

**Python Standard Library**: 
- `xml.etree.ElementTree` and `xml.dom.minidom` for XML processing
- `json` for JSON parsing
- `argparse` for command-line interface
- `pathlib` for file system operations

**Third-Party Dependencies**:
- `stashapp-tools`: Official StashApp API client for GraphQL communication
- `requests`: HTTP library for API connectivity (dependency of stashapp-tools)
- `certifi`: SSL certificate bundle (dependency of stashapp-tools)

**Target Media Centers**: 
- Kodi NFO format compatibility
- Jellyfin NFO format compatibility
- UTF-8 encoding support for international character sets
- Base64 image extraction for poster/fanart files

**StashApp Integration**:
- Direct GraphQL API connectivity
- Real-time data fetching by scene/performer/gallery ID
- Search-based content discovery
- Support for authenticated connections (API key or username/password)
- Automatic type detection and data retrieval