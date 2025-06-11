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
    source_group.add_argument(
        '--list-drive-folders',
        action='store_true',
        help='List available Google Drive folders'
    )
    source_group.add_argument(
        '--list-photos-albums',
        action='store_true',
        help='List available Google Photos albums'
    )
    source_group.add_argument(
        '--search-drive',
        type=str,
        metavar='NAME',
        help='Search Google Drive folders by name'
    )
    source_group.add_argument(
        '--search-photos',
        type=str,
        metavar='TITLE',
        help='Search Google Photos albums by title'
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
    process_group.add_argument(
        '--ocr',
        action='store_true',
        help='Enable OCR processing and data extraction'
    )
    process_group.add_argument(
        '--no-preprocessing',
        action='store_true',
        help='Disable image preprocessing'
    )
    process_group.add_argument(
        '--ocr-only',
        action='store_true',
        help='Run OCR without downloading (process cached images only)'
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
        if args.no_preprocessing:
            config.processing.use_opencv_preprocessing = False
        
        logger.info(f"Configuration loaded from: {config_manager.config_file or 'defaults'}")
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return 1
    
    # Handle listing and search commands
    if args.list_drive_folders or args.list_photos_albums or args.search_drive or args.search_photos:
        try:
            from src.services.image_processor import ImageProcessor
            processor = ImageProcessor(config, auth_manager)
            
            if args.list_drive_folders:
                folders = processor.list_available_drive_folders()
                print(f"\nFound {len(folders)} Google Drive folders:")
                for folder in folders[:20]:  # Limit to first 20
                    print(f"  {folder['id']} - {folder['name']}")
                if len(folders) > 20:
                    print(f"  ... and {len(folders) - 20} more")
            
            elif args.list_photos_albums:
                albums = processor.list_available_photos_albums()
                print(f"\nFound {len(albums)} Google Photos albums:")
                for album in albums[:20]:  # Limit to first 20
                    print(f"  {album['id']} - {album['title']}")
                if len(albums) > 20:
                    print(f"  ... and {len(albums) - 20} more")
            
            elif args.search_drive:
                folders = processor.search_drive_folders(args.search_drive)
                print(f"\nFound {len(folders)} Google Drive folders matching '{args.search_drive}':")
                for folder in folders:
                    print(f"  {folder['id']} - {folder['name']}")
            
            elif args.search_photos:
                albums = processor.search_photos_albums(args.search_photos)
                print(f"\nFound {len(albums)} Google Photos albums matching '{args.search_photos}':")
                for album in albums:
                    print(f"  {album['id']} - {album['title']}")
            
            return 0
            
        except Exception as e:
            logger.error(f"Listing/search failed: {str(e)}")
            print(f"ERROR: {str(e)}")
            return 1
    
    # Check if we have a source to process
    if not (config.google_drive_folder_id or config.google_photos_album_id):
        print("ERROR: No source specified!")
        print("Please specify either:")
        print("  --drive-folder <FOLDER_ID>")
        print("  --photos-album <ALBUM_ID>")
        print("Or configure in config file.")
        print()
        print("Use --list-drive-folders or --list-photos-albums to see available sources.")
        print("Run 'python main.py --help' for more options.")
        return 1
    
    # Check authentication
    auth_manager = GoogleAuthManager()
    if not auth_manager.is_authenticated():
        print("ERROR: Not authenticated with Google services!")
        print("Run 'python main.py --auth' to authenticate first.")
        return 1
    
    # Initialize image processor
    try:
        from src.services.image_processor import ImageProcessor
        processor = ImageProcessor(config, auth_manager)
        
        # Process images based on configuration
        results = None
        
        # Check OCR engine status
        if args.ocr:
            ocr_status = processor.get_ocr_engine_status()
            print(f"OCR Engine Status:")
            print(f"  Google Vision: {'✓' if ocr_status['google_vision_available'] else '✗'}")
            print(f"  Tesseract: {'✓' if ocr_status['tesseract_available'] else '✗'}")
            print(f"  Preprocessing: {'✓' if ocr_status['preprocessing_enabled'] else '✗'}")
            print()
        
        if config.google_drive_folder_id:
            if args.ocr:
                print(f"Processing Google Drive folder with OCR: {config.google_drive_folder_id}")
                results = processor.process_drive_folder_with_ocr(config.google_drive_folder_id)
            else:
                print(f"Processing Google Drive folder: {config.google_drive_folder_id}")
                results = processor.process_drive_folder(config.google_drive_folder_id)
        elif config.google_photos_album_id:
            if args.ocr:
                print(f"Processing Google Photos album with OCR: {config.google_photos_album_id}")
                results = processor.process_photos_album_with_ocr(config.google_photos_album_id)
            else:
                print(f"Processing Google Photos album: {config.google_photos_album_id}")
                results = processor.process_photos_album(config.google_photos_album_id)
        
        if results:
            # Display results
            print("\n" + "="*60)
            print("PROCESSING RESULTS")
            print("="*60)
            print(f"Source: {results['source_name']} ({results['source_type']})")
            print(f"Total files found: {results['total_files_found']}")
            print(f"Successfully processed: {results['processed_files']}")
            print(f"Skipped (cached): {results['skipped_files']}")
            print(f"Errors: {results['error_files']}")
            
            if results['duplicate_groups'] > 0:
                print(f"Duplicate groups found: {results['duplicate_groups']}")
            
            # Display OCR results if available
            if 'ocr_results' in results:
                print(f"OCR Success: {results['ocr_success_count']}/{len(results['ocr_results'])}")
                print(f"Valid receipts: {results['receipts_extracted']}")
                
                # Show summary of successful OCR results
                successful_ocr = [r for r in results['ocr_results'] if r.get('success')]
                if successful_ocr:
                    print(f"\nOCR Methods used:")
                    method_counts = {}
                    for r in successful_ocr:
                        method = r.get('ocr_method', 'unknown')
                        method_counts[method] = method_counts.get(method, 0) + 1
                    
                    for method, count in method_counts.items():
                        print(f"  {method}: {count}")
                    
                    # Show average confidence
                    avg_confidence = sum(r.get('ocr_confidence', 0) for r in successful_ocr) / len(successful_ocr)
                    print(f"Average OCR confidence: {avg_confidence:.1%}")
                    
                    # Show receipts with valid data
                    valid_receipts = [r for r in successful_ocr if r.get('receipt_data') and 
                                    r['receipt_data'].get('confidence_score', 0) >= config.processing.confidence_threshold]
                    
                    if valid_receipts:
                        print(f"\nValid Receipt Summary:")
                        total_amount = 0
                        merchants = set()
                        
                        for receipt in valid_receipts:
                            rd = receipt['receipt_data']
                            if rd.get('total_amount'):
                                try:
                                    total_amount += float(rd['total_amount'])
                                except (ValueError, TypeError):
                                    pass
                            if rd.get('merchant_name'):
                                merchants.add(rd['merchant_name'])
                        
                        print(f"  Total amount processed: ${total_amount:.2f}")
                        print(f"  Unique merchants: {len(merchants)}")
                        
                        if len(merchants) <= 5:
                            print(f"  Merchants: {', '.join(merchants)}")
            
            # Display cache stats
            cache_stats = processor.get_cache_stats()
            print(f"\nCache Usage: {cache_stats['mb_used']} MB / {cache_stats['max_size_mb']} MB ({cache_stats['usage_percent']}%)")
            print(f"Unique files: {cache_stats['unique_files']}, Duplicates: {cache_stats['duplicate_files']}")
            
            if args.ocr:
                print("\n✓ Phase 3 OCR processing completed successfully!")
                print("Next: Phase 4 will add spreadsheet export capabilities.")
            else:
                print("\n✓ Phase 2 processing completed successfully!")
                print("Next: Add --ocr flag to enable OCR and data extraction.")
        
        logger.info("Receipt Scanner Phase 2 completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        print(f"ERROR: Processing failed: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())