# Receipt Scanner

A powerful Python application that automatically processes receipt images from Google Drive or Google Photos, extracts purchase data using advanced OCR technology, and organizes the information into structured formats with comprehensive duplicate detection.

## Features

### ✅ **Phase 1 Complete**: Project Setup and Authentication
- **OAuth 2.0 Authentication**: Secure Google API integration with automatic token refresh
- **Flexible Configuration**: YAML/JSON configuration with environment variable support
- **Comprehensive CLI**: Full command-line interface with help and argument parsing
- **Professional Logging**: Configurable logging levels and file output

### ✅ **Phase 2 Complete**: Google Services Integration
- **Google Drive Integration**: Folder listing, navigation, and bulk image download
- **Google Photos Integration**: Album access and media item processing
- **Smart Caching System**: Local storage with hash-based duplicate detection
- **Cache Management**: Size limits, automatic cleanup, and storage optimization
- **Advanced Duplicate Detection**: Perceptual hashing and structural similarity analysis

### ✅ **Phase 3 Complete**: OCR and Data Extraction
- **Multi-Method OCR**: Google Cloud Vision API with Tesseract fallback
- **Image Preprocessing**: OpenCV-based enhancement for better accuracy
- **Advanced Data Extraction**: Sophisticated parsing of receipts with regex patterns
- **Merchant Intelligence**: Store-specific templates (Walmart, Target, Costco, etc.)
- **Validation Engine**: Comprehensive data quality scoring and issue detection
- **Confidence Scoring**: Multi-factor reliability assessment

### ✅ **Phase 4 Complete**: Data Export and Spreadsheet Generation
- **Multi-Format Export**: Professional CSV, Excel, and JSON output
- **Export Templates**: Customizable templates for personal, business, tax, and accounting
- **Visual Reports**: Charts, graphs, and PDF reports with spending analytics
- **Batch Processing**: Multiple templates and comprehensive export packages
- **Professional Formatting**: Excel worksheets with charts, styling, and summaries
- **Data Analysis**: Merchant breakdowns, temporal analysis, and quality metrics

## Installation

### Prerequisites

1. **Python 3.8+** with pip
2. **Google Cloud Project** with APIs enabled
3. **OpenCV dependencies** (usually installed automatically)
4. **Tesseract OCR** (optional, for offline processing)

### Quick Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd receipt-scanner
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google APIs:**
   ```bash
   python main.py --setup
   ```
   Follow the detailed instructions to:
   - Create a Google Cloud Project
   - Enable required APIs (Drive, Photos, Vision)
   - Download OAuth 2.0 credentials

4. **Authenticate:**
   ```bash
   python main.py --auth
   ```

## Usage

### Basic Commands

```bash
# Show setup instructions
python main.py --setup

# Authenticate with Google services
python main.py --auth

# List available Google Drive folders
python main.py --list-drive-folders

# List available Google Photos albums
python main.py --list-photos-albums

# Search for specific folders/albums
python main.py --search-drive "receipts"
python main.py --search-photos "expenses"
```

### Image Processing

```bash
# Download and cache images (no OCR)
python main.py --drive-folder <FOLDER_ID>
python main.py --photos-album <ALBUM_ID>

# Full OCR processing with data extraction
python main.py --drive-folder <FOLDER_ID> --ocr
python main.py --photos-album <ALBUM_ID> --ocr

# Custom confidence threshold (0.0-1.0)
python main.py --drive-folder <FOLDER_ID> --ocr --confidence 0.9

# Disable image preprocessing
python main.py --drive-folder <FOLDER_ID> --ocr --no-preprocessing

# Custom configuration file
python main.py --config my-config.yaml --drive-folder <FOLDER_ID> --ocr
```

### Data Export

```bash
# Standard export (uses configured format)
python main.py --drive-folder <FOLDER_ID> --ocr --export

# Export with specific templates
python main.py --drive-folder <FOLDER_ID> --ocr \
  --export-templates personal_expenses business_expenses

# Comprehensive export package with reports
python main.py --drive-folder <FOLDER_ID> --ocr --export-comprehensive

# Include visual reports and charts
python main.py --drive-folder <FOLDER_ID> --ocr \
  --export-comprehensive --export-reports
```

### Advanced Options

```bash
# Set output directory and format
python main.py --drive-folder <FOLDER_ID> --ocr \
  --output-dir ./my-receipts --output-format xlsx

# Enable debug logging
python main.py --drive-folder <FOLDER_ID> --ocr \
  --log-level DEBUG --log-file processing.log

# Skip duplicate detection
python main.py --drive-folder <FOLDER_ID> --ocr --no-duplicates
```

