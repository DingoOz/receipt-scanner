# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python application that automatically processes receipt images from Google Drive or Google Photos, extracts purchase data using OCR technology, and organizes the information into structured spreadsheet format with duplicate detection capabilities.

## Planned Architecture

The project follows a modular architecture as outlined in the development plan:

- **Authentication Layer** (`auth/`): Google API OAuth 2.0 handling for Drive and Photos access
- **Service Layer** (`services/`): Integration with Google Drive, Photos, and Vision APIs
- **Processing Layer** (`processing/`): Image preprocessing with OpenCV, OCR with Google Vision/Tesseract, and data extraction
- **Storage Layer** (`storage/`): Local caching and duplicate detection using image hashing
- **Export Layer** (`export/`): Spreadsheet generation (CSV/Excel) with pandas/openpyxl
- **Utilities** (`utils/`): Configuration management, logging, and helper functions

## Key Technology Stack

- **Google APIs**: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
- **Image Processing**: `opencv-python`, `Pillow`
- **OCR**: `google-cloud-vision` (primary), `pytesseract` (fallback)
- **Data Processing**: `pandas`, `openpyxl`
- **Core Python**: `pathlib`, `hashlib`, `json`, `logging`

## Development Status

✅ **Phase 1 Complete**: Project Setup and Authentication
- Project directory structure created
- Google API OAuth 2.0 authentication implemented
- Configuration management system with YAML/JSON support
- Command-line interface with argument parsing
- Logging system with configurable levels

📋 **Next Phase**: Google Services Integration (Phase 2)

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Show setup instructions
python main.py --setup

# Authenticate with Google services
python main.py --auth

# Revoke stored credentials
python main.py --revoke

# Process Google Drive folder (when Phase 2 is complete)
python main.py --drive-folder <FOLDER_ID>

# Process Google Photos album (when Phase 2 is complete)
python main.py --photos-album <ALBUM_ID>

# Run with custom configuration
python main.py --config config/config.yaml

# Set logging level
python main.py --log-level DEBUG
```

## Project Goals

- Process various receipt formats with >80% accuracy
- Implement robust duplicate detection
- Handle Google Drive and Photos integration
- Generate clean, structured spreadsheet outputs
- Provide comprehensive error handling and logging