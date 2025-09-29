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
    Supports both local credentials.json files and Streamlit secrets.
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
        self.temp_creds_file = None
        
        logger.info(f"GoogleDriveAuth initialized with credentials file: {credentials_file}")
    
    def _is_streamlit_cloud(self) -> bool:
        """
        Check if running on Streamlit Cloud.
        
        Returns:
            True if running on Streamlit Cloud, False if local
        """
        return (
            hasattr(st, 'secrets') or
            'STREAMLIT_SHARING_MODE' in os.environ or
            'streamlit' in os.getcwd().lower()
        )
    
    def _create_credentials_from_secrets(self) -> Optional[str]:
        """
        Create temporary credentials file from Streamlit secrets.
        
        Returns:
            Path to temporary credentials file or None if failed
        """
        try:
            # Check if Streamlit secrets are available
            if not (hasattr(st, 'secrets') and 'GOOGLE_CLIENT_ID' in st.secrets and 'GOOGLE_CLIENT_SECRET' in st.secrets):
                logger.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not found in Streamlit secrets")
                return None
            
            logger.info("Creating temporary credentials from Streamlit secrets")
            
            # Create credentials dictionary
            credentials_dict = {
                "web": {
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [
                        "https://intelligent-agent-menna.streamlit.app/",
                        "https://intelligent-agent-menna.streamlit.app/_oauth2callback"
                    ]
                }
            }
            
            # Create temporary file
            self.temp_creds_file = tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False,
                prefix='streamlit_creds_'
            )
            
            # Write credentials to temp file
            json.dump(credentials_dict, self.temp_creds_file, indent=2)
            self.temp_creds_file.flush()
            self.temp_creds_file.close()
            
            logger.info(f"Temporary credentials file created: {self.temp_creds_file.name}")
            return self.temp_creds_file.name
            
        except Exception as e:
            logger.error(f"Failed to create credentials from Streamlit secrets: {str(e)}")
            return None
    
    def _cleanup_temp_file(self):
        """Clean up temporary credentials file if it exists."""
        if self.temp_creds_file and os.path.exists(self.temp_creds_file.name):
            try:
                os.unlink(self.temp_creds_file.name)
                logger.info("Temporary credentials file cleaned up")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {e}")
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive and return the service object.
        Works both locally (with credentials.json) and on Streamlit Cloud (with secrets).
        
        Returns:
            Google Drive API service object or None if authentication fails
        """
        try:
            logger.info("Starting Google Drive authentication")
            
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
                    
                    # Determine credentials source
                    creds_file_path = None
                    temp_file_created = False
                    
                    if os.path.exists(self.credentials_file):
                        # Local development - use credentials.json file
                        creds_file_path = self.credentials_file
                        logger.info(f"Using local credentials file: {self.credentials_file}")
                    elif self._is_streamlit_cloud():
                        # Streamlit Cloud - create from secrets
                        creds_file_path = self._create_credentials_from_secrets()
                        if creds_file_path:
                            temp_file_created = True
                            logger.info("Using credentials from Streamlit secrets")
                        else:
                            raise Exception("Failed to create credentials from Streamlit secrets")
                    else:
                        raise FileNotFoundError(
                            f"Credentials file '{self.credentials_file}' not found. "
                            f"Please download it from Google Cloud Console or set up Streamlit secrets."
                        )
                    
                    if not creds_file_path:
                        raise Exception("No valid credentials source found")
                    
                    try:
                        # Create OAuth flow
                        flow = InstalledAppFlow.from_client_secrets_file(
                            creds_file_path, 
                            self.SCOPES
                        )
                        
                        # Run OAuth flow
                        if self._is_streamlit_cloud():
                            # For Streamlit Cloud, try different approaches
                            logger.info("Running OAuth flow for Streamlit Cloud")
                            try:
                                # First attempt: standard local server
                                self.credentials = flow.run_local_server(
                                    port=8080,
                                    authorization_prompt_message=(
                                        'Please visit this URL to authorize the application: {url}\n'
                                        'After authorization, you can return to the app.'
                                    ),
                                    success_message='Authorization complete! You may close this window.',
                                    open_browser=False
                                )
                            except Exception as cloud_error:
                                logger.warning(f"Cloud OAuth attempt 1 failed: {cloud_error}")
                                # Second attempt: try with different settings
                                self.credentials = flow.run_local_server(
                                    port=0,  # Use any available port
                                    authorization_prompt_message='Please visit this URL: {url}',
                                    success_message='Authorization complete!',
                                    open_browser=False
                                )
                        else:
                            # Local development
                            logger.info("Running OAuth flow for local development")
                            self.credentials = flow.run_local_server(
                                port=8080,
                                authorization_prompt_message='Please visit this URL to authorize the application: {url}',
                                success_message='Authorization complete! You may close this window.',
                                open_browser=True
                            )
                        
                        # Save the credentials for next time
                        self._save_credentials()
                        logger.info("New credentials obtained and saved")
                        
                    except Exception as oauth_error:
                        logger.error(f"OAuth flow failed: {oauth_error}")
                        raise Exception(f"OAuth authentication failed: {str(oauth_error)}")
                    
                    finally:
                        # Clean up temporary file if created
                        if temp_file_created:
                            self._cleanup_temp_file()
            
            # Build the Google Drive service
            logger.info("Building Google Drive API service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test the service to make sure it works
            if self._test_service():
                logger.info("✅ Google Drive service created and tested successfully")
                return self.service
            else:
                logger.error("❌ Service test failed")
                return None
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            # Clean up any temporary files
            self._cleanup_temp_file()
            raise Exception(f"Google Drive authentication failed: {str(e)}")
    
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
            logger.info(f"Service test passed - able to access Drive ({len(files)} files found in test)")
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
        Check if the user is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        return (
            self.credentials is not None and 
            self.credentials.valid and 
            self.service is not None
        )
    
    def logout(self) -> None:
        """
        Log out by removing stored credentials.
        """
        try:
            # Remove token file
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"Failed to remove token file: {e}")
        
        # Clean up temporary files
        self._cleanup_temp_file()
        
        # Clear in-memory objects
        self.credentials = None
        self.service = None
        
        logger.info("Logged out successfully")
    
    def get_auth_url(self) -> Optional[str]:
        """
        Get authorization URL for manual OAuth flow (useful for Streamlit Cloud).
        
        Returns:
            Authorization URL or None if failed
        """
        try:
            creds_file_path = None
            
            if os.path.exists(self.credentials_file):
                creds_file_path = self.credentials_file
            elif self._is_streamlit_cloud():
                creds_file_path = self._create_credentials_from_secrets()
            
            if not creds_file_path:
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_file_path, self.SCOPES)
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'  # For manual flow
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to get auth URL: {e}")
            return None
    
    def complete_auth_with_code(self, auth_code: str) -> bool:
        """
        Complete authentication with authorization code (for manual flow).
        
        Args:
            auth_code: Authorization code from Google OAuth
            
        Returns:
            True if successful, False otherwise
        """
        try:
            creds_file_path = None
            temp_file_created = False
            
            if os.path.exists(self.credentials_file):
                creds_file_path = self.credentials_file
            elif self._is_streamlit_cloud():
                creds_file_path = self._create_credentials_from_secrets()
                temp_file_created = True
            
            if not creds_file_path:
                return False
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_file_path, self.SCOPES)
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            
            # Exchange code for credentials
            flow.fetch_token(code=auth_code)
            self.credentials = flow.credentials
            
            # Save credentials
            self._save_credentials()
            
            # Build service
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Clean up
            if temp_file_created:
                self._cleanup_temp_file()
            
            return self._test_service()
            
        except Exception as e:
            logger.error(f"Failed to complete auth with code: {e}")
            if temp_file_created:
                self._cleanup_temp_file()
            return False
