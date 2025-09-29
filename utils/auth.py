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
    Google Drive authentication that handles both local development and Streamlit Cloud.
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
        
        # This is the INDICATOR that the new code is running
        logger.info("🆕 NEW AUTHENTICATION CODE LOADED - VERSION 4.0 - PROJECT_ID FIXED")
        print("🆕 NEW AUTHENTICATION CODE LOADED - VERSION 4.0 - PROJECT_ID FIXED")

    def _detect_environment(self):
        """Detect if we're running locally or on Streamlit Cloud."""
        try:
            # Check for local credentials file
            has_local_creds = os.path.exists(self.credentials_file)
            
            # Check if we can access Streamlit secrets
            has_streamlit_secrets = False
            secrets_accessible = False
            
            if hasattr(st, 'secrets'):
                try:
                    # Try to access secrets without triggering error
                    secrets_dict = dict(st.secrets)
                    secrets_accessible = True
                    has_streamlit_secrets = (
                        'GOOGLE_CLIENT_ID' in secrets_dict and 
                        'GOOGLE_CLIENT_SECRET' in secrets_dict and
                        'GOOGLE_PROJECT_ID' in secrets_dict  # FIXED: Added project_id check
                    )
                except Exception as e:
                    logger.warning(f"Failed to access secrets: {e}")
                    secrets_accessible = False
                    has_streamlit_secrets = False

            logger.info("🔍 ENVIRONMENT DETECTION:")
            logger.info(f"   • Local credentials.json exists: {has_local_creds}")
            logger.info(f"   • Streamlit secrets accessible: {secrets_accessible}")
            logger.info(f"   • Google credentials in secrets: {has_streamlit_secrets}")

            return {
                'has_local_creds': has_local_creds,
                'has_streamlit_secrets': has_streamlit_secrets,
                'secrets_accessible': secrets_accessible,
                'environment': 'streamlit_cloud' if secrets_accessible else 'local'
            }

        except Exception as e:
            logger.error(f"Environment detection failed: {e}")
            return {
                'has_local_creds': False,
                'has_streamlit_secrets': False,
                'secrets_accessible': False,
                'environment': 'unknown'
            }

    def _create_temp_credentials(self, env_info):
        """Create temporary credentials file from Streamlit secrets."""
        if not env_info['has_streamlit_secrets']:
            logger.error("❌ Cannot create temp credentials - Streamlit secrets not configured")
            return None

        try:
            logger.info("🔧 Creating temporary credentials from Streamlit secrets...")
            
            # Get credentials from secrets
            client_id = st.secrets["GOOGLE_CLIENT_ID"]
            client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
            project_id = st.secrets["GOOGLE_PROJECT_ID"]  # FIXED: Get project_id
            
            # Create credentials structure
            credentials_dict = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "project_id": project_id,  # FIXED: Added project_id
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [
                        "http://localhost:8080",
                        "http://localhost:8501"
                    ]
                }
            }

            # Create temporary file
            self.temp_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, prefix='streamlit_creds_'
            )
            
            json.dump(credentials_dict, self.temp_file, indent=2)
            self.temp_file.flush()
            self.temp_file.close()
            
            logger.info(f"✅ Temporary credentials created: {self.temp_file.name}")
            return self.temp_file.name

        except Exception as e:
            logger.error(f"❌ Failed to create temp credentials: {e}")
            return None

    def authenticate(self) -> Optional[object]:
        """Main authentication method."""
        try:
            logger.info("🚀 STARTING AUTHENTICATION WITH FIXED CODE")
            
            # Detect environment
            env_info = self._detect_environment()
            
            # Load existing token if available
            if os.path.exists(self.token_file):
                logger.info("📁 Loading existing token...")
                try:
                    self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                    if self.credentials.valid:
                        logger.info("✅ Existing token is valid")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load existing token: {e}")
                    self.credentials = None

            # Refresh expired credentials
            if (self.credentials and 
                self.credentials.expired and 
                self.credentials.refresh_token):
                logger.info("🔄 Refreshing expired credentials...")
                try:
                    self.credentials.refresh(Request())
                    logger.info("✅ Credentials refreshed successfully")
                except Exception as e:
                    logger.warning(f"❌ Failed to refresh: {e}")
                    self.credentials = None

            # Get new credentials if needed
            if not self.credentials or not self.credentials.valid:
                logger.info("🆕 Getting new credentials...")
                creds_file = None
                using_temp_file = False

                # Determine credentials source
                if env_info['has_local_creds']:
                    creds_file = self.credentials_file
                    logger.info(f"📄 Using local credentials: {os.path.abspath(creds_file)}")
                elif env_info['has_streamlit_secrets']:
                    creds_file = self._create_temp_credentials(env_info)
                    if creds_file:
                        using_temp_file = True
                        logger.info("☁️ Using Streamlit secrets credentials")
                    else:
                        logger.error("❌ Failed to create credentials from secrets")

                # Handle no credentials case
                if not creds_file:
                    if env_info['environment'] == 'streamlit_cloud':
                        error_msg = (
                            "❌ STREAMLIT CLOUD: No Google credentials configured!\n\n"
                            "SOLUTION:\n"
                            "1. Go to your Streamlit Cloud app settings\n"
                            "2. Add these secrets:\n"
                            "   GOOGLE_CLIENT_ID = \"your-client-id\"\n"
                            "   GOOGLE_CLIENT_SECRET = \"your-client-secret\"\n"
                            "   GOOGLE_PROJECT_ID = \"your-project-id\"\n\n"
                            f"Current status:\n"
                            f"• Secrets accessible: {env_info['secrets_accessible']}\n"
                            f"• Google secrets configured: {env_info['has_streamlit_secrets']}"
                        )
                    else:
                        error_msg = (
                            "❌ LOCAL DEVELOPMENT: No credentials.json found!\n\n"
                            "SOLUTION:\n"
                            "1. Go to Google Cloud Console\n"
                            "2. Create OAuth 2.0 credentials\n"
                            "3. Download credentials.json\n"
                            f"4. Place it here: {os.path.abspath(self.credentials_file)}\n\n"
                            f"Current location checked: {os.path.abspath(self.credentials_file)}\n"
                            f"File exists: {os.path.exists(self.credentials_file)}"
                        )
                    
                    logger.error(error_msg)
                    raise Exception(error_msg)

                # Run OAuth flow
                try:
                    logger.info(f"🔐 Starting OAuth flow with: {creds_file}")
                    flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                    
                    # Always use headless mode for cloud deployments
                    self.credentials = flow.run_local_server(
                        port=8080,
                        open_browser=False,
                        authorization_prompt_message='Visit this URL to authenticate: {url}',
                        success_message='Authentication successful! You can now close this tab.'
                    )

                    # Save credentials
                    self._save_credentials()
                    logger.info("✅ New credentials saved")

                except Exception as oauth_error:
                    logger.error(f"❌ OAuth failed: {oauth_error}")
                    raise Exception(f"OAuth authentication failed: {str(oauth_error)}")
                
                finally:
                    # Cleanup
                    if using_temp_file and self.temp_file and os.path.exists(self.temp_file.name):
                        try:
                            os.unlink(self.temp_file.name)
                            logger.info("🧹 Cleaned up temp credentials")
                        except:
                            pass

            # Build and test service
            logger.info("🔨 Building Google Drive service...")
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            if self._test_service():
                logger.info("✅ AUTHENTICATION SUCCESSFUL!")
                return self.service
            else:
                logger.error("❌ Service test failed")
                return None

        except Exception as e:
            logger.error(f"💥 AUTHENTICATION FAILED: {str(e)}")
            raise e

    def _save_credentials(self):
        """Save credentials to token file."""
        try:
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            logger.info(f"💾 Credentials saved to {self.token_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save: {e}")

    def _test_service(self):
        """Test Google Drive service."""
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
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
                logger.info(f"🗑️ Removed {self.token_file}")
            except:
                pass
        
        self.credentials = None
        self.service = None
        logger.info("👋 Logged out")
