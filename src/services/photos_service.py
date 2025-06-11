import io
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
from urllib.parse import urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..auth.google_auth import GoogleAuthManager


class GooglePhotosService:
    """Service for interacting with Google Photos Library API."""
    
    def __init__(self, auth_manager: GoogleAuthManager):
        """
        Initialize Google Photos service.
        
        Args:
            auth_manager: Authenticated Google Auth Manager
        """
        self.auth_manager = auth_manager
        self.service = None
        self.logger = logging.getLogger(__name__)
        self._initialize_service()
    
    def _initialize_service(self) -> None:
        """Initialize the Google Photos service."""
        try:
            if not self.auth_manager.is_authenticated():
                raise RuntimeError("Not authenticated with Google services")
            
            self.service = self.auth_manager.get_photos_service()
            self.logger.info("Google Photos service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Photos service: {str(e)}")
            raise
    
    def list_albums(self, page_size: int = 50) -> List[Dict[str, Any]]:
        """
        List all albums in Google Photos.
        
        Args:
            page_size: Number of albums per page
            
        Returns:
            List of album information dictionaries
        """
        try:
            albums = []
            page_token = None
            
            while True:
                request_body = {'pageSize': page_size}
                if page_token:
                    request_body['pageToken'] = page_token
                
                response = self.service.albums().list(**request_body).execute()
                
                batch_albums = response.get('albums', [])
                albums.extend(batch_albums)
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"Found {len(albums)} albums")
            return albums
            
        except HttpError as e:
            self.logger.error(f"Failed to list albums: {str(e)}")
            raise
    
    def get_album_info(self, album_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific album.
        
        Args:
            album_id: Google Photos album ID
            
        Returns:
            Dictionary with album information or None if not found
        """
        try:
            album = self.service.albums().get(albumId=album_id).execute()
            return album
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"Album {album_id} not found")
                return None
            else:
                self.logger.error(f"Failed to get album info for {album_id}: {str(e)}")
                raise
    
    def list_media_items_in_album(self, album_id: str, page_size: int = 100) -> Generator[Dict[str, Any], None, None]:
        """
        List all media items in a Google Photos album with pagination.
        
        Args:
            album_id: Google Photos album ID
            page_size: Number of items per page
            
        Yields:
            Dict containing media item information
        """
        try:
            page_token = None
            total_items = 0
            
            while True:
                request_body = {
                    'albumId': album_id,
                    'pageSize': page_size
                }
                if page_token:
                    request_body['pageToken'] = page_token
                
                response = self.service.mediaItems().search(body=request_body).execute()
                
                media_items = response.get('mediaItems', [])
                if not media_items:
                    break
                
                for item in media_items:
                    # Only yield image items
                    if self._is_image_item(item):
                        total_items += 1
                        yield item
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"Found {total_items} image items in album {album_id}")
            
        except HttpError as e:
            self.logger.error(f"Failed to list media items in album {album_id}: {str(e)}")
            raise
    
    def _is_image_item(self, media_item: Dict[str, Any]) -> bool:
        """
        Check if a media item is an image.
        
        Args:
            media_item: Media item dictionary
            
        Returns:
            bool: True if item is an image
        """
        metadata = media_item.get('mediaMetadata', {})
        return 'photo' in metadata
    
    def download_media_item(self, media_item: Dict[str, Any], output_path: Path, max_size: int = 2048) -> bool:
        """
        Download a media item from Google Photos.
        
        Args:
            media_item: Media item dictionary from API
            output_path: Local path to save the file
            max_size: Maximum dimension for download (pixels)
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            # Get download URL with size parameter
            base_url = media_item.get('baseUrl')
            if not base_url:
                self.logger.error(f"No base URL for media item {media_item.get('id')}")
                return False
            
            # Add size parameter to get resized image
            download_url = f"{base_url}=w{max_size}-h{max_size}"
            
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the image
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            # Write to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.debug(f"Downloaded {media_item.get('filename', 'Unknown')} to {output_path}")
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to download media item: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error downloading media item: {str(e)}")
            return False
    
    def get_media_item_info(self, media_item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific media item.
        
        Args:
            media_item_id: Google Photos media item ID
            
        Returns:
            Dictionary with media item information or None if not found
        """
        try:
            media_item = self.service.mediaItems().get(mediaItemId=media_item_id).execute()
            return media_item
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"Media item {media_item_id} not found")
                return None
            else:
                self.logger.error(f"Failed to get media item info for {media_item_id}: {str(e)}")
                raise
    
    def search_albums_by_title(self, title: str) -> List[Dict[str, Any]]:
        """
        Search for albums by title.
        
        Args:
            title: Title to search for
            
        Returns:
            List of matching album information
        """
        try:
            all_albums = self.list_albums()
            matching_albums = []
            
            for album in all_albums:
                album_title = album.get('title', '').lower()
                if title.lower() in album_title:
                    matching_albums.append(album)
            
            self.logger.info(f"Found {len(matching_albums)} albums matching '{title}'")
            return matching_albums
            
        except Exception as e:
            self.logger.error(f"Failed to search albums: {str(e)}")
            raise
    
    def get_album_size_info(self, album_id: str) -> Dict[str, Any]:
        """
        Get size information for an album.
        
        Args:
            album_id: Google Photos album ID
            
        Returns:
            Dictionary with size information
        """
        try:
            # Get album info first
            album_info = self.get_album_info(album_id)
            if not album_info:
                raise ValueError(f"Album {album_id} not found")
            
            # Count media items
            total_items = 0
            image_items = 0
            
            for media_item in self.list_media_items_in_album(album_id):
                total_items += 1
                if self._is_image_item(media_item):
                    image_items += 1
            
            return {
                'album_title': album_info.get('title', 'Unknown'),
                'total_items': total_items,
                'image_items': image_items,
                'media_items_count': album_info.get('mediaItemsCount', 'Unknown'),
                'is_writable': album_info.get('isWriteable', False)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get album size info: {str(e)}")
            raise
    
    def list_recent_media_items(self, days: int = 30, page_size: int = 100) -> Generator[Dict[str, Any], None, None]:
        """
        List recent media items (images only).
        
        Args:
            days: Number of days to look back
            page_size: Number of items per page
            
        Yields:
            Dict containing media item information
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            page_token = None
            total_items = 0
            
            while True:
                request_body = {
                    'pageSize': page_size,
                    'filters': {
                        'dateFilter': {
                            'ranges': [{
                                'startDate': {
                                    'year': start_date.year,
                                    'month': start_date.month,
                                    'day': start_date.day
                                },
                                'endDate': {
                                    'year': end_date.year,
                                    'month': end_date.month,
                                    'day': end_date.day
                                }
                            }]
                        },
                        'mediaTypeFilter': {
                            'mediaTypes': ['PHOTO']
                        }
                    }
                }
                
                if page_token:
                    request_body['pageToken'] = page_token
                
                response = self.service.mediaItems().search(body=request_body).execute()
                
                media_items = response.get('mediaItems', [])
                if not media_items:
                    break
                
                for item in media_items:
                    total_items += 1
                    yield item
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"Found {total_items} recent image items from last {days} days")
            
        except HttpError as e:
            self.logger.error(f"Failed to list recent media items: {str(e)}")
            raise