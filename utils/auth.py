import streamlit as st
import os
import json
import tempfile
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveAuth:
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    def __init__(self,
                 credentials_file: str = "credentials.json",
                 token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials: Optional[Credentials] = None
        self.service = None
        self._temp_creds_path: Optional[str] = None
        logger.info("🆕 AUTH CODE LOADED - Streamlit Cloud Compatible")
    
    def _env_info(self) -> Dict[str, bool]:
        """Check available credential sources"""
        has_local = os.path.exists(self.credentials_file)
        has_secrets = False
        can_access = False
        
        if hasattr(st, "secrets"):
            try:
                _ = dict(st.secrets)
                can_access = True
                has_secrets = ("GOOGLE_CLIENT_ID" in st.secrets and 
                              "GOOGLE_CLIENT_SECRET" in st.secrets)
            except:
                pass
        
        return {"local": has_local, "secrets": has_secrets, "can_access": can_access}
    
    def _create_temp_credentials(self) -> Optional[str]:
        """Create temporary credentials file from Streamlit secrets"""
        info = self._env_info()
        if not info["secrets"]:
            logger.error("No Streamlit secrets found")
            return None
        
        try:
            # Create credentials JSON structure
            creds = {
                "installed": {
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"]
                }
            }
            
            # Create temporary file
            tf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix="tmp_creds_"
            )
            json.dump(creds, tf, indent=2)
            tf.flush()
            tf.close()
            
            self._temp_creds_path = tf.name
            logger.info(f"✅ Created temporary credentials file: {tf.name}")
            return tf.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create temp credentials: {e}")
            return None
    
    def _load_existing_token(self) -> bool:
        """Load token from Streamlit secrets (refresh token)"""
        # Try loading from Streamlit secrets first (for cloud deployment)
        if hasattr(st, "secrets") and "GOOGLE_REFRESH_TOKEN" in st.secrets:
            try:
                token_info = {
                    "refresh_token": st.secrets["GOOGLE_REFRESH_TOKEN"],
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "scopes": self.SCOPES
                }
                self.credentials = Credentials.from_authorized_user_info(token_info)
                logger.info("✅ Loaded credentials from Streamlit secrets")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load token from secrets: {e}")
        
        # Try loading from local token file (for development)
        if os.path.exists(self.token_file):
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.SCOPES
                )
                logger.info("✅ Loaded credentials from local token file")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load local token: {e}")
        
        return False
    
    def authenticate(self) -> Optional[object]:
        """Authenticate with Google Drive API"""
        info = self._env_info()
        logger.info(f"🔍 ENV INFO: {info}")
        
        # Load existing token
        self._load_existing_token()
        
        # Refresh if expired
        if (self.credentials and self.credentials.expired 
            and self.credentials.refresh_token):
            try: 
                self.credentials.refresh(Request())
                logger.info("🔄 Refreshed expired credentials")
            except Exception as e:
                logger.warning(f"⚠️ Failed to refresh credentials: {e}")
                self.credentials = None
        
        # Get new credentials if needed
        if not self.credentials or not self.credentials.valid:
            # Determine credential source
            if info["local"]:
                secret_path = self.credentials_file
                logger.info("📁 Using local credentials file")
            elif info["secrets"]:
                secret_path = self._create_temp_credentials()
                if not secret_path:
                    raise Exception("❌ Failed to create temporary credentials file")
                logger.info("☁️ Using Streamlit secrets for credentials")
            else:
                # Better error message for cloud deployment
                raise Exception(
                    "❌ Google Drive authentication failed: No credentials available.\n\n"
                    "For Streamlit Cloud deployment, please:\n"
                    "1. Go to your Streamlit Cloud app settings\n"
                    "2. Add the following secrets:\n"
                    "   GOOGLE_CLIENT_ID = \"your_client_id\"\n"
                    "   GOOGLE_CLIENT_SECRET = \"your_client_secret\"\n\n"
                    "For local development:\n"
                    "1. Download credentials.json from Google Cloud Console\n"
                    "2. Place it in your project root directory"
                )
            
            # Create OAuth flow
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    secret_path, self.SCOPES
                )
                
                # For cloud deployment, use manual OAuth flow
                is_cloud = not info["local"]
                
                if is_cloud:
                    # Manual OAuth flow for Streamlit Cloud
                    st.error("🔐 **Google Drive Authentication Required**")
                    st.info("Please complete the OAuth authorization process:")
                    
                    # Generate authorization URL
                    auth_url, _ = flow.authorization_url(
                        prompt='consent',
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    
                    st.markdown(f"**Step 1:** [🔗 Click here to authorize with Google]({auth_url})")
                    st.markdown("**Step 2:** Copy the authorization code from the redirect URL")
                    st.markdown("*(Look for 'code=' in the URL after authorization)*")
                    
                    # Get authorization code from user
                    auth_code = st.text_input(
                        "**Step 3:** Paste the authorization code here:",
                        type="password",
                        help="After clicking the authorization link, copy the 'code' parameter from the URL"
                    )
                    
                    if auth_code:
                        try:
                            # Exchange code for tokens
                            flow.fetch_token(code=auth_code.strip())
                            self.credentials = flow.credentials
                            
                            # Display success and next steps
                            st.success("✅ **Authentication successful!**")
                            
                            # Show refresh token for saving
                            if self.credentials.refresh_token:
                                st.info("🔑 **Save this refresh token in your Streamlit secrets:**")
                                st.code(f"GOOGLE_REFRESH_TOKEN = \"{self.credentials.refresh_token}\"")
                                st.markdown("*Add this to your Streamlit Cloud app secrets to avoid re-authentication*")
                            
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"❌ **Authentication failed:** {str(e)}")
                            st.info("Please try again with a fresh authorization code")
                            return None
                    else:
                        st.warning("⏳ Waiting for authorization code...")
                        return None
                        
                else:
                    # Local development - use built-in server
                    self.credentials = flow.run_local_server(
                        port=8080,
                        open_browser=True,
                        authorization_prompt_message="Please visit: {url}",
                        success_message="✅ Authentication complete! You can close this window."
                    )
                    
                    # Save token locally
                    with open(self.token_file, "w") as f:
                        f.write(self.credentials.to_json())
                    logger.info("💾 Saved credentials to local token file")
                    
            except Exception as e:
                logger.error(f"❌ OAuth flow failed: {e}")
                raise Exception(f"OAuth flow failed: {str(e)}")
        
        # Cleanup temporary credentials file
        if self._temp_creds_path:
            try: 
                os.unlink(self._temp_creds_path)
                logger.info("🧹 Cleaned up temporary credentials file")
            except: 
                pass
        
        # Build and test service
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            # Test the service with a simple API call
            self.service.files().list(pageSize=1).execute()
            logger.info("✅ Google Drive service successfully initialized and tested")
            return self.service
            
        except HttpError as e:
            logger.error(f"❌ Drive service test failed: {e}")
            raise Exception(f"Google Drive service test failed: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            raise Exception(f"Service initialization failed: {str(e)}")
