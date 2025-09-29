import os
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
    Google Drive authentication handler.
    Uses environment variables instead of a local credentials.json file.
    """
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]

    def __init__(self, token_file: str = "token.json"):
        """
        Initialize the Google Drive authentication handler.

        Args:
            token_file: Path to store/load the access token
        """
        self.token_file = token_file
        self.credentials = None
        self.service = None
        logger.info("GoogleDriveAuth initialized")

    def authenticate(self) -> Optional[object]:
        """
        Authenticate with Google Drive using environment variables and return the service object.

        Returns:
            Google Drive API service object or None if authentication fails
        """
        try:
            # Load existing credentials if they exist
            if os.path.exists(self.token_file):
                logger.info(f"Loading existing credentials from {self.token_file}")
                self.credentials = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)

            # If credentials are invalid or missing, perform OAuth flow
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Refreshing expired credentials")
                    try:
                        self.credentials.refresh(Request())
                        logger.info("Credentials refreshed successfully")
                    except Exception as refresh_error:
                        logger.warning(f"Failed to refresh credentials: {refresh_error}")
                        self.credentials = None

                if not self.credentials or not self.credentials.valid:
                    logger.info("Starting OAuth2 flow via environment variables")

                    # Ensure required environment variables exist
                    required = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_PROJECT_ID', 'GOOGLE_REDIRECT_URIS']
                    missing = [var for var in required if var not in os.environ]
                    if missing:
                        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

                    client_config = {
                        "web": {
                            "client_id": os.environ['GOOGLE_CLIENT_ID'],
                            "client_secret": os.environ['GOOGLE_CLIENT_SECRET'],
                            "project_id": os.environ['GOOGLE_PROJECT_ID'],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": os.environ['GOOGLE_REDIRECT_URIS'].split(',')
                        }
                    }

                    # Run the OAuth flow using the config dictionary
                    flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                    self.credentials = flow.run_local_server(
                        port=8080,
                        authorization_prompt_message='Please visit this URL to authorize the application: {url}',
                        success_message='Authorization complete! You may close this window.',
                        open_browser=True
                    )

                    # Save the credentials for next time
                    self._save_credentials()
                    logger.info("New credentials obtained and saved")

            # Build and test the service
            logger.info("Building Google Drive API service")
            self.service = build('drive', 'v3', credentials=self.credentials)
            if self._test_service():
                logger.info("Google Drive service created and tested successfully")
                return self.service
            else:
                logger.error("Service test failed")
                return None

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise Exception(f"Google Drive authentication failed: {e}")

    def _save_credentials(self) -> None:
        """Save credentials to file."""
        try:
            with open(self.token_file, 'w') as token_file:
                token_file.write(self.credentials.to_json())
            logger.info(f"Credentials saved to {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")

    def _test_service(self) -> bool:
        """Test the Google Drive service to make sure it's working."""
        try:
            self.service.files().list(pageSize=1, fields="files(id, name)").execute()
            logger.info("Service test passed - able to list files")
            return True
        except Exception as e:
            logger.error(f"Service test failed: {e}")
            return False

    def get_service(self) -> Optional[object]:
        """Get the authenticated Google Drive service."""
        return self.service

    def is_authenticated(self) -> bool:
        """Check if the user is authenticated."""
        return bool(self.credentials and self.credentials.valid and self.service)

    def logout(self) -> None:
        """Log out by removing stored credentials."""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"Removed token file: {self.token_file}")
        except Exception as e:
            logger.warning(f"Failed to remove token file: {e}")
        self.credentials = None
        self.service = None
        logger.info("Logged out successfully")
