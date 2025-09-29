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
    Google Drive authentication that works with both local credentials and Streamlit secrets.
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
        self.temp_file = None
        
        logger.info("🔧 GoogleDriveAuth initialized - UPDATED VERSION")
    
    def _is_streamlit_cloud(self) -> bool:
        """Check if running on Streamlit Cloud."""
        try:
            # Multiple ways to detect Streamlit Cloud
            if hasattr(st, 'secrets'):
                # Try to access secrets - if it works, we're on Streamlit Cloud
                try:
                    _ = st.secrets
                    logger.info("✅ Detected Streamlit Cloud environment")
                    return True
                except:
                    logger.info("🖥️ Detected local Streamlit environment")
                    return False
            else:
                logger.info("🖥️ Not running in Streamlit environment")
                return False
        except Exception as e:
            logger.warning(f"Could not determine environment: {e}")
            return False
    
    def _check_streamlit_secrets(self) -> bool:
        """Check if Streamlit secrets are properly configured."""
        try:
            if not self._is_streamlit_cloud():
                logger.info("ℹ️ Not on Streamlit Cloud - skipping secrets check")
                return False
            
            # Check for required secrets
            required_secrets = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
            for secret in required_secrets:
                if secret not in st.secrets:
                    logger.error(f"❌ {secret} not found in Streamlit secrets")
                    return False
                else:
                    logger.info(f"✅ {secret} found in Streamlit secrets")
            
            logger.info("✅ All required Streamlit secrets are configured")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking Streamlit secrets: {e}")
            return False
    
    def _create_credentials_from_secrets(self) -> Optional[str]:
        """Create temporary credentials file from Streamlit secrets."""
        try:
            if not self._check_streamlit_secrets():
                logger.error("❌ Cannot create credentials from secrets - secrets not configured")
                return None
            
            logger.info("🔧 Creating credentials from Streamlit secrets...")
            
            # Get secrets
            client_id = st.secrets["GOOGLE_CLIENT_ID"]
            client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
            
            # Create the credentials structure
            credentials_dict = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
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
            self.temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False,
                prefix='streamlit_creds_'
            )
            
            json.dump(credentials_dict, self.temp_file, indent=2)
            self.temp_file.flush()
            self.temp_file.close()
            
            logger.info(f"✅ Temporary credentials file created: {self.temp_file.name}")
            return self.temp_file.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create credentials from Streamlit secrets: {e}")
            return None
    
    def _cleanup_temp_file(self):
        """Clean up temporary credentials file."""
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                os.unlink(self.temp_file.name)
                logger.info("🧹 Temporary credentials file cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean up temp file: {e}")
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive using local file or Streamlit secrets.
        """
        try:
            logger.info("🔍 Starting Google Drive authentication - UPDATED VERSION")
            
            # Environmental diagnosis
            logger.info("🔍 Environment diagnosis:")
            logger.info(f"   • Local credentials.json exists: {os.path.exists(self.credentials_file)}")
            logger.info(f"   • Running on Streamlit Cloud: {self._is_streamlit_cloud()}")
            logger.info(f"   • Streamlit secrets configured: {self._check_streamlit_secrets()}")
            
            # Try to load existing token
            if os.path.exists(self.token_file):
                logger.info("📁 Loading existing token")
                try:
                    self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                    logger.info("✅ Token loaded successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load existing token: {e}")
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
                
                # Need new credentials - determine source
                if not self.credentials or not self.credentials.valid:
                    logger.info("🆕 Need new credentials - determining source")
                    
                    creds_file_path = None
                    using_temp_file = False
                    
                    # Check for local credentials file first (for development)
                    if os.path.exists(self.credentials_file):
                        creds_file_path = self.credentials_file
                        logger.info(f"📄 Using local credentials file: {os.path.abspath(self.credentials_file)}")
                    
                    # Try Streamlit secrets if no local file (for production)
                    elif self._is_streamlit_cloud():
                        logger.info("☁️ On Streamlit Cloud - trying to create credentials from secrets")
                        creds_file_path = self._create_credentials_from_secrets()
                        if creds_file_path:
                            using_temp_file = True
                            logger.info("✅ Successfully created credentials from Streamlit secrets")
                        else:
                            logger.error("❌ Failed to create credentials from Streamlit secrets")
                    
                    else:
                        logger.info("🖥️ Local environment - no credentials.json found")
                    
                    # No credentials source available
                    if not creds_file_path:
                        # Create detailed error message based on environment
                        if self._is_streamlit_cloud():
                            error_msg = (
                                "❌ STREAMLIT CLOUD ERROR:\n"
                                "No Google Drive credentials configured!\n\n"
                                "REQUIRED: Set these secrets in Streamlit Cloud:\n"
                                "• GOOGLE_CLIENT_ID\n"
                                "• GOOGLE_CLIENT_SECRET\n\n"
                                f"Current status:\n"
                                f"• Streamlit secrets exist: {hasattr(st, 'secrets')}\n"
                                f"• GOOGLE_CLIENT_ID configured: {'GOOGLE_CLIENT_ID' in st.secrets if hasattr(st, 'secrets') else 'N/A'}\n"
                                f"• GOOGLE_CLIENT_SECRET configured: {'GOOGLE_CLIENT_SECRET' in st.secrets if hasattr(st, 'secrets') else 'N/A'}"
                            )
                        else:
                            error_msg = (
                                "❌ LOCAL DEVELOPMENT ERROR:\n"
                                "No Google Drive credentials found!\n\n"
                                "REQUIRED: Create credentials.json file\n"
                                f"Expected location: {os.path.abspath(self.credentials_file)}\n\n"
                                "How to fix:\n"
                                "1. Go to Google Cloud Console\n"
                                "2. Create OAuth 2.0 credentials\n"
                                "3. Download credentials.json\n"
                                "4. Place it in your project root directory"
                            )
                        
                        logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    # Run OAuth flow
                    try:
                        logger.info(f"🔐 Starting OAuth flow with credentials: {creds_file_path}")
                        
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file_path, self.SCOPES)
                        
                        # Run OAuth flow
                        if using_temp_file:
                            # Streamlit Cloud
                            logger.info("☁️ Running OAuth flow for Streamlit Cloud")
                            self.credentials = flow.run_local_server(
                                port=8080,
                                authorization_prompt_message=(
                                    'Please visit this URL to authorize the application: {url}\n'
                                    'After authorization, return to the app.'
                                ),
                                success_message='Authorization complete! You can close this browser window.',
                                open_browser=False
                            )
                        else:
                            # Local development
                            logger.info("💻 Running OAuth flow for local development")
                            self.credentials = flow.run_local_server(
                                port=8080,
                                authorization_prompt_message='Please visit this URL to authorize: {url}',
                                success_message='Authorization complete! You can close this window.',
                                open_browser=True
                            )
                        
                        # Save credentials for next time
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
            # Re-raise the error with better formatting
            raise Exception(str(e))
    
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
            logger.info(f"✅ Service test passed - accessible files found: {len(files)}")
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
        """Log out and clean up all authentication data."""
        try:
            # Remove token file
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"🗑️ Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to remove token file: {e}")
        
        # Clean up temporary files
        self._cleanup_temp_file()
        
        # Clear in-memory objects
        self.credentials = None
        self.service = None
        
        logger.info("👋 Logged out successfully")
