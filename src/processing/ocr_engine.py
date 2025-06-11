import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import pytesseract
from PIL import Image

from ..services.vision_service import GoogleVisionService
from ..processing.image_processor import ImagePreprocessor
from ..processing.data_extractor import ReceiptDataExtractor, ReceiptData
from ..auth.google_auth import GoogleAuthManager
from ..utils.config import ProcessingConfig


class OCREngine:
    """Main OCR engine that coordinates Vision API, Tesseract, and data extraction."""
    
    def __init__(self, config: ProcessingConfig, auth_manager: GoogleAuthManager):
        """
        Initialize OCR engine.
        
        Args:
            config: Processing configuration
            auth_manager: Authenticated Google Auth Manager
        """
        self.config = config
        self.auth_manager = auth_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize services
        self.vision_service = GoogleVisionService(auth_manager)
        self.image_preprocessor = ImagePreprocessor(max_size=config.max_image_size)
        self.data_extractor = ReceiptDataExtractor()
        
        # Check Tesseract availability
        self.tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract is available."""
        try:
            pytesseract.get_tesseract_version()
            self.logger.info("Tesseract OCR is available")
            return True
        except Exception as e:
            self.logger.warning(f"Tesseract OCR not available: {str(e)}")
            return False
    
    def process_receipt_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Process a receipt image through the complete OCR pipeline.
        
        Args:
            image_path: Path to receipt image
            
        Returns:
            Dict containing OCR results and extracted data
        """
        try:
            self.logger.info(f"Processing receipt image: {image_path}")
            
            # Step 1: Image quality assessment
            quality_metrics = self.image_preprocessor.get_image_quality_metrics(image_path)
            
            # Step 2: Preprocess image if needed
            processed_image_path = image_path
            if self.config.use_opencv_preprocessing:
                processed_image_path = self.image_preprocessor.preprocess_image(image_path)
            
            # Step 3: OCR with primary method (Google Vision)
            ocr_result = self._perform_ocr(processed_image_path)
            
            # Step 4: Extract structured data
            receipt_data = None
            if ocr_result['success'] and ocr_result['text']:
                receipt_data = self.data_extractor.extract_receipt_data(
                    ocr_result['text'], 
                    ocr_result['confidence']
                )
            
            # Step 5: Compile results
            result = {
                'success': ocr_result['success'],
                'image_path': str(image_path),
                'processed_image_path': str(processed_image_path),
                'quality_metrics': quality_metrics,
                'ocr_method': ocr_result['method'],
                'ocr_confidence': ocr_result['confidence'],
                'raw_text': ocr_result['text'],
                'receipt_data': receipt_data.to_dict() if receipt_data else None,
                'processing_time': ocr_result.get('processing_time', 0),
                'error': ocr_result.get('error')
            }
            
            # Clean up processed image if different from original
            if processed_image_path != image_path and processed_image_path.exists():
                try:
                    processed_image_path.unlink()
                except Exception:
                    pass
            
            self.logger.info(f"Receipt processing completed: {ocr_result['method']} method, {ocr_result['confidence']:.2f} confidence")
            return result
            
        except Exception as e:
            self.logger.error(f"Receipt processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'image_path': str(image_path),
                'ocr_method': 'none',
                'ocr_confidence': 0.0,
                'raw_text': '',
                'receipt_data': None
            }
    
    def _perform_ocr(self, image_path: Path) -> Dict[str, Any]:
        """
        Perform OCR using available methods with fallback.
        
        Args:
            image_path: Path to image
            
        Returns:
            Dict with OCR results
        """
        import time
        start_time = time.time()
        
        # Try Google Vision API first
        if self.vision_service.is_available():
            try:
                self.logger.debug("Attempting OCR with Google Vision API")
                vision_result = self.vision_service.extract_text_from_image(image_path)
                
                if vision_result['success'] and vision_result['confidence'] >= self.config.confidence_threshold:
                    processing_time = time.time() - start_time
                    return {
                        'success': True,
                        'method': 'google_vision',
                        'text': vision_result['text'],
                        'confidence': vision_result['confidence'],
                        'processing_time': processing_time,
                        'annotations': vision_result.get('annotations', [])
                    }
                else:
                    self.logger.debug(f"Vision API confidence too low: {vision_result['confidence']:.2f}")
                    
            except Exception as e:
                self.logger.warning(f"Google Vision API failed: {str(e)}")
        
        # Try document detection if regular text detection failed
        if self.vision_service.is_available():
            try:
                self.logger.debug("Attempting document detection with Google Vision API")
                doc_result = self.vision_service.extract_text_with_document_detection(image_path)
                
                if doc_result['success'] and doc_result['confidence'] >= self.config.confidence_threshold:
                    processing_time = time.time() - start_time
                    return {
                        'success': True,
                        'method': 'google_vision_document',
                        'text': doc_result['text'],
                        'confidence': doc_result['confidence'],
                        'processing_time': processing_time,
                        'pages': doc_result.get('pages', [])
                    }
                    
            except Exception as e:
                self.logger.warning(f"Google Vision document detection failed: {str(e)}")
        
        # Fallback to Tesseract if enabled and available
        if self.config.fallback_to_tesseract and self.tesseract_available:
            try:
                self.logger.debug("Falling back to Tesseract OCR")
                tesseract_result = self._tesseract_ocr(image_path)
                processing_time = time.time() - start_time
                
                return {
                    'success': True,
                    'method': 'tesseract',
                    'text': tesseract_result['text'],
                    'confidence': tesseract_result['confidence'],
                    'processing_time': processing_time
                }
                
            except Exception as e:
                self.logger.error(f"Tesseract OCR failed: {str(e)}")
        
        # No OCR method succeeded
        processing_time = time.time() - start_time
        return {
            'success': False,
            'method': 'none',
            'text': '',
            'confidence': 0.0,
            'processing_time': processing_time,
            'error': 'All OCR methods failed'
        }
    
    def _tesseract_ocr(self, image_path: Path) -> Dict[str, Any]:
        """
        Perform OCR using Tesseract.
        
        Args:
            image_path: Path to image
            
        Returns:
            Dict with Tesseract OCR results
        """
        try:
            # Configure Tesseract for better receipt recognition
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,/$:-% '
            
            # Open image
            image = Image.open(image_path)
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Get confidence data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=custom_config)
            
            # Calculate average confidence
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0
            
            return {
                'text': text,
                'confidence': avg_confidence
            }
            
        except Exception as e:
            self.logger.error(f"Tesseract processing failed: {str(e)}")
            raise
    
    def extract_text_only(self, image_path: Path) -> Dict[str, Any]:
        """
        Extract only text without data parsing (faster).
        
        Args:
            image_path: Path to image
            
        Returns:
            Dict with text extraction results
        """
        try:
            # Preprocess if enabled
            processed_image_path = image_path
            if self.config.use_opencv_preprocessing:
                processed_image_path = self.image_preprocessor.preprocess_image(image_path)
            
            # Perform OCR
            ocr_result = self._perform_ocr(processed_image_path)
            
            # Clean up
            if processed_image_path != image_path and processed_image_path.exists():
                try:
                    processed_image_path.unlink()
                except Exception:
                    pass
            
            return {
                'success': ocr_result['success'],
                'method': ocr_result['method'],
                'text': ocr_result['text'],
                'confidence': ocr_result['confidence'],
                'processing_time': ocr_result.get('processing_time', 0),
                'error': ocr_result.get('error')
            }
            
        except Exception as e:
            self.logger.error(f"Text extraction failed: {str(e)}")
            return {
                'success': False,
                'method': 'none',
                'text': '',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def batch_process_images(self, image_paths: List[Path]) -> List[Dict[str, Any]]:
        """
        Process multiple images in batch.
        
        Args:
            image_paths: List of image paths
            
        Returns:
            List of processing results
        """
        results = []
        
        for i, image_path in enumerate(image_paths):
            self.logger.info(f"Processing image {i+1}/{len(image_paths)}: {image_path}")
            
            try:
                result = self.process_receipt_image(image_path)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to process {image_path}: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'image_path': str(image_path),
                    'ocr_method': 'none',
                    'ocr_confidence': 0.0,
                    'raw_text': '',
                    'receipt_data': None
                })
        
        return results
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get OCR engine status and capabilities."""
        return {
            'google_vision_available': self.vision_service.is_available(),
            'tesseract_available': self.tesseract_available,
            'preprocessing_enabled': self.config.use_opencv_preprocessing,
            'fallback_enabled': self.config.fallback_to_tesseract,
            'confidence_threshold': self.config.confidence_threshold,
            'max_image_size': self.config.max_image_size,
            'supported_formats': self.config.supported_formats
        }