#!/usr/bin/env python3
"""
Receipt Scanner - Main Entry Point

A Python application that processes receipt images from Google Drive or Google Photos,
extracts purchase data using OCR, and exports to structured spreadsheet format.
"""

import sys
import logging
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils.config import ConfigManager
from src.utils.logging import setup_logging
from src.auth.google_auth import GoogleAuthManager
from src.auth.credentials import CredentialsManager


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description='Receipt Scanner - Process receipt images with OCR',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --auth                    # Authenticate with Google services
  python main.py --drive-folder <ID>      # Process Google Drive folder
  python main.py --photos-album <ID>      # Process Google Photos album
  python main.py --config config.yaml     # Use specific config file
  python main.py --setup                  # Show setup instructions
        """
    )
    
    # Authentication options
    auth_group = parser.add_argument_group('Authentication')
    auth_group.add_argument(
        '--auth', 
        action='store_true',
        help='Authenticate with Google services'
    )
    auth_group.add_argument(
        '--revoke', 
        action='store_true',
        help='Revoke stored credentials'
    )
    auth_group.add_argument(
        '--setup', 
        action='store_true',
        help='Show setup instructions'
    )
    
    # Source options
    source_group = parser.add_argument_group('Source')
    source_group.add_argument(
        '--drive-folder',
        type=str,
        metavar='FOLDER_ID',
        help='Google Drive folder ID to process'
    )
    source_group.add_argument(
        '--photos-album',
        type=str,
        metavar='ALBUM_ID',
        help='Google Photos album ID to process'
    )
    
    # Configuration options
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument(
        '--config',
        type=str,
        metavar='FILE',
        help='Configuration file path (YAML or JSON)'
    )
    config_group.add_argument(
        '--output-dir',
        type=str,
        metavar='DIR',
        default='output',
        help='Output directory for results (default: output)'
    )
    config_group.add_argument(
        '--output-format',
        choices=['csv', 'xlsx', 'json'],
        default='xlsx',
        help='Output format (default: xlsx)'
    )
    
    # Processing options
    process_group = parser.add_argument_group('Processing')
    process_group.add_argument(
        '--confidence',
        type=float,
        metavar='THRESHOLD',
        default=0.8,
        help='OCR confidence threshold 0.0-1.0 (default: 0.8)'
    )
    process_group.add_argument(
        '--no-duplicates',
        action='store_true',
        help='Skip duplicate detection'
    )
    
    # Logging options
    log_group = parser.add_argument_group('Logging')
    log_group.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    log_group.add_argument(
        '--log-file',
        type=str,
        metavar='FILE',
        help='Log to file instead of console'
    )
    
    return parser


def handle_setup_command() -> None:
    """Display setup instructions."""
    creds_manager = CredentialsManager()
    
    print("=" * 60)
    print("RECEIPT SCANNER SETUP")
    print("=" * 60)
    print(creds_manager.setup_instructions())
    print("=" * 60)
    print()
    print("After setting up credentials, run:")
    print("  python main.py --auth")
    print()


def handle_auth_command(args) -> bool:
    """Handle authentication command."""
    try:
        # Check for credentials file
        creds_manager = CredentialsManager()
        creds_path = creds_manager.get_google_credentials_path()
        
        if not creds_path:
            print("ERROR: No credentials file found!")
            print("Run 'python main.py --setup' for setup instructions.")
            return False
        
        # Validate credentials file
        if not creds_manager.validate_credentials_file(creds_path):
            print(f"ERROR: Invalid credentials file: {creds_path}")
            print("Please check the file format and try again.")
            return False
        
        # Perform authentication
        print(f"Using credentials file: {creds_path}")
        auth_manager = GoogleAuthManager(str(creds_path))
        
        if auth_manager.authenticate():
            print("✓ Authentication successful!")
            print("You can now process receipts from Google Drive and Photos.")
            return True
        else:
            print("✗ Authentication failed!")
            print("Please check your credentials and try again.")
            return False
            
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False


def handle_revoke_command() -> bool:
    """Handle credential revocation command."""
    try:
        auth_manager = GoogleAuthManager()
        if auth_manager.revoke_credentials():
            print("✓ Credentials revoked successfully!")
            return True
        else:
            print("✗ Failed to revoke credentials!")
            return False
            
    except Exception as e:
        print(f"Revoke error: {str(e)}")
        return False


def main():
    """Main application entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Handle setup command first
    if args.setup:
        handle_setup_command()
        return 0
    
    # Set up logging
    setup_logging(
        level=args.log_level,
        log_file=args.log_file
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Receipt Scanner starting...")
    
    # Handle authentication commands
    if args.revoke:
        success = handle_revoke_command()
        return 0 if success else 1
    
    if args.auth:
        success = handle_auth_command(args)
        return 0 if success else 1
    
    # Load configuration
    try:
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Override config with command line arguments
        if args.output_dir:
            config.export.output_directory = args.output_dir
        if args.output_format:
            config.export.output_format = args.output_format
        if args.confidence:
            config.processing.confidence_threshold = args.confidence
        if args.drive_folder:
            config.google_drive_folder_id = args.drive_folder
        if args.photos_album:
            config.google_photos_album_id = args.photos_album
        
        logger.info(f"Configuration loaded from: {config_manager.config_file or 'defaults'}")
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return 1
    
    # Check if we have a source to process
    if not (config.google_drive_folder_id or config.google_photos_album_id):
        print("ERROR: No source specified!")
        print("Please specify either:")
        print("  --drive-folder <FOLDER_ID>")
        print("  --photos-album <ALBUM_ID>")
        print("Or configure in config file.")
        print()
        print("Run 'python main.py --help' for more options.")
        return 1
    
    # Check authentication
    auth_manager = GoogleAuthManager()
    if not auth_manager.is_authenticated():
        print("ERROR: Not authenticated with Google services!")
        print("Run 'python main.py --auth' to authenticate first.")
        return 1
    
    # TODO: Implement processing logic in Phase 2
    print("Receipt processing will be implemented in Phase 2!")
    print(f"Would process:")
    if config.google_drive_folder_id:
        print(f"  - Google Drive folder: {config.google_drive_folder_id}")
    if config.google_photos_album_id:
        print(f"  - Google Photos album: {config.google_photos_album_id}")
    print(f"  - Output format: {config.export.output_format}")
    print(f"  - Output directory: {config.export.output_directory}")
    
    logger.info("Receipt Scanner completed Phase 1 setup")
    return 0


if __name__ == '__main__':
    sys.exit(main())