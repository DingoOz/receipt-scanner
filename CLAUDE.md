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

✅ **Phase 2 Complete**: Google Services Integration
- Google Drive API integration with folder listing and file download
- Google Photos Library API integration with album access
- Image download and caching system with hash calculation
- Duplicate detection using perceptual hashing and SSIM
- Comprehensive image processing pipeline
- Cache management with size limits and cleanup

✅ **Phase 3 Complete**: OCR and Data Extraction
- Google Cloud Vision API integration with document detection
- OpenCV image preprocessing for enhanced OCR accuracy
- Tesseract fallback for offline OCR processing
- Advanced receipt data extraction with regex patterns
- Merchant-specific parsing templates (Walmart, Target, Costco, etc.)
- Comprehensive validation and confidence scoring system
- Receipt data structuring with items, totals, dates, and merchants

✅ **Phase 4 Complete**: Data Export and Spreadsheet Generation
- Multi-format export system (CSV, Excel, JSON)
- Customizable export templates for different use cases (personal, business, tax, accounting)
- Professional Excel formatting with charts and multiple worksheets
- Visual report generation with matplotlib charts and PDF reports
- Batch export functionality with multiple templates simultaneously
- Data formatting with currency, date, and field mapping options
- Comprehensive export packages with summaries and analytics

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

# List available Google Drive folders
python main.py --list-drive-folders

# List available Google Photos albums  
python main.py --list-photos-albums

# Search for Drive folders by name
python main.py --search-drive "receipts"

# Search for Photos albums by title
python main.py --search-photos "expenses"

# Process Google Drive folder (download only)
python main.py --drive-folder <FOLDER_ID>

# Process Google Photos album (download only)
python main.py --photos-album <ALBUM_ID>

# Process with OCR and data extraction
python main.py --drive-folder <FOLDER_ID> --ocr

# Process with OCR and custom confidence threshold
python main.py --photos-album <ALBUM_ID> --ocr --confidence 0.9

# Process without image preprocessing
python main.py --drive-folder <FOLDER_ID> --ocr --no-preprocessing

# Process with OCR and standard export
python main.py --drive-folder <FOLDER_ID> --ocr --export

# Process with OCR and specific export templates
python main.py --drive-folder <FOLDER_ID> --ocr --export-templates personal_expenses business_expenses

# Process with OCR and comprehensive export package
python main.py --drive-folder <FOLDER_ID> --ocr --export-comprehensive

# Process with OCR and comprehensive export including reports
python main.py --drive-folder <FOLDER_ID> --ocr --export-comprehensive --export-reports

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