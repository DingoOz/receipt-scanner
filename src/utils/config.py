import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict


@dataclass
class ProcessingConfig:
    """Configuration for image processing and OCR."""
    confidence_threshold: float = 0.8
    max_image_size: int = 2048
    use_opencv_preprocessing: bool = True
    fallback_to_tesseract: bool = True
    supported_formats: list = None
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']


@dataclass
class ExportConfig:
    """Configuration for data export."""
    output_format: str = 'xlsx'
    output_directory: str = 'output'
    include_confidence_scores: bool = True
    include_raw_text: bool = False
    date_format: str = '%Y-%m-%d'


@dataclass
class StorageConfig:
    """Configuration for caching and storage."""
    cache_directory: str = 'cache'
    max_cache_size_mb: int = 1000
    duplicate_threshold: float = 0.95
    keep_original_images: bool = False


@dataclass
class AppConfig:
    """Main application configuration."""
    processing: ProcessingConfig
    export: ExportConfig
    storage: StorageConfig
    google_drive_folder_id: Optional[str] = None
    google_photos_album_id: Optional[str] = None
    log_level: str = 'INFO'
    
    def __post_init__(self):
        if isinstance(self.processing, dict):
            self.processing = ProcessingConfig(**self.processing)
        if isinstance(self.export, dict):
            self.export = ExportConfig(**self.export)
        if isinstance(self.storage, dict):
            self.storage = StorageConfig(**self.storage)


class ConfigManager:
    """Manages application configuration from files and environment variables."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file (YAML or JSON)
        """
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """
        Load configuration from file and environment variables.
        
        Returns:
            AppConfig: Loaded configuration
        """
        if self._config is not None:
            return self._config
        
        # Start with default configuration
        config_dict = self._get_default_config()
        
        # Load from file if specified
        if self.config_file:
            file_config = self._load_from_file(self.config_file)
            if file_config:
                config_dict = self._merge_configs(config_dict, file_config)
        else:
            # Try to find config file in standard locations
            config_file = self._find_config_file()
            if config_file:
                file_config = self._load_from_file(config_file)
                if file_config:
                    config_dict = self._merge_configs(config_dict, file_config)
        
        # Override with environment variables
        env_config = self._load_from_env()
        config_dict = self._merge_configs(config_dict, env_config)
        
        # Create and validate configuration
        self._config = AppConfig(**config_dict)
        self._validate_config(self._config)
        
        return self._config
    
    def save_config(self, config: AppConfig, file_path: Optional[str] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            file_path: Output file path (defaults to config file)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            output_path = file_path or self.config_file or 'config/config.yaml'
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            config_dict = asdict(config)
            
            if output_path.suffix.lower() in ['.yaml', '.yml']:
                with open(output_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            else:
                with open(output_path, 'w') as f:
                    json.dump(config_dict, f, indent=2)
            
            self.logger.info(f"Configuration saved to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration dictionary."""
        return {
            'processing': asdict(ProcessingConfig()),
            'export': asdict(ExportConfig()),
            'storage': asdict(StorageConfig()),
            'google_drive_folder_id': None,
            'google_photos_album_id': None,
            'log_level': 'INFO'
        }
    
    def _find_config_file(self) -> Optional[Path]:
        """Find configuration file in standard locations."""
        possible_paths = [
            Path('config/config.yaml'),
            Path('config/config.yml'),
            Path('config/config.json'),
            Path('config.yaml'),
            Path('config.yml'),
            Path('config.json'),
            Path.home() / '.config' / 'receipt-scanner' / 'config.yaml'
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def _load_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        try:
            path = Path(file_path)
            if not path.exists():
                self.logger.warning(f"Configuration file not found: {file_path}")
                return None
            
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
                    
        except Exception as e:
            self.logger.error(f"Failed to load configuration file {file_path}: {str(e)}")
            return None
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Processing configuration
        if os.getenv('RECEIPT_CONFIDENCE_THRESHOLD'):
            env_config.setdefault('processing', {})['confidence_threshold'] = float(os.getenv('RECEIPT_CONFIDENCE_THRESHOLD'))
        
        if os.getenv('RECEIPT_MAX_IMAGE_SIZE'):
            env_config.setdefault('processing', {})['max_image_size'] = int(os.getenv('RECEIPT_MAX_IMAGE_SIZE'))
        
        # Export configuration
        if os.getenv('RECEIPT_OUTPUT_FORMAT'):
            env_config.setdefault('export', {})['output_format'] = os.getenv('RECEIPT_OUTPUT_FORMAT')
        
        if os.getenv('RECEIPT_OUTPUT_DIR'):
            env_config.setdefault('export', {})['output_directory'] = os.getenv('RECEIPT_OUTPUT_DIR')
        
        # Storage configuration
        if os.getenv('RECEIPT_CACHE_DIR'):
            env_config.setdefault('storage', {})['cache_directory'] = os.getenv('RECEIPT_CACHE_DIR')
        
        # Google services
        if os.getenv('GOOGLE_DRIVE_FOLDER_ID'):
            env_config['google_drive_folder_id'] = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        if os.getenv('GOOGLE_PHOTOS_ALBUM_ID'):
            env_config['google_photos_album_id'] = os.getenv('GOOGLE_PHOTOS_ALBUM_ID')
        
        # Logging
        if os.getenv('LOG_LEVEL'):
            env_config['log_level'] = os.getenv('LOG_LEVEL')
        
        return env_config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self, config: AppConfig) -> None:
        """Validate configuration values."""
        if not 0.0 <= config.processing.confidence_threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        
        if config.processing.max_image_size <= 0:
            raise ValueError("Max image size must be positive")
        
        if config.export.output_format.lower() not in ['csv', 'xlsx', 'json']:
            raise ValueError("Output format must be 'csv', 'xlsx', or 'json'")
        
        if config.storage.max_cache_size_mb <= 0:
            raise ValueError("Max cache size must be positive")
        
        if not 0.0 <= config.storage.duplicate_threshold <= 1.0:
            raise ValueError("Duplicate threshold must be between 0.0 and 1.0")