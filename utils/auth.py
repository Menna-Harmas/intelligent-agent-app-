import streamlit as st
import os
import json
import tempfile
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
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
        logger.info("🔧 GoogleDriveAuth initialized - Desktop OAuth optimized")
    
    def _env_info(self) -> Dict[str, bool]:
        """Check available credential sources"""
        has_local = os.path.exists(self.credentials_file)
        has_oauth_secrets = False
        has_service_account = False
        can_access = False
        
        try:
            if hasattr(st, "secrets"):
                _ = dict(st.secrets)
                can_access = True
                has_oauth_secrets = ("GOOGLE_CLIENT_ID" in st.secrets and 
                                   "GOOGLE_CLIENT_SECRET" in st.secrets)
                has_service_account = "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets
        except Exception as e:
            logger.warning(f"Cannot access Streamlit secrets: {e}")
        
        return {
            "local": has_local, 
            "oauth_secrets": has_oauth_secrets, 
            "service_account": has_service_account,
            "can_access": can_access
        }
    
    def _authenticate_with_service_account(self) -> Optional[object]:
        """Authenticate using service account credentials"""
        try:
            if hasattr(st, "secrets") and "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets:
                # Parse service account JSON
                service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
                
                # Create service account credentials
                self.credentials = ServiceAccountCredentials.from_service_account_info(
                    service_account_info, scopes=self.SCOPES
                )
                
                logger.info("✅ Service account authentication successful")
                return self._build_service()
            else:
                logger.error("❌ Service account JSON not found in secrets")
                return None
                
        except Exception as e:
            logger.error(f"❌ Service account authentication failed: {e}")
            return None
    
    def _create_temp_oauth_credentials(self) -> Optional[str]:
        """Create temporary Desktop OAuth credentials file from Streamlit secrets"""
        info = self._env_info()
        if not info["oauth_secrets"]:
            logger.error("No OAuth secrets found")
            return None
        
        try:
            # Desktop application configuration - no redirect URI needed!
            creds = {
                "installed": {  # Desktop app type
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]  # Out-of-band for desktop
                }
            }
            
            # Create temporary file
            tf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix="tmp_oauth_"
            )
            json.dump(creds, tf, indent=2)
            tf.flush()
            tf.close()
            
            self._temp_creds_path = tf.name
            logger.info("✅ Created temporary Desktop OAuth credentials file")
            return tf.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create temp OAuth credentials: {e}")
            return None
    
    def _load_existing_oauth_token(self) -> bool:
        """Load existing OAuth token from secrets or local file"""
        # Priority 1: Try loading from Streamlit secrets (refresh token)
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
                logger.info("✅ Loaded refresh token from Streamlit secrets")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load refresh token from secrets: {e}")
        
        # Priority 2: Try loading from local token file
        if os.path.exists(self.token_file):
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.SCOPES
                )
                logger.info("✅ Loaded OAuth credentials from local token file")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load local token: {e}")
        
        return False
    
    def _authenticate_with_oauth(self) -> Optional[object]:
        """Authenticate using Desktop OAuth flow - Streamlit Cloud optimized"""
        info = self._env_info()
        
        # Step 1: Try to load existing credentials
        self._load_existing_oauth_token()
        
        # Step 2: Refresh if expired
        if (self.credentials and self.credentials.expired 
            and self.credentials.refresh_token):
            try: 
                self.credentials.refresh(Request())
                logger.info("🔄 Successfully refreshed expired OAuth credentials")
            except Exception as e:
                logger.warning(f"⚠️ Failed to refresh credentials: {e}")
                self.credentials = None
        
        # Step 3: Get new credentials if needed
        if not self.credentials or not self.credentials.valid:
            # Determine credential source
            if info["local"]:
                secret_path = self.credentials_file
                logger.info("📁 Using local OAuth credentials.json file")
            elif info["oauth_secrets"]:
                secret_path = self._create_temp_oauth_credentials()
                if not secret_path:
                    raise Exception("❌ Failed to create temporary OAuth credentials file from secrets")
                logger.info("☁️ Using Desktop OAuth from Streamlit secrets")
            else:
                raise Exception("❌ No OAuth credentials available")
            
            # Step 4: Create Desktop OAuth flow
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    secret_path, self.SCOPES
                )
                
                # Check if we're in cloud environment (no local credentials.json)
                is_cloud_deployment = not info["local"]
                
                if is_cloud_deployment:
                    # **STREAMLIT CLOUD - Manual Desktop OAuth Flow**
                    st.info("🔐 **Google Drive Authentication Required**")
                    st.markdown("Complete the **Desktop OAuth** process to access your **personal Google Drive**:")
                    
                    # Generate authorization URL for desktop app
                    auth_url, state = flow.authorization_url(
                        prompt='consent',
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    
                    st.markdown(f"**Step 1:** [🔗 Click to authorize with Google]({auth_url})")
                    st.markdown("**Step 2:** Complete authorization in Google")
                    st.markdown("**Step 3:** Copy the authorization code from Google")
                    st.info("💡 **After clicking 'Allow'**, Google will show you a **code**. Copy that code!")
                    
                    # Input for authorization code
                    auth_code = st.text_input(
                        "**Step 4:** Paste the authorization code here:",
                        type="password",
                        help="The code Google shows you after authorization",
                        placeholder="4/0AX4XfWi..."
                    )
                    
                    if auth_code:
                        with st.spinner("🔄 Processing authorization..."):
                            try:
                                # Exchange code for tokens using desktop flow
                                flow.fetch_token(code=auth_code.strip())
                                self.credentials = flow.credentials
                                
                                st.success("✅ **Desktop OAuth Authentication Successful!**")
                                
                                # Show refresh token for permanent setup
                                if self.credentials.refresh_token:
                                    st.info("🔑 **Save this refresh token to avoid future re-authentication:**")
                                    st.code(f"GOOGLE_REFRESH_TOKEN = \"{self.credentials.refresh_token}\"")
                                    st.markdown("*Add this to your Streamlit Cloud app secrets*")
                                
                                st.balloons()
                                return self._build_service()
                                
                            except Exception as e:
                                st.error(f"❌ **Desktop OAuth failed:** {str(e)}")
                                st.info("💡 Please try again with a fresh authorization code")
                                logger.error(f"Desktop OAuth exchange failed: {e}")
                                return None
                    else:
                        st.warning("⏳ Waiting for authorization code...")
                        return None
                        
                else:
                    # **LOCAL DEVELOPMENT - Automatic Desktop OAuth**
                    try:
                        st.info("🔄 Starting local Desktop OAuth flow...")
                        
                        self.credentials = flow.run_local_server(
                            port=8080,
                            open_browser=True,
                            authorization_prompt_message="Please visit: {url}",
                            success_message="✅ Desktop authentication complete! You can close this window."
                        )
                        
                        # Save token locally for future use
                        with open(self.token_file, "w") as f:
                            f.write(self.credentials.to_json())
                        
                        st.success("✅ Local Desktop OAuth successful!")
                        logger.info("💾 Saved Desktop OAuth credentials to local token file")
                        
                        return self._build_service()
                        
                    except Exception as e:
                        st.error(f"❌ Local Desktop OAuth failed: {str(e)}")
                        logger.error(f"Local Desktop OAuth failed: {e}")
                        raise Exception(f"Local Desktop OAuth failed: {str(e)}")
                    
            except Exception as e:
                logger.error(f"❌ Desktop OAuth flow creation failed: {e}")
                raise Exception(f"Desktop OAuth flow failed: {str(e)}")
        else:
            # Credentials are valid, build service
            logger.info("✅ Using existing valid Desktop OAuth credentials")
            return self._build_service()
    
    def _build_service(self) -> Optional[object]:
        """Build and test Google Drive service"""
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Test the service with a simple API call
            test_result = self.service.files().list(pageSize=1).execute()
            logger.info("✅ Google Drive service successfully initialized and tested")
            
            return self.service
            
        except HttpError as e:
            logger.error(f"❌ Google Drive API test failed: {e}")
            raise Exception(f"Google Drive API access failed: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            raise Exception(f"Service initialization failed: {str(e)}")
    
    def authenticate(self) -> Optional[object]:
        """Authenticate with Google Drive API - Desktop OAuth optimized"""
        info = self._env_info()
        logger.info(f"🔍 Environment check: Local={info['local']}, OAuth={info['oauth_secrets']}, ServiceAccount={info['service_account']}")
        
        try:
            # Priority 1: Desktop OAuth authentication (for personal Drive access)
            if info["local"] or info["oauth_secrets"]:
                logger.info("🔑 Attempting Desktop OAuth authentication (Personal Drive Access)")
                st.info("🖥️ **Using Desktop OAuth** for accessing your **personal Google Drive**")
                return self._authenticate_with_oauth()
            
            # Priority 2: Fallback to service account (limited access)
            elif info["service_account"]:
                logger.info("🔧 Using Service Account authentication (Limited Access)")
                st.warning("📋 **Using Service Account**: Can only access files shared with the service account")
                return self._authenticate_with_service_account()
            
            else:
                # No credentials available
                error_msg = (
                    "❌ **No Google credentials available!**\n\n"
                    "**For Personal Drive Access (Recommended):**\n"
                    "1. Create **Desktop OAuth Client** in Google Cloud Console\n"
                    "2. Add to your Streamlit secrets:\n"
                    "   - `GOOGLE_CLIENT_ID`\n"
                    "   - `GOOGLE_CLIENT_SECRET`\n\n"
                    "**For Local Development:**\n"
                    "1. Download Desktop OAuth `credentials.json`\n"
                    "2. Place it in your project root directory\n\n"
                    "💡 **Desktop OAuth** works best with Streamlit Cloud!"
                )
                st.error(error_msg)
                raise Exception(error_msg)
        
        finally:
            # Cleanup temporary files
            if self._temp_creds_path:
                try: 
                    os.unlink(self._temp_creds_path)
                    logger.info("🧹 Cleaned up temporary credentials file")
                except: 
                    pass
