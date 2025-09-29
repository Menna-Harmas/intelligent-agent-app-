import os
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveAuth:
    """
    Google Drive authentication handler.
    FIXED: Better service creation and validation.
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        """
        Initialize the Google Drive authentication handler.
        
        Args:
            credentials_file: Path to the OAuth2 credentials file
            token_file: Path to store/load the access token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials = None
        self.service = None
        
        logger.info(f"GoogleDriveAuth initialized with credentials file: {credentials_file}")
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive and return the service object.
        FIXED: Better error handling and service validation.
        
        Returns:
            Google Drive API service object or None if authentication fails
        """
        try:
            # Load existing credentials if they exist
            if os.path.exists(self.token_file):
                logger.info(f"Loading existing credentials from {self.token_file}")
                self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
            
            # Check if credentials are valid or need refresh
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Refreshing expired credentials")
                    try:
                        self.credentials.refresh(Request())
                        logger.info("Credentials refreshed successfully")
                    except Exception as refresh_error:
                        logger.warning(f"Failed to refresh credentials: {refresh_error}")
                        self.credentials = None
                
                # If credentials are still invalid, start OAuth flow
                if not self.credentials or not self.credentials.valid:
                    logger.info("Starting OAuth2 flow")
                    
                    if not os.path.exists(self.credentials_file):
                        raise FileNotFoundError(f"Credentials file '{self.credentials_file}' not found. "
                                              f"Please download it from Google Cloud Console.")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, 
                        self.SCOPES
                    )
                    
                    self.credentials = flow.run_local_server(
                        port=8080,
                        authorization_prompt_message='Please visit this URL to authorize the application: {url}',
                        success_message='Authorization complete! You may close this window.',
                        open_browser=True
                    )
                    
                    # Save the credentials for next time
                    self._save_credentials()
                    logger.info("New credentials obtained and saved")
            
            # Build the service
            logger.info("Building Google Drive API service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test the service to make sure it works
            if self._test_service():
                logger.info("Google Drive service created and tested successfully")
                return self.service
            else:
                logger.error("Service test failed")
                return None
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise Exception(f"Google Drive authentication failed: {str(e)}")
    
    def _save_credentials(self) -> None:
        """Save credentials to file."""
        try:
            with open(self.token_file, 'w') as token_file:
                token_file.write(self.credentials.to_json())
            logger.info(f"Credentials saved to {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def _test_service(self) -> bool:
        """
        Test the Google Drive service to make sure it's working.
        
        Returns:
            True if service is working, False otherwise
        """
        try:
            # Try to list files (with a small limit)
            results = self.service.files().list(pageSize=1, fields="files(id, name)").execute()
            logger.info("Service test passed - able to list files")
            return True
        except Exception as e:
            logger.error(f"Service test failed: {e}")
            return False
    
    def get_service(self) -> Optional[object]:
        """
        Get the authenticated Google Drive service.
        
        Returns:
            Google Drive API service object or None
        """
        return self.service
    
    def is_authenticated(self) -> bool:
        """
        Check if the user is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        return (self.credentials is not None and 
                self.credentials.valid and 
                self.service is not None)
    
    def logout(self) -> None:
        """
        Log out by removing stored credentials.
        """
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"Failed to remove token file: {e}")
        
        self.credentials = None
        self.service = None
        logger.info("Logged out successfully")
