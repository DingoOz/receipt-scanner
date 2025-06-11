import io
import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from ..auth.google_auth import GoogleAuthManager


class GoogleDriveService:
    """Service for interacting with Google Drive API."""
    
    SUPPORTED_IMAGE_MIMES = {
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/tiff',
        'image/bmp',
        'image/webp'
    }
    
    def __init__(self, auth_manager: GoogleAuthManager):
        """
        Initialize Google Drive service.
        
        Args:
            auth_manager: Authenticated Google Auth Manager
        """
        self.auth_manager = auth_manager
        self.service = None
        self.logger = logging.getLogger(__name__)
        self._initialize_service()
    
    def _initialize_service(self) -> None:
        """Initialize the Google Drive service."""
        try:
            if not self.auth_manager.is_authenticated():
                raise RuntimeError("Not authenticated with Google services")
            
            self.service = self.auth_manager.get_drive_service()
            self.logger.info("Google Drive service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Drive service: {str(e)}")
            raise
    
    def list_folders(self, parent_folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List folders in Google Drive.
        
        Args:
            parent_folder_id: ID of parent folder (None for root)
            
        Returns:
            List of folder information dictionaries
        """
        try:
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, parents, createdTime, modifiedTime)"
            ).execute()
            
            folders = results.get('files', [])
            self.logger.info(f"Found {len(folders)} folders")
            return folders
            
        except HttpError as e:
            self.logger.error(f"Failed to list folders: {str(e)}")
            raise
    
    def list_images_in_folder(self, folder_id: str, page_size: int = 100) -> Generator[Dict[str, Any], None, None]:
        """
        List all image files in a Google Drive folder with pagination.
        
        Args:
            folder_id: Google Drive folder ID
            page_size: Number of files per page
            
        Yields:
            Dict containing file information
        """
        try:
            # Build query for image files in folder
            mime_query = " or ".join([f"mimeType='{mime}'" for mime in self.SUPPORTED_IMAGE_MIMES])
            query = f"({mime_query}) and '{folder_id}' in parents and trashed=false"
            
            page_token = None
            total_files = 0
            
            while True:
                results = self.service.files().list(
                    q=query,
                    pageSize=page_size,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, size, mimeType, createdTime, modifiedTime, md5Checksum)"
                ).execute()
                
                files = results.get('files', [])
                if not files:
                    break
                
                for file_info in files:
                    total_files += 1
                    yield file_info
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"Found {total_files} image files in folder {folder_id}")
            
        except HttpError as e:
            self.logger.error(f"Failed to list images in folder {folder_id}: {str(e)}")
            raise
    
    def get_folder_info(self, folder_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific folder.
        
        Args:
            folder_id: Google Drive folder ID
            
        Returns:
            Dictionary with folder information or None if not found
        """
        try:
            file_info = self.service.files().get(
                fileId=folder_id,
                fields="id, name, parents, createdTime, modifiedTime, mimeType"
            ).execute()
            
            # Verify it's actually a folder
            if file_info.get('mimeType') != 'application/vnd.google-apps.folder':
                self.logger.warning(f"File {folder_id} is not a folder")
                return None
            
            return file_info
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"Folder {folder_id} not found")
                return None
            else:
                self.logger.error(f"Failed to get folder info for {folder_id}: {str(e)}")
                raise
    
    def download_file(self, file_id: str, output_path: Path) -> bool:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            output_path: Local path to save the file
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            # Get file metadata first
            file_metadata = self.service.files().get(fileId=file_id).execute()
            
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    self.logger.debug(f"Download progress: {progress}%")
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(file_io.getvalue())
            
            self.logger.debug(f"Downloaded {file_metadata['name']} to {output_path}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Failed to download file {file_id}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error downloading file {file_id}: {str(e)}")
            return False
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dictionary with file information or None if not found
        """
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields="id, name, size, mimeType, createdTime, modifiedTime, md5Checksum, parents"
            ).execute()
            
            return file_info
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"File {file_id} not found")
                return None
            else:
                self.logger.error(f"Failed to get file info for {file_id}: {str(e)}")
                raise
    
    def search_folders_by_name(self, folder_name: str) -> List[Dict[str, Any]]:
        """
        Search for folders by name.
        
        Args:
            folder_name: Name to search for
            
        Returns:
            List of matching folder information
        """
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name contains '{folder_name}' and trashed=false"
            
            results = self.service.files().list(
                q=query,
                pageSize=50,
                fields="nextPageToken, files(id, name, parents, createdTime, modifiedTime)"
            ).execute()
            
            folders = results.get('files', [])
            self.logger.info(f"Found {len(folders)} folders matching '{folder_name}'")
            return folders
            
        except HttpError as e:
            self.logger.error(f"Failed to search folders: {str(e)}")
            raise
    
    def get_folder_size_info(self, folder_id: str) -> Dict[str, Any]:
        """
        Get size information for a folder.
        
        Args:
            folder_id: Google Drive folder ID
            
        Returns:
            Dictionary with size information
        """
        try:
            total_files = 0
            total_size = 0
            image_files = 0
            
            for file_info in self.list_images_in_folder(folder_id):
                total_files += 1
                if file_info.get('mimeType') in self.SUPPORTED_IMAGE_MIMES:
                    image_files += 1
                
                size = file_info.get('size')
                if size:
                    total_size += int(size)
            
            return {
                'total_files': total_files,
                'image_files': image_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get folder size info: {str(e)}")
            raise