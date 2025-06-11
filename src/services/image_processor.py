import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..auth.google_auth import GoogleAuthManager
from ..services.drive_service import GoogleDriveService
from ..services.photos_service import GooglePhotosService
from ..storage.cache_manager import CacheManager
from ..storage.duplicate_detector import DuplicateDetector
from ..utils.config import AppConfig


class ImageProcessor:
    """Main processor for handling image download and management from Google services."""
    
    def __init__(self, config: AppConfig, auth_manager: GoogleAuthManager):
        """
        Initialize image processor.
        
        Args:
            config: Application configuration
            auth_manager: Authenticated Google Auth Manager
        """
        self.config = config
        self.auth_manager = auth_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize services
        self.drive_service = GoogleDriveService(auth_manager)
        self.photos_service = GooglePhotosService(auth_manager)
        self.cache_manager = CacheManager(config.storage)
        self.duplicate_detector = DuplicateDetector(config.storage)
    
    def process_drive_folder(self, folder_id: str) -> Dict[str, Any]:
        """
        Process all images in a Google Drive folder.
        
        Args:
            folder_id: Google Drive folder ID
            
        Returns:
            Dict with processing results
        """
        try:
            self.logger.info(f"Starting processing of Google Drive folder: {folder_id}")
            
            # Get folder information
            folder_info = self.drive_service.get_folder_info(folder_id)
            if not folder_info:
                raise ValueError(f"Folder {folder_id} not found or inaccessible")
            
            self.logger.info(f"Processing folder: {folder_info['name']}")
            
            # Get folder size info
            size_info = self.drive_service.get_folder_size_info(folder_id)
            self.logger.info(f"Folder contains {size_info['image_files']} images ({size_info['total_size_mb']} MB)")
            
            # Process images
            processed_files = []
            skipped_files = []
            error_files = []
            
            for file_info in self.drive_service.list_images_in_folder(folder_id):
                result = self._process_single_drive_file(file_info)
                
                if result['status'] == 'processed':
                    processed_files.append(result)
                elif result['status'] == 'skipped':
                    skipped_files.append(result)
                else:
                    error_files.append(result)
            
            # Find duplicates if enabled
            duplicates = []
            if not self.config.processing.confidence_threshold:  # Using this as a proxy for skip duplicates
                cache_files = [{'file_id': f['file_id'], 'cache_path': f['cache_path']} for f in processed_files if f.get('cache_path')]
                if len(cache_files) > 1:
                    duplicate_matches = self.duplicate_detector.find_duplicates_in_batch(cache_files)
                    duplicates = self.duplicate_detector.get_duplicate_groups(duplicate_matches)
            
            results = {
                'source_type': 'google_drive',
                'source_id': folder_id,
                'source_name': folder_info['name'],
                'total_files_found': size_info['image_files'],
                'processed_files': len(processed_files),
                'skipped_files': len(skipped_files),
                'error_files': len(error_files),
                'duplicate_groups': len(duplicates),
                'files': processed_files,
                'skipped': skipped_files,
                'errors': error_files,
                'duplicates': duplicates
            }
            
            self.logger.info(f"Completed processing: {len(processed_files)} processed, {len(skipped_files)} skipped, {len(error_files)} errors")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to process Drive folder {folder_id}: {str(e)}")
            raise
    
    def process_photos_album(self, album_id: str) -> Dict[str, Any]:
        """
        Process all images in a Google Photos album.
        
        Args:
            album_id: Google Photos album ID
            
        Returns:
            Dict with processing results
        """
        try:
            self.logger.info(f"Starting processing of Google Photos album: {album_id}")
            
            # Get album information
            album_info = self.photos_service.get_album_info(album_id)
            if not album_info:
                raise ValueError(f"Album {album_id} not found or inaccessible")
            
            self.logger.info(f"Processing album: {album_info['title']}")
            
            # Get album size info
            size_info = self.photos_service.get_album_size_info(album_id)
            self.logger.info(f"Album contains {size_info['image_items']} images")
            
            # Process images
            processed_files = []
            skipped_files = []
            error_files = []
            
            for media_item in self.photos_service.list_media_items_in_album(album_id):
                result = self._process_single_photos_item(media_item)
                
                if result['status'] == 'processed':
                    processed_files.append(result)
                elif result['status'] == 'skipped':
                    skipped_files.append(result)
                else:
                    error_files.append(result)
            
            # Find duplicates if enabled
            duplicates = []
            if not self.config.processing.confidence_threshold:  # Using this as a proxy for skip duplicates
                cache_files = [{'file_id': f['file_id'], 'cache_path': f['cache_path']} for f in processed_files if f.get('cache_path')]
                if len(cache_files) > 1:
                    duplicate_matches = self.duplicate_detector.find_duplicates_in_batch(cache_files)
                    duplicates = self.duplicate_detector.get_duplicate_groups(duplicate_matches)
            
            results = {
                'source_type': 'google_photos',
                'source_id': album_id,
                'source_name': album_info['title'],
                'total_files_found': size_info['image_items'],
                'processed_files': len(processed_files),
                'skipped_files': len(skipped_files),
                'error_files': len(error_files),
                'duplicate_groups': len(duplicates),
                'files': processed_files,
                'skipped': skipped_files,
                'errors': error_files,
                'duplicates': duplicates
            }
            
            self.logger.info(f"Completed processing: {len(processed_files)} processed, {len(skipped_files)} skipped, {len(error_files)} errors")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to process Photos album {album_id}: {str(e)}")
            raise
    
    def _process_single_drive_file(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single file from Google Drive.
        
        Args:
            file_info: File information from Drive API
            
        Returns:
            Dict with processing result
        """
        file_id = file_info['id']
        file_name = file_info['name']
        
        try:
            # Check if already cached
            if self.cache_manager.is_file_cached(file_id):
                cached_path = self.cache_manager.get_cached_file_path_by_id(file_id)
                if cached_path and cached_path.exists():
                    return {
                        'status': 'skipped',
                        'reason': 'already_cached',
                        'file_id': file_id,
                        'file_name': file_name,
                        'cache_path': str(cached_path)
                    }
            
            # Download to temporary file first
            with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix, delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            if not self.drive_service.download_file(file_id, temp_path):
                return {
                    'status': 'error',
                    'reason': 'download_failed',
                    'file_id': file_id,
                    'file_name': file_name
                }
            
            # Add to cache
            if self.cache_manager.add_file_to_cache(file_id, temp_path, file_info):
                cached_path = self.cache_manager.get_cached_file_path_by_id(file_id)
                
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
                return {
                    'status': 'processed',
                    'file_id': file_id,
                    'file_name': file_name,
                    'cache_path': str(cached_path),
                    'file_size': file_info.get('size', 0),
                    'created_time': file_info.get('createdTime'),
                    'modified_time': file_info.get('modifiedTime')
                }
            else:
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
                return {
                    'status': 'error',
                    'reason': 'cache_failed',
                    'file_id': file_id,
                    'file_name': file_name
                }
            
        except Exception as e:
            self.logger.error(f"Failed to process Drive file {file_id}: {str(e)}")
            return {
                'status': 'error',
                'reason': f'exception: {str(e)}',
                'file_id': file_id,
                'file_name': file_name
            }
    
    def _process_single_photos_item(self, media_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single media item from Google Photos.
        
        Args:
            media_item: Media item from Photos API
            
        Returns:
            Dict with processing result
        """
        item_id = media_item['id']
        item_name = media_item.get('filename', f"photo_{item_id}.jpg")
        
        try:
            # Check if already cached
            if self.cache_manager.is_file_cached(item_id):
                cached_path = self.cache_manager.get_cached_file_path_by_id(item_id)
                if cached_path and cached_path.exists():
                    return {
                        'status': 'skipped',
                        'reason': 'already_cached',
                        'file_id': item_id,
                        'file_name': item_name,
                        'cache_path': str(cached_path)
                    }
            
            # Download to temporary file first
            with tempfile.NamedTemporaryFile(suffix=Path(item_name).suffix, delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            if not self.photos_service.download_media_item(media_item, temp_path, self.config.processing.max_image_size):
                return {
                    'status': 'error',
                    'reason': 'download_failed',
                    'file_id': item_id,
                    'file_name': item_name
                }
            
            # Create metadata for Photos item
            photos_metadata = {
                'id': item_id,
                'name': item_name,
                'mimeType': media_item.get('mimeType', 'image/jpeg'),
                'creationTime': media_item.get('mediaMetadata', {}).get('creationTime'),
                'width': media_item.get('mediaMetadata', {}).get('width'),
                'height': media_item.get('mediaMetadata', {}).get('height')
            }
            
            # Add to cache
            if self.cache_manager.add_file_to_cache(item_id, temp_path, photos_metadata):
                cached_path = self.cache_manager.get_cached_file_path_by_id(item_id)
                
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
                return {
                    'status': 'processed',
                    'file_id': item_id,
                    'file_name': item_name,
                    'cache_path': str(cached_path),
                    'creation_time': photos_metadata.get('creationTime'),
                    'dimensions': f"{photos_metadata.get('width', 0)}x{photos_metadata.get('height', 0)}"
                }
            else:
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
                return {
                    'status': 'error',
                    'reason': 'cache_failed',
                    'file_id': item_id,
                    'file_name': item_name
                }
            
        except Exception as e:
            self.logger.error(f"Failed to process Photos item {item_id}: {str(e)}")
            return {
                'status': 'error',
                'reason': f'exception: {str(e)}',
                'file_id': item_id,
                'file_name': item_name
            }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()
    
    def cleanup_cache(self, max_age_days: int = 30) -> Dict[str, Any]:
        """Clean up old cache files."""
        return self.cache_manager.cleanup_cache(max_age_days)
    
    def list_available_drive_folders(self) -> List[Dict[str, Any]]:
        """List available Google Drive folders."""
        return self.drive_service.list_folders()
    
    def list_available_photos_albums(self) -> List[Dict[str, Any]]:
        """List available Google Photos albums."""
        return self.photos_service.list_albums()
    
    def search_drive_folders(self, name: str) -> List[Dict[str, Any]]:
        """Search for Drive folders by name."""
        return self.drive_service.search_folders_by_name(name)
    
    def search_photos_albums(self, title: str) -> List[Dict[str, Any]]:
        """Search for Photos albums by title."""
        return self.photos_service.search_albums_by_title(title)