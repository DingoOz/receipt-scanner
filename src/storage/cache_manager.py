import os
import json
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from ..utils.config import StorageConfig


class CacheManager:
    """Manages local caching of downloaded images and metadata."""
    
    def __init__(self, config: StorageConfig):
        """
        Initialize cache manager.
        
        Args:
            config: Storage configuration
        """
        self.config = config
        self.cache_dir = Path(config.cache_directory)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.images_dir = self.cache_dir / 'images'
        self.metadata_dir = self.cache_dir / 'metadata'
        self.images_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Cache index file
        self.index_file = self.cache_dir / 'cache_index.json'
        self.cache_index = self._load_cache_index()
        
        self.logger = logging.getLogger(__name__)
    
    def _load_cache_index(self) -> Dict[str, Any]:
        """Load cache index from file."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache index: {str(e)}")
        
        # Default cache index structure
        return {
            'files': {},  # file_id -> cache info
            'hashes': {},  # content_hash -> file_id
            'stats': {
                'total_files': 0,
                'total_size_bytes': 0,
                'last_cleanup': None
            }
        }
    
    def _save_cache_index(self) -> None:
        """Save cache index to file."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cache index: {str(e)}")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate MD5 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: MD5 hash of file content
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to calculate hash for {file_path}: {str(e)}")
            raise
    
    def get_cached_file_path(self, file_id: str, original_name: str) -> Path:
        """
        Get the local cache path for a file.
        
        Args:
            file_id: Unique file identifier
            original_name: Original filename
            
        Returns:
            Path: Local cache file path
        """
        # Use file extension from original name
        extension = Path(original_name).suffix.lower()
        if not extension:
            extension = '.jpg'  # Default extension
        
        # Create filename with file_id and extension
        cache_filename = f"{file_id}{extension}"
        return self.images_dir / cache_filename
    
    def is_file_cached(self, file_id: str) -> bool:
        """
        Check if a file is already cached.
        
        Args:
            file_id: File identifier
            
        Returns:
            bool: True if file is cached
        """
        return file_id in self.cache_index['files']
    
    def get_cached_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached file information.
        
        Args:
            file_id: File identifier
            
        Returns:
            Dict with cached file info or None if not cached
        """
        return self.cache_index['files'].get(file_id)
    
    def add_file_to_cache(self, file_id: str, source_path: Path, metadata: Dict[str, Any]) -> bool:
        """
        Add a file to the cache.
        
        Args:
            file_id: Unique file identifier
            source_path: Path to source file
            metadata: File metadata
            
        Returns:
            bool: True if successful
        """
        try:
            # Calculate file hash
            file_hash = self.calculate_file_hash(source_path)
            
            # Check for duplicate based on hash
            if file_hash in self.cache_index['hashes']:
                existing_file_id = self.cache_index['hashes'][file_hash]
                self.logger.info(f"File {file_id} is duplicate of {existing_file_id}")
                
                # Update metadata to point to existing file
                self.cache_index['files'][file_id] = {
                    'original_file_id': file_id,
                    'cache_file_id': existing_file_id,
                    'is_duplicate': True,
                    'content_hash': file_hash,
                    'cached_at': datetime.now().isoformat(),
                    'metadata': metadata
                }
                self._save_cache_index()
                return True
            
            # Get cache file path
            original_name = metadata.get('name', f"{file_id}.jpg")
            cache_path = self.get_cached_file_path(file_id, original_name)
            
            # Copy file to cache
            shutil.copy2(source_path, cache_path)
            
            # Get file size
            file_size = cache_path.stat().st_size
            
            # Update cache index
            cache_info = {
                'original_file_id': file_id,
                'cache_file_id': file_id,
                'cache_path': str(cache_path),
                'content_hash': file_hash,
                'file_size': file_size,
                'cached_at': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'is_duplicate': False,
                'metadata': metadata
            }
            
            self.cache_index['files'][file_id] = cache_info
            self.cache_index['hashes'][file_hash] = file_id
            self.cache_index['stats']['total_files'] += 1
            self.cache_index['stats']['total_size_bytes'] += file_size
            
            self._save_cache_index()
            
            self.logger.debug(f"Added file {file_id} to cache: {cache_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add file {file_id} to cache: {str(e)}")
            return False
    
    def get_cached_file_path_by_id(self, file_id: str) -> Optional[Path]:
        """
        Get the cached file path for a file ID.
        
        Args:
            file_id: File identifier
            
        Returns:
            Path to cached file or None if not cached
        """
        cache_info = self.get_cached_file_info(file_id)
        if not cache_info:
            return None
        
        # Handle duplicates
        if cache_info.get('is_duplicate'):
            actual_file_id = cache_info['cache_file_id']
            actual_cache_info = self.get_cached_file_info(actual_file_id)
            if actual_cache_info:
                cache_path = Path(actual_cache_info['cache_path'])
            else:
                return None
        else:
            cache_path = Path(cache_info['cache_path'])
        
        # Verify file exists
        if cache_path.exists():
            # Update last accessed time
            self.cache_index['files'][file_id]['last_accessed'] = datetime.now().isoformat()
            self._save_cache_index()
            return cache_path
        else:
            # File was deleted, remove from cache
            self.remove_file_from_cache(file_id)
            return None
    
    def remove_file_from_cache(self, file_id: str) -> bool:
        """
        Remove a file from cache.
        
        Args:
            file_id: File identifier
            
        Returns:
            bool: True if successful
        """
        try:
            cache_info = self.get_cached_file_info(file_id)
            if not cache_info:
                return True  # Already not in cache
            
            # Remove physical file if not a duplicate
            if not cache_info.get('is_duplicate'):
                cache_path = Path(cache_info['cache_path'])
                if cache_path.exists():
                    cache_path.unlink()
                
                # Remove hash reference
                content_hash = cache_info['content_hash']
                if content_hash in self.cache_index['hashes']:
                    del self.cache_index['hashes'][content_hash]
                
                # Update stats
                self.cache_index['stats']['total_files'] -= 1
                self.cache_index['stats']['total_size_bytes'] -= cache_info.get('file_size', 0)
            
            # Remove from index
            del self.cache_index['files'][file_id]
            self._save_cache_index()
            
            self.logger.debug(f"Removed file {file_id} from cache")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove file {file_id} from cache: {str(e)}")
            return False
    
    def cleanup_cache(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old cache files.
        
        Args:
            max_age_days: Maximum age of files to keep
            
        Returns:
            Dict with cleanup statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            files_removed = 0
            bytes_freed = 0
            
            files_to_remove = []
            
            for file_id, cache_info in self.cache_index['files'].items():
                cached_at = datetime.fromisoformat(cache_info['cached_at'])
                if cached_at < cutoff_date:
                    files_to_remove.append(file_id)
            
            for file_id in files_to_remove:
                cache_info = self.cache_index['files'][file_id]
                if self.remove_file_from_cache(file_id):
                    files_removed += 1
                    bytes_freed += cache_info.get('file_size', 0)
            
            # Update cleanup timestamp
            self.cache_index['stats']['last_cleanup'] = datetime.now().isoformat()
            self._save_cache_index()
            
            cleanup_stats = {
                'files_removed': files_removed,
                'bytes_freed': bytes_freed,
                'mb_freed': round(bytes_freed / (1024 * 1024), 2)
            }
            
            self.logger.info(f"Cache cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {str(e)}")
            return {'files_removed': 0, 'bytes_freed': 0, 'mb_freed': 0}
    
    def enforce_cache_size_limit(self) -> Dict[str, Any]:
        """
        Enforce cache size limit by removing least recently accessed files.
        
        Returns:
            Dict with enforcement statistics
        """
        try:
            max_size_bytes = self.config.max_cache_size_mb * 1024 * 1024
            current_size = self.cache_index['stats']['total_size_bytes']
            
            if current_size <= max_size_bytes:
                return {'files_removed': 0, 'bytes_freed': 0, 'mb_freed': 0}
            
            # Sort files by last accessed time (oldest first)
            file_items = []
            for file_id, cache_info in self.cache_index['files'].items():
                if not cache_info.get('is_duplicate'):  # Only consider non-duplicates
                    last_accessed = datetime.fromisoformat(cache_info.get('last_accessed', cache_info['cached_at']))
                    file_items.append((last_accessed, file_id, cache_info.get('file_size', 0)))
            
            file_items.sort()  # Sort by timestamp (oldest first)
            
            files_removed = 0
            bytes_freed = 0
            
            for last_accessed, file_id, file_size in file_items:
                if current_size - bytes_freed <= max_size_bytes:
                    break
                
                if self.remove_file_from_cache(file_id):
                    files_removed += 1
                    bytes_freed += file_size
            
            enforcement_stats = {
                'files_removed': files_removed,
                'bytes_freed': bytes_freed,
                'mb_freed': round(bytes_freed / (1024 * 1024), 2)
            }
            
            self.logger.info(f"Cache size limit enforced: {enforcement_stats}")
            return enforcement_stats
            
        except Exception as e:
            self.logger.error(f"Cache size enforcement failed: {str(e)}")
            return {'files_removed': 0, 'bytes_freed': 0, 'mb_freed': 0}
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache statistics
        """
        stats = self.cache_index['stats'].copy()
        stats['mb_used'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        stats['max_size_mb'] = self.config.max_cache_size_mb
        stats['usage_percent'] = round((stats['total_size_bytes'] / (self.config.max_cache_size_mb * 1024 * 1024)) * 100, 1)
        
        # Count duplicates
        duplicate_count = sum(1 for info in self.cache_index['files'].values() if info.get('is_duplicate'))
        stats['duplicate_files'] = duplicate_count
        stats['unique_files'] = stats['total_files'] - duplicate_count
        
        return stats
    
    def list_cached_files(self) -> List[Dict[str, Any]]:
        """
        List all cached files with their information.
        
        Returns:
            List of cached file information
        """
        cached_files = []
        
        for file_id, cache_info in self.cache_index['files'].items():
            file_info = {
                'file_id': file_id,
                'original_name': cache_info['metadata'].get('name', 'Unknown'),
                'file_size': cache_info.get('file_size', 0),
                'cached_at': cache_info['cached_at'],
                'last_accessed': cache_info.get('last_accessed', cache_info['cached_at']),
                'is_duplicate': cache_info.get('is_duplicate', False),
                'content_hash': cache_info['content_hash']
            }
            cached_files.append(file_info)
        
        return cached_files