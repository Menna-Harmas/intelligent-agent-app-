import os
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveAuth:
    """
    Google Drive authentication handler using environment variables only.
    """
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]

    def __init__(self, token_file: str = "token.json"):
        self.token_file = token_file
        self.credentials = None
        self.service = None
        logger.info("GoogleDriveAuth initialized")

    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive and return the service object.
        """
        try:
            # Load existing token if present
            if os.path.exists(self.token_file):
                logger.info(f"Loading existing credentials from {self.token_file}")
                self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)

            # If no valid credentials, perform OAuth
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Refreshing expired credentials")
                    self.credentials.refresh(Request())

                if not self.credentials or not self.credentials.valid:
                    logger.info("Starting OAuth2 flow via environment variables")
                    # Verify required env vars
                    required = ['GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_PROJECT_ID','GOOGLE_REDIRECT_URIS']
                    missing = [v for v in required if v not in os.environ]
                    if missing:
                        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

                    config = {"web":{
                        "client_id": os.environ['GOOGLE_CLIENT_ID'],
                        "client_secret": os.environ['GOOGLE_CLIENT_SECRET'],
                        "project_id": os.environ['GOOGLE_PROJECT_ID'],
                        "auth_uri":"https://accounts.google.com/o/oauth2/auth",
                        "token_uri":"https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": os.environ['GOOGLE_REDIRECT_URIS'].split(',')
                    }}
                    flow = InstalledAppFlow.from_client_config(config, self.SCOPES)
                    self.credentials = flow.run_local_server(
                        port=8080,
                        authorization_prompt_message='Please visit this URL: {url}',
                        success_message='Authentication complete!',
                        open_browser=True
                    )
                    # Save token
                    with open(self.token_file,'w') as f:
                        f.write(self.credentials.to_json())
                    logger.info(f"Token saved to {self.token_file}")

            # Build service
            self.service = build('drive','v3',credentials=self.credentials)
            # Test
            self.service.files().list(pageSize=1).execute()
            logger.info("Google Drive service ready")
            return self.service

        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            raise

    def get_service(self)->Optional[object]:
        return self.service

    def is_authenticated(self)->bool:
        return bool(self.credentials and self.credentials.valid and self.service)

    def logout(self)->None:
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
            logger.info(f"Removed {self.token_file}")
        self.credentials=self.service=None
        logger.info("Logged out")