## Configuration

The application uses a hierarchical configuration system:

1. **Default values** (built-in)
2. **Configuration file** (`config/config.yaml`)
3. **Environment variables** (e.g., `RECEIPT_CONFIDENCE_THRESHOLD`)
4. **Command-line arguments** (highest priority)

### Sample Configuration (`config/config.yaml`)

```yaml
# Image processing and OCR settings
processing:
  confidence_threshold: 0.8        # Minimum confidence for OCR results
  max_image_size: 2048            # Maximum image dimension in pixels
  use_opencv_preprocessing: true   # Enable image preprocessing
  fallback_to_tesseract: true     # Use Tesseract if Vision API fails

# Data export settings
export:
  output_format: 'xlsx'           # Output format: csv, xlsx, json
  output_directory: 'output'      # Directory for exported files
  include_confidence_scores: true # Include OCR confidence in output
  include_raw_text: false        # Include raw OCR text in output
  date_format: '%Y-%m-%d'        # Date format for exports

# Storage and caching settings
storage:
  cache_directory: 'cache'        # Directory for cached images
  max_cache_size_mb: 1000        # Maximum cache size in MB
  duplicate_threshold: 0.95      # Similarity threshold for duplicates

# Google services configuration
google_drive_folder_id: null     # Default Drive folder to process
google_photos_album_id: null     # Default Photos album to process

# Application settings
log_level: 'INFO'               # Logging level
```

### Environment Variables

```bash
# Processing settings
export RECEIPT_CONFIDENCE_THRESHOLD=0.8
export RECEIPT_MAX_IMAGE_SIZE=2048
export RECEIPT_OUTPUT_FORMAT=xlsx
export RECEIPT_OUTPUT_DIR=./output

# Google service IDs
export GOOGLE_DRIVE_FOLDER_ID=your_folder_id
export GOOGLE_PHOTOS_ALBUM_ID=your_album_id

# Credentials
export GOOGLE_CREDENTIALS_FILE=./credentials.json
export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json

# Logging
export LOG_LEVEL=DEBUG
```

## Output

### Processing Results

The application provides detailed output showing:

```
Processing Google Drive folder with OCR: 1234567890
OCR Engine Status:
  Google Vision: ✓
  Tesseract: ✓
  Preprocessing: ✓

============================================================
PROCESSING RESULTS
============================================================
Source: My Receipts (google_drive)
Total files found: 25
Successfully processed: 23
Skipped (cached): 2
Errors: 0
OCR Success: 21/23
Valid receipts: 18

OCR Methods used:
  google_vision: 19
  tesseract: 2
Average OCR confidence: 87.3%

Valid Receipt Summary:
  Total amount processed: $1,247.89
  Unique merchants: 8
  Merchants: Walmart, Target, Starbucks, Shell, Kroger

Cache Usage: 156.7 MB / 1000 MB (15.7%)
Unique files: 23, Duplicates: 2

============================================================
EXPORTING DATA
============================================================
✓ Comprehensive export package created!
  Total files: 12
  Spreadsheets: 3
  Reports: 4
  Template exports: 5
  Output directory: ./output

✓ Phase 4 OCR processing and export completed successfully!
All phases implemented: Image processing, OCR, data extraction, and export.
```

### Extracted Data Structure

Each receipt is parsed into structured data:

```json
{
  "merchant_name": "Walmart Supercenter",
  "merchant_address": "123 Main St, City, ST 12345",
  "date": "2024-01-15",
  "time": "14:32",
  "total_amount": "67.89",
  "subtotal": "63.45",
  "tax_amount": "4.44",
  "payment_method": "Visa",
  "items": [
    {
      "description": "MILK WHOLE GAL",
      "quantity": 1.0,
      "unit_price": "3.98",
      "total_price": "3.98"
    }
  ],
  "confidence_score": 0.91
}
```

### Export Output Files

When using export functionality, the application generates various output files:

**Standard Export (`--export`):**
- `receipts_source_timestamp.xlsx` - Main Excel file with multiple worksheets
- `receipts_source_timestamp.csv` - CSV format for data analysis
- `receipts_source_timestamp.json` - JSON format with full metadata

**Template Export (`--export-templates`):**
- `personal_expenses_source_timestamp.xlsx` - Personal expense tracking
- `business_expenses_source_timestamp.csv` - Business expense report
- `tax_preparation_source_timestamp.xlsx` - Tax-optimized format

