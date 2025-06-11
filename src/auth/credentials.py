import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class CredentialsManager:
    """Manages API credentials and configuration securely."""
    
    def __init__(self, config_dir: str = 'config'):
        """
        Initialize credentials manager.
        
        Args:
            config_dir: Directory to store configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def get_google_credentials_path(self) -> Optional[Path]:
        """
        Get path to Google OAuth 2.0 credentials file.
        
        Returns:
            Path to credentials file if exists, None otherwise
        """
        # Check environment variable first
        creds_path = os.getenv('GOOGLE_CREDENTIALS_FILE')
        if creds_path and Path(creds_path).exists():
            return Path(creds_path)
        
        # Check standard locations
        standard_paths = [
            self.config_dir / 'credentials.json',
            Path('credentials.json'),
            Path.home() / '.config' / 'receipt-scanner' / 'credentials.json'
        ]
        
        for path in standard_paths:
            if path.exists():
                return path
        
        return None
    
    def get_service_account_path(self) -> Optional[Path]:
        """
        Get path to Google service account key file.
        
        Returns:
            Path to service account key if exists, None otherwise
        """
        # Check environment variable first
        sa_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        if sa_path and Path(sa_path).exists():
            return Path(sa_path)
        
        # Check standard locations
        standard_paths = [
            self.config_dir / 'service-account.json',
            Path('service-account.json'),
            Path.home() / '.config' / 'receipt-scanner' / 'service-account.json'
        ]
        
        for path in standard_paths:
            if path.exists():
                return path
        
        return None
    
    def validate_credentials_file(self, file_path: Path) -> bool:
        """
        Validate Google OAuth 2.0 credentials file format.
        
        Args:
            file_path: Path to credentials file
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check for required OAuth 2.0 fields
            if 'installed' in data or 'web' in data:
                client_config = data.get('installed') or data.get('web')
                required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
                
                if all(field in client_config for field in required_fields):
                    return True
            
            # Check for service account format
            elif 'type' in data and data['type'] == 'service_account':
                required_fields = ['client_email', 'private_key', 'project_id']
                if all(field in data for field in required_fields):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to validate credentials file: {str(e)}")
            return False
    
    def setup_instructions(self) -> str:
        """
        Get setup instructions for Google API credentials.
        
        Returns:
            str: Setup instructions
        """
        return """
Google API Credentials Setup:

1. Go to the Google Cloud Console: https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Google Drive API
   - Google Photos Library API
   - Google Cloud Vision API

4. Go to Credentials section and create OAuth 2.0 Client ID
5. Download the credentials file as 'credentials.json'
6. Place it in one of these locations:
   - ./config/credentials.json
   - ./credentials.json
   - ~/.config/receipt-scanner/credentials.json

Alternatively, set the GOOGLE_CREDENTIALS_FILE environment variable
to point to your credentials file.

For automated/server deployments, you can also use a service account:
- Create a service account key in Google Cloud Console
- Download as JSON and save as 'service-account.json'
- Set GOOGLE_SERVICE_ACCOUNT_FILE environment variable
"""