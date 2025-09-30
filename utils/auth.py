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
        logger.info("🆕 AUTH CODE LOADED (Streamlit Cloud compatible)")
    
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
            return None
        
        # Create credentials JSON structure for OAuth2 web application
        creds = {
            "web": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [
                    "http://localhost:8501",
                    "http://localhost:8501/",
                    "https://intelligent-agent-menna.streamlit.app/",
                    "https://intelligent-agent-menna.streamlit.app"
                ]
            }
        }
        
        # Create temporary file
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="tmp_creds_"
        )
        json.dump(creds, tf, indent=2)
        tf.flush(); tf.close()
        
        self._temp_creds_path = tf.name
        logger.info(f"Created temporary credentials file: {tf.name}")
        return tf.name
    
    def _load_existing_token(self) -> bool:
        """Load token from file or Streamlit secrets"""
        # Try loading from local token file first
        if os.path.exists(self.token_file):
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.SCOPES
                )
                logger.info("Loaded credentials from local token file")
                return True
            except Exception as e:
                logger.warning(f"Failed to load local token: {e}")
        
        # Try loading from Streamlit secrets
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
                logger.info("Loaded credentials from Streamlit secrets")
                return True
            except Exception as e:
                logger.warning(f"Failed to load token from secrets: {e}")
        
        return False
    
    def authenticate(self) -> Optional[object]:
        """Authenticate with Google Drive API"""
        info = self._env_info()
        logger.info(f"ENV INFO: {info}")
        
        # Load existing token
        self._load_existing_token()
        
        # Refresh if expired
        if (self.credentials and self.credentials.expired 
            and self.credentials.refresh_token):
            try: 
                self.credentials.refresh(Request())
                logger.info("Refreshed expired credentials")
            except Exception as e:
                logger.warning(f"Failed to refresh credentials: {e}")
                self.credentials = None
        
        # Get new credentials if needed
        if not self.credentials or not self.credentials.valid:
            if info["local"]:
                secret_path = self.credentials_file
                logger.info("Using local credentials file")
            elif info["secrets"]:
                secret_path = self._create_temp_credentials()
                logger.info("Using Streamlit secrets for credentials")
            else:
                raise Exception(
                    "Google Drive authentication failed: Credentials file 'credentials.json' not found. "
                    "Please either:\n"
                    "1. Download credentials.json from Google Cloud Console, OR\n"
                    "2. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to Streamlit secrets."
                )
            
            if not secret_path:
                raise Exception("Failed to create credentials file")
            
            # Create OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                secret_path, self.SCOPES
            )
            
            # For Streamlit Cloud, use a different auth method
            is_cloud = not info["local"] or os.getenv("STREAMLIT_CLOUD", False)
            
            if is_cloud:
                # Use manual OAuth flow for cloud deployment
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                st.error("🔐 **Google Drive Authentication Required**")
                st.info("Please complete OAuth authentication:")
                st.markdown(f"1. [Click here to authorize]({auth_url})")
                st.markdown("2. Copy the authorization code from the redirect URL")
                
                auth_code = st.text_input("Paste the authorization code here:", type="password")
                
                if auth_code:
                    try:
                        flow.fetch_token(code=auth_code)
                        self.credentials = flow.credentials
                        
                        # Save token for future use
                        with open(self.token_file, "w") as f:
                            f.write(self.credentials.to_json())
                        
                        st.success("✅ Authentication successful!")
                        
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")
                        return None
                else:
                    return None
            else:
                # Use local server for development
                self.credentials = flow.run_local_server(
                    port=0,
                    open_browser=True,
                    authorization_prompt_message="Please visit: {url}",
                    success_message="Auth complete."
                )
                
                # Save token
                with open(self.token_file, "w") as f:
                    f.write(self.credentials.to_json())
        
        # Cleanup temporary credentials file
        if self._temp_creds_path:
            try: 
                os.unlink(self._temp_creds_path)
                logger.info("Cleaned up temporary credentials file")
            except: 
                pass
        
        # Build and test service
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            # Test the service
            self.service.files().list(pageSize=1).execute()
            logger.info("Google Drive service successfully initialized")
            return self.service
        except HttpError as e:
            logger.error(f"Drive service test failed: {e}")
            raise Exception(f"Drive service test failed: {e}")
