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
        logger.info("ðŸ†• AUTH CODE LOADED (no run_console)")

    def _env_info(self) -> Dict[str, bool]:
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
        info = self._env_info()
        if not info["secrets"]:
            return None
        creds = {
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
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="tmp_creds_"
        )
        json.dump(creds, tf, indent=2)
        tf.flush(); tf.close()
        self._temp_creds_path = tf.name
        return tf.name

    def authenticate(self) -> Optional[object]:
        info = self._env_info()
        logger.info(f"ENV INFO: {info}")
        # Load token
        if os.path.exists(self.token_file):
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.SCOPES
                )
            except:
                self.credentials = None
        # Refresh if expired
        if (self.credentials and self.credentials.expired 
                and self.credentials.refresh_token):
            try: self.credentials.refresh(Request())
            except: self.credentials = None
        # New creds
        if not self.credentials or not self.credentials.valid:
            if info["local"]:
                secret_path = self.credentials_file
            elif info["secrets"]:
                secret_path = self._create_temp_credentials()
            else:
                raise Exception(
                    "No local credentials.json and no Streamlit secrets."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                secret_path, self.SCOPES
            )
            self.credentials = flow.run_local_server(
                port=0,
                open_browser=not info["secrets"],
                authorization_prompt_message="Please visit: {url}",
                success_message="Auth complete."
            )
            # Save
            with open(self.token_file, "w") as f:
                f.write(self.credentials.to_json())
            # Cleanup
            if self._temp_creds_path:
                try: os.unlink(self._temp_creds_path)
                except: pass
        # Build & test
        self.service = build('drive', 'v3', credentials=self.credentials)
        try:
            self.service.files().list(pageSize=1).execute()
            return self.service
        except HttpError as e:
            raise Exception(f"Drive service test failed: {e}")