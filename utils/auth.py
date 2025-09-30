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
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials: Optional[Credentials] = None
        self.service = None
        self._temp_creds_path: Optional[str] = None
    
    def _create_temp_oauth_credentials(self) -> Optional[str]:
        """Create temporary Desktop OAuth credentials"""
        try:
            creds = {
                "installed": {  # Desktop app - this is the key!
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
                }
            }
            
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            json.dump(creds, tf, indent=2)
            tf.flush()
            tf.close()
            self._temp_creds_path = tf.name
            return tf.name
        except Exception as e:
            st.error(f"❌ Failed to create credentials: {e}")
            return None
    
    def authenticate(self) -> Optional[object]:
        """Simple Desktop OAuth authentication"""
        # Load refresh token if available
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
                if self.credentials.expired:
                    self.credentials.refresh(Request())
                return self._build_service()
            except Exception as e:
                st.warning(f"⚠️ Refresh token expired: {e}")
        
        # Create new OAuth flow
        secret_path = self._create_temp_oauth_credentials()
        if not secret_path:
            return None
            
        try:
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, self.SCOPES)
            
            st.info("🔐 **Google Drive Authentication Required**")
            
            # **CRITICAL FIX: Manually construct URL with OOB redirect**
            auth_url = (
                f"https://accounts.google.com/o/oauth2/auth?"
                f"response_type=code&"
                f"client_id={st.secrets['GOOGLE_CLIENT_ID']}&"
                f"redirect_uri=urn:ietf:wg:oauth:2.0:oob&"
                f"scope=https://www.googleapis.com/auth/drive.readonly%20https://www.googleapis.com/auth/drive.file%20https://www.googleapis.com/auth/drive.metadata.readonly&"
                f"access_type=offline&"
                f"prompt=consent"
            )
            
            st.markdown(f"**Step 1:** [🔗 Click to authorize with Google]({auth_url})")
            st.markdown("**Step 2:** Complete authorization and copy the code")
            
            auth_code = st.text_input(
                "**Step 3:** Paste authorization code here:",
                type="password",
                placeholder="4/0AX4XfWi..."
            )
            
            if auth_code:
                try:
                    # Set redirect URI explicitly before fetching token
                    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
                    flow.fetch_token(code=auth_code.strip())
                    self.credentials = flow.credentials
                    
                    st.success("✅ **Authentication Successful!**")
                    
                    if self.credentials.refresh_token:
                        st.info("🔑 **Add this to your secrets for future use:**")
                        st.code(f"GOOGLE_REFRESH_TOKEN = \"{self.credentials.refresh_token}\"")
                    
                    return self._build_service()
                except Exception as e:
                    st.error(f"❌ Authentication failed: {str(e)}")
                    return None
            else:
                st.warning("⏳ Waiting for authorization code...")
                return None
                
        finally:
            if self._temp_creds_path:
                try:
                    os.unlink(self._temp_creds_path)
                except:
                    pass
    
    def _build_service(self):
        """Build Google Drive service"""
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            # Test the connection
            self.service.files().list(pageSize=1).execute()
            return self.service
        except Exception as e:
            st.error(f"❌ Service creation failed: {e}")
            return None
