import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter


class ImagePreprocessor:
    """Handles image preprocessing for better OCR results."""
    
    def __init__(self, max_size: int = 2048):
        """
        Initialize image preprocessor.
        
        Args:
            max_size: Maximum dimension for processed images
        """
        self.max_size = max_size
        self.logger = logging.getLogger(__name__)
    
    def preprocess_image(self, image_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Apply comprehensive preprocessing to improve OCR accuracy.
        
        Args:
            image_path: Input image path
            output_path: Optional output path (creates temp file if None)
            
        Returns:
            Path to preprocessed image
        """
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Apply preprocessing pipeline
            processed = self._apply_preprocessing_pipeline(image)
            
            # Save processed image
            if output_path is None:
                output_path = image_path.parent / f"processed_{image_path.name}"
            
            cv2.imwrite(str(output_path), processed)
            
            self.logger.debug(f"Preprocessed image saved to: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Image preprocessing failed: {str(e)}")
            return image_path  # Return original if preprocessing fails
    
    def _apply_preprocessing_pipeline(self, image: np.ndarray) -> np.ndarray:
        """
        Apply the complete preprocessing pipeline.
        
        Args:
            image: Input image array
            
        Returns:
            Processed image array
        """
        # 1. Resize if too large
        processed = self._resize_image(image)
        
        # 2. Noise reduction
        processed = self._reduce_noise(processed)
        
        # 3. Contrast enhancement
        processed = self._enhance_contrast(processed)
        
        # 4. Deskew if needed
        processed = self._deskew_image(processed)
        
        # 5. Sharpen for better text clarity
        processed = self._sharpen_image(processed)
        
        return processed
    
    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """Resize image while maintaining aspect ratio."""
        height, width = image.shape[:2]
        
        if max(height, width) <= self.max_size:
            return image
        
        # Calculate new dimensions
        if height > width:
            new_height = self.max_size
            new_width = int(width * (self.max_size / height))
        else:
            new_width = self.max_size
            new_height = int(height * (self.max_size / width))
        
        resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        self.logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        
        return resized
    
    def _reduce_noise(self, image: np.ndarray) -> np.ndarray:
        """Apply noise reduction techniques."""
        # Convert to grayscale for noise reduction
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Non-local Means Denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Convert back to BGR
        return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast using CLAHE."""
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        
        # Convert back to BGR
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """Detect and correct image skew."""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Hough line detection
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None:
                return image
            
            # Calculate skew angle
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                # Normalize angle to [-45, 45] degrees
                if angle > 45:
                    angle = angle - 90
                if abs(angle) < 45:  # Only consider reasonable skew angles
                    angles.append(angle)
            
            if not angles:
                return image
            
            # Use median angle to avoid outliers
            skew_angle = np.median(angles)
            
            # Only deskew if angle is significant
            if abs(skew_angle) > 0.5:
                height, width = image.shape[:2]
                center = (width // 2, height // 2)
                
                # Create rotation matrix
                rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
                
                # Apply rotation
                deskewed = cv2.warpAffine(image, rotation_matrix, (width, height),
                                        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                
                self.logger.debug(f"Deskewed image by {skew_angle:.2f} degrees")
                return deskewed
            
            return image
            
        except Exception as e:
            self.logger.warning(f"Deskewing failed: {str(e)}")
            return image
    
    def _sharpen_image(self, image: np.ndarray) -> np.ndarray:
        """Apply sharpening filter to enhance text clarity."""
        # Create sharpening kernel
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        
        # Apply kernel
        sharpened = cv2.filter2D(image, -1, kernel)
        
        return sharpened
    
    def preprocess_for_text_detection(self, image_path: Path) -> Path:
        """
        Specialized preprocessing for text detection.
        
        Args:
            image_path: Input image path
            
        Returns:
            Path to preprocessed image
        """
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply bilateral filter to reduce noise while keeping edges sharp
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
            
            # Morphological operations to clean up text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Save processed image
            output_path = image_path.parent / f"text_detection_{image_path.name}"
            cv2.imwrite(str(output_path), cleaned)
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Text detection preprocessing failed: {str(e)}")
            return image_path
    
    def enhance_for_ocr(self, image_path: Path) -> Path:
        """
        Apply OCR-specific enhancements.
        
        Args:
            image_path: Input image path
            
        Returns:
            Path to enhanced image
        """
        try:
            # Use PIL for some enhancements
            pil_image = Image.open(image_path)
            
            # Convert to grayscale if not already
            if pil_image.mode != 'L':
                pil_image = pil_image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(pil_image)
            enhanced = enhancer.enhance(1.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = enhancer.enhance(2.0)
            
            # Apply unsharp mask
            enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            
            # Save enhanced image
            output_path = image_path.parent / f"ocr_enhanced_{image_path.name}"
            enhanced.save(output_path)
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"OCR enhancement failed: {str(e)}")
            return image_path
    
    def get_image_quality_metrics(self, image_path: Path) -> Dict[str, Any]:
        """
        Analyze image quality metrics.
        
        Args:
            image_path: Path to image
            
        Returns:
            Dict with quality metrics
        """
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                return {'error': 'Could not load image'}
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate sharpness (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate brightness
            brightness = np.mean(gray)
            
            # Calculate contrast (standard deviation)
            contrast = np.std(gray)
            
            # Estimate noise level
            noise = self._estimate_noise(gray)
            
            # Calculate resolution
            height, width = gray.shape
            total_pixels = height * width
            
            return {
                'width': width,
                'height': height,
                'total_pixels': total_pixels,
                'sharpness': float(laplacian_var),
                'brightness': float(brightness),
                'contrast': float(contrast),
                'noise_level': float(noise),
                'aspect_ratio': width / height
            }
            
        except Exception as e:
            self.logger.error(f"Quality analysis failed: {str(e)}")
            return {'error': str(e)}
    
    def _estimate_noise(self, image: np.ndarray) -> float:
        """Estimate noise level in image."""
        # Use Laplacian to estimate noise
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        noise_estimate = laplacian.var()
        return noise_estimate