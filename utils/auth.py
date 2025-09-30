import streamlit as st
import os
import json
import tempfile
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveAuth:
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]

    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials: Optional[Credentials] = None
        self.service = None

    def authenticate(self) -> Optional[object]:
        """Authenticate with Google Drive - works on Streamlit Cloud and locally"""
        try:
            # Try loading from secrets (Streamlit Cloud)
            if hasattr(st, "secrets") and "GOOGLE_REFRESH_TOKEN" in st.secrets:
                return self._authenticate_with_refresh_token()
            
            # Try local credentials file
            if os.path.exists(self.credentials_file):
                return self._authenticate_local()
            
            # Interactive OAuth flow for first-time setup
            return self._authenticate_interactive()
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            st.error(f"❌ Authentication error: {str(e)}")
            return None

    def _authenticate_with_refresh_token(self) -> Optional[object]:
        """Use stored refresh token from Streamlit secrets"""
        try:
            logger.info("🔑 Using refresh token from secrets")
            token_info = {
                "refresh_token": st.secrets["GOOGLE_REFRESH_TOKEN"],
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "scopes": self.SCOPES
            }
            
            self.credentials = Credentials.from_authorized_user_info(token_info)
            
            # Refresh if expired
            if not self.credentials.valid:
                if self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                    logger.info("✅ Token refreshed successfully")
            
            return self._build_service()
            
        except Exception as e:
            logger.error(f"Refresh token authentication failed: {e}")
            st.warning(f"⚠️ Refresh token expired or invalid. Please re-authenticate.")
            return None

    def _authenticate_local(self) -> Optional[object]:
        """Authenticate using local credentials.json file"""
        try:
            logger.info("🔐 Using local credentials file")
            
            # Check for existing token
            if os.path.exists(self.token_file):
                self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
            
            # Refresh or get new credentials
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES
                    )
                    self.credentials = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(self.token_file, 'w') as token:
                    token.write(self.credentials.to_json())
            
            logger.info("✅ Local authentication successful")
            return self._build_service()
            
        except Exception as e:
            logger.error(f"Local authentication failed: {e}")
            return None

    def _authenticate_interactive(self) -> Optional[object]:
        """Interactive OAuth flow for Streamlit Cloud (manual code entry)"""
        try:
            if not (hasattr(st, "secrets") and "GOOGLE_CLIENT_ID" in st.secrets):
                st.error("❌ Google OAuth credentials not found in secrets")
                st.info("""
                **Setup Instructions:**
                1. Go to [Google Cloud Console](https://console.cloud.google.com)
                2. Create OAuth 2.0 credentials (Desktop app)
                3. Add to Streamlit secrets:
                ```
                GOOGLE_CLIENT_ID = "your_client_id"
                GOOGLE_CLIENT_SECRET = "your_client_secret"
                ```
                """)
                return None
            
            # Create temporary credentials file
            creds_data = {
                "installed": {
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
                }
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                json.dump(creds_data, tf)
                temp_creds_path = tf.name
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(temp_creds_path, self.SCOPES)
                flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
                
                # Generate authorization URL
                auth_url, _ = flow.authorization_url(
                    access_type='offline',
                    include_granted_scopes='true',
                    prompt='consent'
                )
                
                st.info("🔐 **Google Drive Authorization Required**")
                st.markdown(f"**Step 1:** [Click here to authorize]({auth_url})")
                st.markdown("**Step 2:** Copy the authorization code")
                
                auth_code = st.text_input(
                    "**Step 3:** Paste the authorization code here:",
                    type="password",
                    key="google_auth_code"
                )
                
                if auth_code:
                    with st.spinner("Authenticating..."):
                        flow.fetch_token(code=auth_code.strip())
                        self.credentials = flow.credentials
                        
                        st.success("✅ **Authentication Successful!**")
                        
                        if self.credentials.refresh_token:
                            st.info("🔑 **Save this refresh token to your Streamlit secrets:**")
                            st.code(f'GOOGLE_REFRESH_TOKEN = "{self.credentials.refresh_token}"')
                            st.warning("⚠️ Copy the refresh token above and add it to your secrets to avoid re-authenticating!")
                        
                        return self._build_service()
                else:
                    st.warning("⏳ Waiting for authorization code...")
                    return None
                    
            finally:
                try:
                    os.unlink(temp_creds_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Interactive authentication failed: {e}")
            st.error(f"❌ Authentication failed: {str(e)}")
            return None

    def _build_service(self):
        """Build and test Google Drive service"""
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            # Test the connection
            self.service.files().list(pageSize=1).execute()
            logger.info("✅ Google Drive service created successfully")
            return self.service
        except Exception as e:
            logger.error(f"Service creation failed: {e}")
            st.error(f"❌ Failed to connect to Google Drive: {str(e)}")
            return None
