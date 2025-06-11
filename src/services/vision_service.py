import io
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from google.cloud import vision
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..auth.google_auth import GoogleAuthManager


class GoogleVisionService:
    """Service for interacting with Google Cloud Vision API for OCR."""
    
    def __init__(self, auth_manager: GoogleAuthManager):
        """
        Initialize Google Vision service.
        
        Args:
            auth_manager: Authenticated Google Auth Manager
        """
        self.auth_manager = auth_manager
        self.client = None
        self.logger = logging.getLogger(__name__)
        self._initialize_service()
    
    def _initialize_service(self) -> None:
        """Initialize the Google Vision client."""
        try:
            if not self.auth_manager.is_authenticated():
                raise RuntimeError("Not authenticated with Google services")
            
            # Use the same credentials as the auth manager
            credentials = self.auth_manager.creds
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
            self.logger.info("Google Vision service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Vision service: {str(e)}")
            # Don't raise here - we'll fall back to Tesseract
            self.client = None
    
    def extract_text_from_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Extract text from image using Google Vision API.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict containing extracted text and metadata
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Vision API not available',
                    'text': '',
                    'confidence': 0.0,
                    'annotations': []
                }
            
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Perform text detection
            response = self.client.text_detection(image=image)
            
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            
            texts = response.text_annotations
            
            if not texts:
                return {
                    'success': True,
                    'text': '',
                    'confidence': 0.0,
                    'annotations': [],
                    'full_text_annotation': None
                }
            
            # Extract full text (first annotation contains all text)
            full_text = texts[0].description if texts else ''
            
            # Calculate average confidence from bounding polygon data
            confidence = self._calculate_text_confidence(response.full_text_annotation)
            
            # Extract individual text annotations
            annotations = []
            for text in texts[1:]:  # Skip first one (full text)
                annotation = {
                    'text': text.description,
                    'bounding_poly': self._extract_bounding_poly(text.bounding_poly),
                    'confidence': getattr(text, 'confidence', 0.0)
                }
                annotations.append(annotation)
            
            result = {
                'success': True,
                'text': full_text,
                'confidence': confidence,
                'annotations': annotations,
                'full_text_annotation': self._process_full_text_annotation(response.full_text_annotation)
            }
            
            self.logger.debug(f"Vision API extracted {len(full_text)} characters with {confidence:.2f} confidence")
            return result
            
        except Exception as e:
            self.logger.error(f"Vision API text extraction failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0,
                'annotations': []
            }
    
    def extract_text_with_document_detection(self, image_path: Path) -> Dict[str, Any]:
        """
        Extract text using document text detection (better for documents).
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict containing extracted text and structure
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Vision API not available',
                    'text': '',
                    'confidence': 0.0,
                    'pages': []
                }
            
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Perform document text detection
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            
            document = response.full_text_annotation
            
            if not document:
                return {
                    'success': True,
                    'text': '',
                    'confidence': 0.0,
                    'pages': []
                }
            
            # Extract structured text information
            pages = []
            for page in document.pages:
                page_info = {
                    'width': page.width,
                    'height': page.height,
                    'blocks': [],
                    'confidence': getattr(page, 'confidence', 0.0)
                }
                
                for block in page.blocks:
                    block_info = {
                        'paragraphs': [],
                        'confidence': getattr(block, 'confidence', 0.0),
                        'bounding_box': self._extract_bounding_poly(block.bounding_box)
                    }
                    
                    for paragraph in block.paragraphs:
                        paragraph_text = ''
                        word_confidences = []
                        
                        for word in paragraph.words:
                            word_text = ''.join([symbol.text for symbol in word.symbols])
                            paragraph_text += word_text + ' '
                            
                            word_confidence = getattr(word, 'confidence', 0.0)
                            word_confidences.append(word_confidence)
                        
                        paragraph_info = {
                            'text': paragraph_text.strip(),
                            'confidence': sum(word_confidences) / len(word_confidences) if word_confidences else 0.0,
                            'bounding_box': self._extract_bounding_poly(paragraph.bounding_box)
                        }
                        block_info['paragraphs'].append(paragraph_info)
                    
                    page_info['blocks'].append(block_info)
                
                pages.append(page_info)
            
            # Calculate overall confidence
            all_confidences = []
            for page in pages:
                for block in page['blocks']:
                    for paragraph in block['paragraphs']:
                        all_confidences.append(paragraph['confidence'])
            
            overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            result = {
                'success': True,
                'text': document.text,
                'confidence': overall_confidence,
                'pages': pages
            }
            
            self.logger.debug(f"Document detection extracted {len(document.text)} characters with {overall_confidence:.2f} confidence")
            return result
            
        except Exception as e:
            self.logger.error(f"Vision API document detection failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0,
                'pages': []
            }
    
    def _calculate_text_confidence(self, full_text_annotation) -> float:
        """Calculate average confidence from full text annotation."""
        if not full_text_annotation or not full_text_annotation.pages:
            return 0.0
        
        confidences = []
        for page in full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_confidence = getattr(word, 'confidence', 0.0)
                        confidences.append(word_confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _extract_bounding_poly(self, bounding_poly) -> List[Dict[str, int]]:
        """Extract bounding polygon coordinates."""
        if not bounding_poly or not bounding_poly.vertices:
            return []
        
        vertices = []
        for vertex in bounding_poly.vertices:
            vertices.append({
                'x': getattr(vertex, 'x', 0),
                'y': getattr(vertex, 'y', 0)
            })
        
        return vertices
    
    def _process_full_text_annotation(self, full_text_annotation) -> Optional[Dict[str, Any]]:
        """Process full text annotation into structured format."""
        if not full_text_annotation:
            return None
        
        return {
            'text': full_text_annotation.text,
            'pages_count': len(full_text_annotation.pages) if full_text_annotation.pages else 0
        }
    
    def detect_handwriting(self, image_path: Path) -> Dict[str, Any]:
        """
        Detect handwritten text in image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict containing handwriting detection results
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Vision API not available',
                    'text': '',
                    'confidence': 0.0
                }
            
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Configure handwriting detection
            image_context = vision.ImageContext(language_hints=['en'])
            
            # Perform handwriting detection
            response = self.client.document_text_detection(
                image=image,
                image_context=image_context
            )
            
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            
            document = response.full_text_annotation
            text = document.text if document else ''
            confidence = self._calculate_text_confidence(document) if document else 0.0
            
            return {
                'success': True,
                'text': text,
                'confidence': confidence
            }
            
        except Exception as e:
            self.logger.error(f"Handwriting detection failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0
            }
    
    def is_available(self) -> bool:
        """Check if Vision API is available."""
        return self.client is not None