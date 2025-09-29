import streamlit as st
import os
import json
import tempfile
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
    Google Drive authentication handler that works both locally and on Streamlit Cloud.
    Uses local credentials.json for development and Streamlit secrets for deployment.
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
            credentials_file: Path to the OAuth2 credentials file (for local development)
            token_file: Path to store/load the access token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials = None
        self.service = None
        self.temp_credentials_file = None
        
        logger.info(f"GoogleDriveAuth initialized")
    
    def _get_credentials_file(self) -> str:
        """
        Get credentials from local file or create from Streamlit secrets.
        
        Returns:
            Path to credentials file
            
        Raises:
            FileNotFoundError: If no credentials are available
        """
        
        # Try local file first (for development)
        if os.path.exists(self.credentials_file):
            logger.info(f"Using local credentials file: {self.credentials_file}")
            return self.credentials_file
        
        # Try Streamlit secrets (for deployment)
        try:
            if hasattr(st, 'secrets') and 'GOOGLE_CLIENT_ID' in st.secrets:
                logger.info("Creating credentials from Streamlit secrets")
                
                credentials_dict = {
                    "web": {
                        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                        "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost:8080/"]
                    }
                }
                
                # Create temporary credentials file
                self.temp_credentials_file = tempfile.NamedTemporaryFile(
                    mode='w', 
                    suffix='.json', 
                    delete=False,
                    prefix='temp_credentials_'
                )
                
                json.dump(credentials_dict, self.temp_credentials_file)
                self.temp_credentials_file.flush()
                self.temp_credentials_file.close()
                
                logger.info(f"Temporary credentials file created: {self.temp_credentials_file.name}")
                return self.temp_credentials_file.name
        
        except Exception as e:
            logger.error(f"Failed to create credentials from Streamlit secrets: {e}")
        
        # No credentials available
        raise FileNotFoundError(
            "No Google credentials found. Please ensure you have either:\n"
            "1. A credentials.json file (for local development), or\n"
            "2. GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in Streamlit secrets (for deployment)"
        )
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive and return the service object.
        
        Returns:
            Google Drive API service object or None if authentication fails
            
        Raises:
            Exception: If authentication fails
        """
        try:
            logger.info("Starting Google Drive authentication")
            
            # Get credentials file
            creds_file = self._get_credentials_file()
            
            # Load existing token if available
            if os.path.exists(self.token_file):
                logger.info(f"Loading existing token from {self.token_file}")
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
                
                # Get new credentials if needed
                if not self.credentials or not self.credentials.valid:
                    logger.info("Starting OAuth2 flow for new credentials")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                    
                    # Different auth approaches based on environment
                    try:
                        if self._is_streamlit_cloud():
                            logger.info("Running in Streamlit Cloud - using headless auth")
                            # For Streamlit Cloud deployment
                            self.credentials = flow.run_local_server(
                                port=8080,
                                open_browser=False,
                                authorization_prompt_message=(
                                    'Please visit this URL to authorize the application: {url}\n'
                                    'After authorization, return to the app.'
                                ),
                                success_message='Authorization complete! You may close this window and return to the app.'
                            )
                        else:
                            logger.info("Running locally - using standard auth")
                            # For local development
                            self.credentials = flow.run_local_server(
                                port=8080,
                                open_browser=True
                            )
                        
                        # Save the credentials for future use
                        self._save_credentials()
                        logger.info("New credentials obtained and saved")
                        
                    except Exception as oauth_error:
                        logger.error(f"OAuth flow failed: {oauth_error}")
                        raise Exception(f"OAuth authentication failed: {str(oauth_error)}")
            
            # Build the service
            logger.info("Building Google Drive API service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test the service
            if self._test_service():
                logger.info("Google Drive service authenticated and tested successfully")
                return self.service
            else:
                logger.error("Service test failed")
                return None
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise Exception(f"Google Drive authentication failed: {str(e)}")
        
        finally:
            # Clean up temporary credentials file
            if self.temp_credentials_file and os.path.exists(self.temp_credentials_file.name):
                try:
                    os.unlink(self.temp_credentials_file.name)
                    logger.info("Temporary credentials file cleaned up")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
    
    def _is_streamlit_cloud(self) -> bool:
        """
        Check if running on Streamlit Cloud.
        
        Returns:
            True if running on Streamlit Cloud, False otherwise
        """
        return (
            hasattr(st, 'secrets') or 
            os.getenv('STREAMLIT_SHARING_MODE') is not None or
            'streamlit' in os.getenv('HOME', '').lower()
        )
    
    def _save_credentials(self) -> None:
        """Save credentials to token file."""
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
            results = self.service.files().list(
                pageSize=1, 
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Service test passed - able to access Drive (found {len(files)} files in test)")
            return True
            
        except HttpError as e:
            logger.error(f"HTTP error during service test: {e}")
            return False
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
        Check if the user is authenticated and service is ready.
        
        Returns:
            True if authenticated and service is available, False otherwise
        """
        return (
            self.credentials is not None and 
            self.credentials.valid and 
            self.service is not None
        )
    
    def logout(self) -> None:
        """
        Log out by removing stored credentials and clearing service.
        """
        try:
            # Remove token file
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"Failed to remove token file: {e}")
        
        # Clear in-memory objects
        self.credentials = None
        self.service = None
        
        logger.info("Logged out successfully")
    
    def get_user_info(self) -> Optional[dict]:
        """
        Get basic user information if available.
        
        Returns:
            Dictionary with user info or None
        """
        try:
            if self.service:
                # Try to get user info from Drive API
                about = self.service.about().get(fields="user").execute()
                user = about.get('user', {})
                
                return {
                    'email': user.get('emailAddress'),
                    'name': user.get('displayName'),
                    'photo': user.get('photoLink')
                }
        except Exception as e:
            logger.warning(f"Could not get user info: {e}")
        
        return None
    
    def list_recent_files(self, max_files: int = 10) -> list:
        """
        List recent files for testing/debugging purposes.
        
        Args:
            max_files: Maximum number of files to return
            
        Returns:
            List of file dictionaries
        """
        try:
            if not self.service:
                return []
            
            results = self.service.files().list(
                pageSize=max_files,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