**Comprehensive Export (`--export-comprehensive`):**
- Multiple template exports in various formats
- `receipt_report_source_timestamp.pdf` - Visual analytics report
- `chart_spending_by_merchant_timestamp.png` - Merchant spending chart
- `chart_spending_over_time_timestamp.png` - Timeline analysis
- `summary_report_source_timestamp.txt` - Text summary

Each Excel file contains multiple worksheets:
- **Summary** - Key statistics and merchant breakdown with charts
- **Receipt Details** - Complete receipt information
- **Line Items** - Individual item details from receipts

## Export Templates

The application includes built-in templates for different use cases:

- **Personal Expenses** - For individual expense tracking
- **Business Expenses** - For business expense reports with approval fields
- **Tax Preparation** - Optimized for tax filing with categorization
- **Accounting Integration** - Formatted for accounting software import
- **Detailed Analysis** - Comprehensive data with all available fields

## Google API Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable billing (required for Vision API)

### 2. Enable Required APIs

Enable these APIs in your project:
- **Google Drive API** - for accessing Drive folders
- **Google Photos Library API** - for accessing Photos albums  
- **Google Cloud Vision API** - for OCR processing

### 3. Create Credentials

**For personal use (OAuth 2.0):**
1. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
2. Configure consent screen if prompted
3. Choose "Desktop application"
4. Download the JSON file as `credentials.json`

**For server/automated use (Service Account):**
1. Go to Credentials → Create Credentials → Service Account
2. Create the service account and download the JSON key
3. Save as `service-account.json`
4. Share your Drive folders/Photos albums with the service account email

### 4. Place Credentials

Put your credentials file in one of these locations:
- `./config/credentials.json`
- `./credentials.json`
- `~/.config/receipt-scanner/credentials.json`

Or set the environment variable:
```bash
export GOOGLE_CREDENTIALS_FILE=/path/to/your/credentials.json
```

## Troubleshooting

### Common Issues

**Authentication errors:**
```bash
# Re-authenticate
python main.py --revoke
python main.py --auth
```

**OCR not working:**
- Check Google Cloud Vision API is enabled and has quota
- Verify Tesseract is installed: `tesseract --version`
- Try with `--no-preprocessing` flag

**Low accuracy:**
- Increase confidence threshold: `--confidence 0.9`
- Enable preprocessing: remove `--no-preprocessing`
- Check image quality in cache directory

**Export issues:**
- Check output directory permissions
- Verify matplotlib dependencies: `pip install matplotlib seaborn`
- Try basic export first: `--export` before `--export-comprehensive`

**Cache issues:**
```bash
# Clear cache
rm -rf cache/
# Or configure smaller cache size in config.yaml
```

### Getting Help

```bash
# Show all available options
python main.py --help

# Check OCR engine status
python main.py --drive-folder <ID> --ocr --log-level DEBUG

# Test with single folder
python main.py --list-drive-folders
python main.py --drive-folder <FOLDER_ID> --ocr
```

## Architecture

The application follows a modular architecture:

- **Authentication Layer**: OAuth 2.0 and service account handling
- **Service Layer**: Google APIs integration (Drive, Photos, Vision)
- **Processing Layer**: Image preprocessing, OCR, and data extraction
- **Storage Layer**: Caching, duplicate detection, and file management
- **Export Layer**: Data formatting and output generation (Phase 4)

## Development

### Project Structure

```
receipt-scanner/
├── src/
│   ├── auth/              # Authentication and credentials
│   ├── services/          # Google API services
│   ├── processing/        # OCR and data extraction
│   ├── storage/           # Caching and duplicate detection
│   ├── export/            # Data export (Phase 4)
│   └── utils/             # Configuration and utilities
├── config/                # Configuration files
├── tests/                 # Test suite
├── docs/                  # Documentation
├── main.py               # Main entry point
└── requirements.txt      # Python dependencies
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Roadmap

- ✅ **Phase 1**: Project Setup and Authentication
- ✅ **Phase 2**: Google Services Integration  
- ✅ **Phase 3**: OCR and Data Extraction
- ✅ **Phase 4**: Data Export and Spreadsheet Generation
- **Phase 5**: Error handling and quality assurance
- **Phase 6**: Web interface and advanced features

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the command help: `python main.py --help`
- Enable debug logging: `--log-level DEBUG`
- Check Google API quotas and billing in Cloud Console