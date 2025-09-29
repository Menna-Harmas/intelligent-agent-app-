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
    Google Drive authentication that works with Streamlit Secrets.
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
        
        logger.info("GoogleDriveAuth initialized")
    
    def _check_streamlit_secrets(self):
        """Check if Streamlit secrets are available"""
        try:
            # Debug: Log what's available
            if hasattr(st, 'secrets'):
                logger.info("✅ st.secrets is available")
                if 'GOOGLE_CLIENT_ID' in st.secrets:
                    logger.info("✅ GOOGLE_CLIENT_ID found in secrets")
                else:
                    logger.error("❌ GOOGLE_CLIENT_ID not found in secrets")
                    return False
                    
                if 'GOOGLE_CLIENT_SECRET' in st.secrets:
                    logger.info("✅ GOOGLE_CLIENT_SECRET found in secrets")
                else:
                    logger.error("❌ GOOGLE_CLIENT_SECRET not found in secrets")
                    return False
                    
                return True
            else:
                logger.error("❌ st.secrets not available")
                return False
                
        except Exception as e:
            logger.error(f"Error checking secrets: {e}")
            return False
    
    def _create_credentials_from_secrets(self):
        """Create temp credentials file from Streamlit secrets"""
        try:
            if not self._check_streamlit_secrets():
                return None
            
            logger.info("Creating credentials from Streamlit secrets...")
            
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
            
            # Create temp file
            self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(credentials_dict, self.temp_file, indent=2)
            self.temp_file.flush()
            self.temp_file.close()
            
            logger.info(f"✅ Temp credentials created: {self.temp_file.name}")
            return self.temp_file.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create credentials from secrets: {e}")
            return None
    
    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive
        """
        try:
            logger.info("🔍 Starting Google Drive authentication")
            
            # Load existing token
            if os.path.exists(self.token_file):
                logger.info("📁 Loading existing token")
                self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
            
            # Check if credentials need refresh
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    try:
                        logger.info("🔄 Refreshing expired credentials")
                        self.credentials.refresh(Request())
                        logger.info("✅ Credentials refreshed successfully")
                    except Exception as e:
                        logger.warning(f"❌ Failed to refresh: {e}")
                        self.credentials = None
                
                # Need new credentials
                if not self.credentials or not self.credentials.valid:
                    logger.info("🆕 Getting new credentials")
                    
                    # Try local file first
                    creds_file = None
                    temp_created = False
                    
                    if os.path.exists(self.credentials_file):
                        creds_file = self.credentials_file
                        logger.info(f"📄 Using local file: {self.credentials_file}")
                    else:
                        # Try Streamlit secrets
                        logger.info("☁️ No local file, trying Streamlit secrets")
                        creds_file = self._create_credentials_from_secrets()
                        if creds_file:
                            temp_created = True
                            logger.info("✅ Using Streamlit secrets")
                        else:
                            # Show detailed error for debugging
                            error_msg = "❌ No credentials available!\n\n"
                            error_msg += "Current status:\n"
                            error_msg += f"• Local credentials.json exists: {os.path.exists(self.credentials_file)}\n"
                            error_msg += f"• Streamlit secrets available: {hasattr(st, 'secrets')}\n"
                            
                            if hasattr(st, 'secrets'):
                                error_msg += f"• GOOGLE_CLIENT_ID in secrets: {'GOOGLE_CLIENT_ID' in st.secrets}\n"
                                error_msg += f"• GOOGLE_CLIENT_SECRET in secrets: {'GOOGLE_CLIENT_SECRET' in st.secrets}\n"
                            
                            logger.error(error_msg)
                            raise FileNotFoundError("Credentials file 'credentials.json' not found. Please download it from Google Cloud Console.")
                    
                    # Run OAuth flow
                    try:
                        logger.info(f"🔐 Starting OAuth with: {creds_file}")
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                        
                        self.credentials = flow.run_local_server(
                            port=8080,
                            open_browser=False,
                            authorization_prompt_message='Visit this URL to authorize: {url}'
                        )
                        
                        self._save_credentials()
                        logger.info("✅ New credentials saved")
                        
                    finally:
                        # Clean up temp file
                        if temp_created and self.temp_file and os.path.exists(self.temp_file.name):
                            try:
                                os.unlink(self.temp_file.name)
                                logger.info("🧹 Temp file cleaned up")
                            except:
                                pass
            
            # Build service
            logger.info("🔨 Building Google Drive service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test service
            if self._test_service():
                logger.info("✅ Google Drive authenticated successfully!")
                return self.service
            else:
                logger.error("❌ Service test failed")
                return None
                
        except Exception as e:
            logger.error(f"💥 Authentication error: {str(e)}")
            raise Exception(f"Google Drive authentication failed: {str(e)}")
    
    def _save_credentials(self):
        """Save credentials to file"""
        try:
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            logger.info("💾 Credentials saved")
        except Exception as e:
            logger.error(f"❌ Failed to save credentials: {e}")
    
    def _test_service(self):
        """Test Google Drive service"""
        try:
            results = self.service.files().list(pageSize=1, fields="files(id, name)").execute()
            logger.info("🧪 Service test passed")
            return True
        except Exception as e:
            logger.error(f"❌ Service test failed: {e}")
            return False
    
    def get_service(self):
        return self.service
    
    def is_authenticated(self):
        return (self.credentials is not None and 
                self.credentials.valid and 
                self.service is not None)
    
    def logout(self):
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
        except:
            pass
        
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                os.unlink(self.temp_file.name)
            except:
                pass
        
        self.credentials = None
        self.service = None
        logger.info("👋 Logged out")
