import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from ..utils.config import StorageConfig


@dataclass
class DuplicateMatch:
    """Information about a duplicate match."""
    file_id_1: str
    file_id_2: str
    similarity_score: float
    method: str
    metadata_1: Dict[str, Any]
    metadata_2: Dict[str, Any]


class DuplicateDetector:
    """Detects duplicate images using various comparison methods."""
    
    def __init__(self, config: StorageConfig):
        """
        Initialize duplicate detector.
        
        Args:
            config: Storage configuration
        """
        self.config = config
        self.threshold = config.duplicate_threshold
        self.logger = logging.getLogger(__name__)
    
    def calculate_image_hash(self, image_path: Path, method: str = 'phash') -> Optional[str]:
        """
        Calculate perceptual hash of an image.
        
        Args:
            image_path: Path to image file
            method: Hash method ('phash', 'dhash', 'whash')
            
        Returns:
            str: Hex string of image hash or None if failed
        """
        try:
            # Read image
            image = cv2.imread(str(image_path))
            if image is None:
                self.logger.warning(f"Could not read image: {image_path}")
                return None
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            if method == 'phash':
                return self._perceptual_hash(gray)
            elif method == 'dhash':
                return self._difference_hash(gray)
            elif method == 'whash':
                return self._wavelet_hash(gray)
            else:
                raise ValueError(f"Unknown hash method: {method}")
                
        except Exception as e:
            self.logger.error(f"Failed to calculate image hash for {image_path}: {str(e)}")
            return None
    
    def _perceptual_hash(self, gray_image: np.ndarray, hash_size: int = 8) -> str:
        """
        Calculate perceptual hash (pHash).
        
        Args:
            gray_image: Grayscale image array
            hash_size: Size of hash matrix
            
        Returns:
            str: Hex string of perceptual hash
        """
        # Resize image
        resized = cv2.resize(gray_image, (hash_size * 4, hash_size * 4))
        
        # Apply DCT (Discrete Cosine Transform)
        dct = cv2.dct(np.float32(resized))
        
        # Extract top-left corner (low frequencies)
        dct_low = dct[:hash_size, :hash_size]
        
        # Calculate median
        median = np.median(dct_low)
        
        # Create binary hash
        binary_hash = dct_low > median
        
        # Convert to hex string
        return self._binary_array_to_hex(binary_hash)
    
    def _difference_hash(self, gray_image: np.ndarray, hash_size: int = 8) -> str:
        """
        Calculate difference hash (dHash).
        
        Args:
            gray_image: Grayscale image array
            hash_size: Size of hash matrix
            
        Returns:
            str: Hex string of difference hash
        """
        # Resize to hash_size+1 x hash_size
        resized = cv2.resize(gray_image, (hash_size + 1, hash_size))
        
        # Calculate horizontal differences
        diff = resized[:, 1:] > resized[:, :-1]
        
        # Convert to hex string
        return self._binary_array_to_hex(diff)
    
    def _wavelet_hash(self, gray_image: np.ndarray, hash_size: int = 8) -> str:
        """
        Calculate wavelet hash (simplified version).
        
        Args:
            gray_image: Grayscale image array
            hash_size: Size of hash matrix
            
        Returns:
            str: Hex string of wavelet hash
        """
        # Resize image
        resized = cv2.resize(gray_image, (hash_size * 2, hash_size * 2))
        
        # Simple wavelet-like transform using blur difference
        blurred = cv2.GaussianBlur(resized, (5, 5), 0)
        diff = resized.astype(np.float32) - blurred.astype(np.float32)
        
        # Resize to final hash size
        final = cv2.resize(diff, (hash_size, hash_size))
        
        # Create binary hash based on median
        median = np.median(final)
        binary_hash = final > median
        
        # Convert to hex string
        return self._binary_array_to_hex(binary_hash)
    
    def _binary_array_to_hex(self, binary_array: np.ndarray) -> str:
        """
        Convert binary array to hex string.
        
        Args:
            binary_array: Boolean numpy array
            
        Returns:
            str: Hex string representation
        """
        # Flatten array and convert to binary string
        binary_string = ''.join(['1' if x else '0' for x in binary_array.flatten()])
        
        # Convert to integer and then to hex
        decimal_value = int(binary_string, 2)
        hex_string = hex(decimal_value)[2:]  # Remove '0x' prefix
        
        return hex_string
    
    def calculate_hash_similarity(self, hash1: str, hash2: str) -> float:
        """
        Calculate similarity between two image hashes.
        
        Args:
            hash1: First image hash
            hash2: Second image hash
            
        Returns:
            float: Similarity score (0.0 to 1.0)
        """
        try:
            # Convert hex strings to integers
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
            
            # Calculate Hamming distance
            xor = int1 ^ int2
            hamming_distance = bin(xor).count('1')
            
            # Convert to similarity (assuming 64-bit hash)
            max_distance = 64  # For 8x8 hash
            similarity = 1.0 - (hamming_distance / max_distance)
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            self.logger.error(f"Failed to calculate hash similarity: {str(e)}")
            return 0.0
    
    def compare_images_structural(self, image_path1: Path, image_path2: Path) -> float:
        """
        Compare images using Structural Similarity Index (SSIM).
        
        Args:
            image_path1: Path to first image
            image_path2: Path to second image
            
        Returns:
            float: SSIM similarity score (0.0 to 1.0)
        """
        try:
            # Read images
            img1 = cv2.imread(str(image_path1), cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(str(image_path2), cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Resize to same dimensions
            height = min(img1.shape[0], img2.shape[0])
            width = min(img1.shape[1], img2.shape[1])
            
            img1 = cv2.resize(img1, (width, height))
            img2 = cv2.resize(img2, (width, height))
            
            # Calculate SSIM using OpenCV (simplified version)
            # Note: For production, consider using skimage.metrics.structural_similarity
            diff = cv2.absdiff(img1, img2)
            mse = np.mean(diff ** 2)
            
            if mse == 0:
                return 1.0
            
            # Simple SSIM approximation
            max_pixel = 255.0
            psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
            ssim_approx = min(1.0, psnr / 50.0)  # Normalize to 0-1
            
            return max(0.0, ssim_approx)
            
        except Exception as e:
            self.logger.error(f"Failed to compare images structurally: {str(e)}")
            return 0.0
    
    def find_duplicates_in_batch(self, file_info_list: List[Dict[str, Any]]) -> List[DuplicateMatch]:
        """
        Find duplicates in a batch of files.
        
        Args:
            file_info_list: List of file information dictionaries
            
        Returns:
            List of duplicate matches
        """
        duplicates = []
        file_hashes = {}
        
        # Calculate hashes for all files
        for file_info in file_info_list:
            file_id = file_info['file_id']
            image_path = Path(file_info['cache_path'])
            
            if not image_path.exists():
                continue
            
            # Calculate perceptual hash
            phash = self.calculate_image_hash(image_path, 'phash')
            if phash:
                file_hashes[file_id] = {
                    'phash': phash,
                    'path': image_path,
                    'metadata': file_info
                }
        
        # Compare all pairs
        file_ids = list(file_hashes.keys())
        for i in range(len(file_ids)):
            for j in range(i + 1, len(file_ids)):
                file_id1, file_id2 = file_ids[i], file_ids[j]
                
                # Compare perceptual hashes
                similarity = self.calculate_hash_similarity(
                    file_hashes[file_id1]['phash'],
                    file_hashes[file_id2]['phash']
                )
                
                if similarity >= self.threshold:
                    # Additional verification with structural comparison
                    structural_sim = self.compare_images_structural(
                        file_hashes[file_id1]['path'],
                        file_hashes[file_id2]['path']
                    )
                    
                    # Use higher of the two similarities
                    final_similarity = max(similarity, structural_sim)
                    
                    if final_similarity >= self.threshold:
                        duplicate_match = DuplicateMatch(
                            file_id_1=file_id1,
                            file_id_2=file_id2,
                            similarity_score=final_similarity,
                            method='phash+structural',
                            metadata_1=file_hashes[file_id1]['metadata'],
                            metadata_2=file_hashes[file_id2]['metadata']
                        )
                        duplicates.append(duplicate_match)
        
        self.logger.info(f"Found {len(duplicates)} duplicate pairs in batch of {len(file_info_list)} files")
        return duplicates
    
    def is_duplicate_of_existing(self, new_file_path: Path, existing_hashes: Dict[str, str]) -> Optional[Tuple[str, float]]:
        """
        Check if a new file is a duplicate of existing files.
        
        Args:
            new_file_path: Path to new file
            existing_hashes: Dict of file_id -> hash for existing files
            
        Returns:
            Tuple of (existing_file_id, similarity) if duplicate found, None otherwise
        """
        try:
            # Calculate hash for new file
            new_hash = self.calculate_image_hash(new_file_path, 'phash')
            if not new_hash:
                return None
            
            # Compare with existing hashes
            best_match = None
            best_similarity = 0.0
            
            for file_id, existing_hash in existing_hashes.items():
                similarity = self.calculate_hash_similarity(new_hash, existing_hash)
                
                if similarity >= self.threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = file_id
            
            if best_match:
                return (best_match, best_similarity)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to check for duplicates: {str(e)}")
            return None
    
    def get_duplicate_groups(self, duplicate_matches: List[DuplicateMatch]) -> List[List[str]]:
        """
        Group duplicate matches into connected components.
        
        Args:
            duplicate_matches: List of duplicate matches
            
        Returns:
            List of groups, where each group is a list of file IDs
        """
        # Build adjacency list
        graph = {}
        all_files = set()
        
        for match in duplicate_matches:
            file1, file2 = match.file_id_1, match.file_id_2
            all_files.add(file1)
            all_files.add(file2)
            
            if file1 not in graph:
                graph[file1] = set()
            if file2 not in graph:
                graph[file2] = set()
            
            graph[file1].add(file2)
            graph[file2].add(file1)
        
        # Find connected components using DFS
        visited = set()
        groups = []
        
        def dfs(node, current_group):
            if node in visited:
                return
            visited.add(node)
            current_group.append(node)
            
            for neighbor in graph.get(node, []):
                dfs(neighbor, current_group)
        
        for file_id in all_files:
            if file_id not in visited:
                group = []
                dfs(file_id, group)
                if len(group) > 1:  # Only include groups with multiple files
                    groups.append(group)
        
        self.logger.info(f"Found {len(groups)} duplicate groups")
        return groups