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
    Google Drive authentication handler for Streamlit Cloud with secrets support.
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials = None
        self.service = None
        self.temp_creds_file = None
        
        logger.info("GoogleDriveAuth initialized for Streamlit Cloud")
    
    def _has_streamlit_secrets(self) -> bool:
        """Check if Streamlit secrets are available and valid."""
        try:
            if not hasattr(st, 'secrets'):
                logger.info("st.secrets not available")
                return False
            
            if 'GOOGLE_CLIENT_ID' not in st.secrets:
                logger.error("GOOGLE_CLIENT_ID not found in Streamlit secrets")
                return False
                
            if 'GOOGLE_CLIENT_SECRET' not in st.secrets:
                logger.error("GOOGLE_CLIENT_SECRET not found in Streamlit secrets")
                return False
            
            logger.info("✅ Streamlit secrets found and valid")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Streamlit secrets: {e}")
            return False
    
    def _create_credentials_from_secrets(self) -> Optional[str]:
        """Create temporary credentials file from Streamlit secrets."""
        try:
            if not self._has_streamlit_secrets():
                return None
            
            logger.info("Creating credentials from Streamlit secrets")
            
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
            
            json.dump(credentials_dict, self.temp_creds_file, indent=2)
            self.temp_creds_file.flush()
            self.temp_creds_file.close()
            
            logger.info(f"✅ Temporary credentials file created: {self.temp_creds_file.name}")
            return self.temp_creds_file.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create credentials from secrets: {e}")
            return None
    
    def _cleanup_temp_file(self):
        """Clean up temporary credentials file."""
        if self.temp_creds_file and os.path.exists(self.temp_creds_file.name):
            try:
                os.unlink(self.temp_creds_file.name)
                logger.info("Temporary file cleaned up")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive using local file or Streamlit secrets.
        """
        try:
            logger.info("🔍 Starting Google Drive authentication")
            
            # Load existing token if available
            if os.path.exists(self.token_file):
                logger.info("📁 Loading existing token")
                try:
                    self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                except Exception as e:
                    logger.warning(f"Failed to load existing token: {e}")
                    self.credentials = None
            
            # Check if credentials need refresh or are invalid
            if not self.credentials or not self.credentials.valid:
                # Try to refresh expired credentials
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("🔄 Attempting to refresh expired credentials")
                    try:
                        self.credentials.refresh(Request())
                        logger.info("✅ Credentials refreshed successfully")
                    except Exception as refresh_error:
                        logger.warning(f"❌ Failed to refresh credentials: {refresh_error}")
                        self.credentials = None
                
                # Need new credentials - try OAuth flow
                if not self.credentials or not self.credentials.valid:
                    logger.info("🆕 Need new credentials - starting OAuth flow")
                    
                    # Determine credentials source
                    creds_file_path = None
                    using_temp_file = False
                    
                    # Check for local credentials file
                    if os.path.exists(self.credentials_file):
                        creds_file_path = self.credentials_file
                        logger.info(f"📄 Using local credentials file: {self.credentials_file}")
                    
                    # Try Streamlit secrets if no local file
                    elif self._has_streamlit_secrets():
                        creds_file_path = self._create_credentials_from_secrets()
                        if creds_file_path:
                            using_temp_file = True
                            logger.info("☁️ Using credentials from Streamlit secrets")
                        else:
                            logger.error("❌ Failed to create credentials from Streamlit secrets")
                    
                    # No credentials source available
                    if not creds_file_path:
                        error_msg = (
                            "No Google credentials found. Please ensure:\n"
                            "1. credentials.json file exists (for local development), OR\n"
                            "2. GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set in Streamlit secrets\n\n"
                            "Current environment check:\n"
                            f"- Local credentials.json exists: {os.path.exists(self.credentials_file)}\n"
                            f"- Streamlit secrets available: {self._has_streamlit_secrets()}"
                        )
                        logger.error(error_msg)
                        raise FileNotFoundError(error_msg)
                    
                    # Run OAuth flow
                    try:
                        logger.info(f"🔐 Starting OAuth flow with credentials file: {creds_file_path}")
                        
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file_path, self.SCOPES)
                        
                        # Try OAuth flow
                        self.credentials = flow.run_local_server(
                            port=8080,
                            authorization_prompt_message=(
                                'Please visit this URL to authorize the application: {url}\n'
                                'After completing authorization, return to the application.'
                            ),
                            success_message='Authorization successful! You can close this browser window.',
                            open_browser=False  # Don't open browser on Streamlit Cloud
                        )
                        
                        # Save credentials
                        self._save_credentials()
                        logger.info("✅ New credentials obtained and saved")
                        
                    except Exception as oauth_error:
                        logger.error(f"❌ OAuth flow failed: {oauth_error}")
                        raise Exception(f"OAuth authentication failed: {str(oauth_error)}")
                    
                    finally:
                        # Clean up temporary file
                        if using_temp_file:
                            self._cleanup_temp_file()
            
            # Build Google Drive service
            logger.info("🔨 Building Google Drive API service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test the service
            if self._test_service():
                logger.info("✅ Google Drive service authenticated and tested successfully!")
                return self.service
            else:
                logger.error("❌ Service authentication test failed")
                return None
                
        except Exception as e:
            logger.error(f"💥 Critical authentication error: {str(e)}")
            # Clean up on error
            self._cleanup_temp_file()
            raise Exception(f"Google Drive authentication failed: {str(e)}")
    
    def _save_credentials(self) -> None:
        """Save credentials to token file."""
        try:
            with open(self.token_file, 'w') as token_file:
                token_file.write(self.credentials.to_json())
            logger.info(f"💾 Credentials saved to {self.token_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save credentials: {e}")
    
    def _test_service(self) -> bool:
        """Test the Google Drive service."""
        try:
            logger.info("🧪 Testing Google Drive service connection...")
            results = self.service.files().list(pageSize=1, fields="files(id, name)").execute()
            files = results.get('files', [])
            logger.info(f"✅ Service test passed - found {len(files)} files")
            return True
        except HttpError as e:
            logger.error(f"❌ HTTP error during service test: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Service test failed: {e}")
            return False
    
    def get_service(self) -> Optional[object]:
        return self.service
    
    def is_authenticated(self) -> bool:
        return (
            self.credentials is not None and 
            self.credentials.valid and 
            self.service is not None
        )
    
    def logout(self) -> None:
        """Log out and clean up."""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"🗑️ Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"Failed to remove token file: {e}")
        
        self._cleanup_temp_file()
        self.credentials = None
        self.service = None
        logger.info("👋 Logged out successfully")
