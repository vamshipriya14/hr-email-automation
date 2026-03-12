"""
OAuth2 Email Client for Microsoft 365
Uses Azure AD app registration with client credentials flow
"""
import os
import imaplib
import base64
import requests
from typing import Optional


class OAuth2EmailClient:
    """Email client with OAuth2 authentication for Microsoft 365"""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, email_user: str):
        """
        Initialize OAuth2 email client

        Args:
            tenant_id: Azure AD Tenant ID
            client_id: Azure AD Application (client) ID
            client_secret: Azure AD Client Secret
            email_user: Email address to access
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.email_user = email_user
        self.access_token = None

    def get_access_token(self) -> str:
        """
        Get OAuth2 access token using client credentials flow

        Returns:
            Access token string
        """
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://outlook.office365.com/.default',
            'grant_type': 'client_credentials'
        }

        response = requests.post(token_url, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception(f"Failed to get access token: {response.text}")

        token_data = response.json()
        self.access_token = token_data['access_token']
        return self.access_token

    def connect_imap(self, imap_server: str = 'outlook.office365.com') -> imaplib.IMAP4_SSL:
        """
        Connect to IMAP server using OAuth2

        Args:
            imap_server: IMAP server address

        Returns:
            IMAP4_SSL connection
        """
        if not self.access_token:
            self.get_access_token()

        # Build XOAUTH2 string
        auth_string = f"user={self.email_user}\x01auth=Bearer {self.access_token}\x01\x01"
        auth_string_b64 = base64.b64encode(auth_string.encode()).decode()

        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(imap_server)

        # Authenticate with OAuth2
        mail.authenticate('XOAUTH2', lambda x: auth_string_b64)

        return mail


def get_oauth_client_from_env() -> Optional[OAuth2EmailClient]:
    """
    Create OAuth2 client from environment variables

    Requires:
        - AZURE_TENANT_ID
        - AZURE_CLIENT_ID
        - AZURE_CLIENT_SECRET
        - EMAIL_USER

    Returns:
        OAuth2EmailClient if all vars present, None otherwise
    """
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    email_user = os.getenv('EMAIL_USER')

    if all([tenant_id, client_id, client_secret, email_user]):
        return OAuth2EmailClient(tenant_id, client_id, client_secret, email_user)

    return None
