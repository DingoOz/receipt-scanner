import os
import json
import logging
from pathlib import Path
from typing import Optional, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleAuthManager:
    """Handles Google API authentication with OAuth 2.0 flow."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/photoslibrary.readonly',
        'https://www.googleapis.com/auth/cloud-platform'
    ]
    
    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json'):
        """
        Initialize Google Auth Manager.
        
        Args:
            credentials_file: Path to OAuth 2.0 credentials file from Google Cloud Console
            token_file: Path to store access/refresh tokens
        """
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.creds: Optional[Credentials] = None
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self) -> bool:
        """
        Perform Google API authentication flow.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # Load existing token if available
            if self.token_file.exists():
                self.creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            
            # If no valid credentials, initiate OAuth flow
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.logger.info("Refreshing expired credentials")
                    self.creds.refresh(Request())
                else:
                    if not self.credentials_file.exists():
                        self.logger.error(f"Credentials file not found: {self.credentials_file}")
                        return False
                    
                    self.logger.info("Starting OAuth 2.0 flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), self.SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(self.token_file, 'w') as token:
                    token.write(self.creds.to_json())
                    self.logger.info(f"Credentials saved to {self.token_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def get_drive_service(self):
        """Get authenticated Google Drive service."""
        if not self.creds:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return build('drive', 'v3', credentials=self.creds)
    
    def get_photos_service(self):
        """Get authenticated Google Photos Library service."""
        if not self.creds:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return build('photoslibrary', 'v1', credentials=self.creds)
    
    def get_vision_service(self):
        """Get authenticated Google Cloud Vision service."""
        if not self.creds:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return build('vision', 'v1', credentials=self.creds)
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid credentials."""
        return self.creds is not None and self.creds.valid
    
    def revoke_credentials(self) -> bool:
        """Revoke stored credentials and delete token file."""
        try:
            if self.token_file.exists():
                os.remove(self.token_file)
                self.logger.info("Token file deleted")
            
            self.creds = None
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to revoke credentials: {str(e)}")
            return False