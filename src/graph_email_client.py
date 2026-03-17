#!/usr/bin/env python3
"""
Microsoft Graph API Email Client
Alternative to IMAP - uses Microsoft Graph REST API
No Exchange admin configuration required!
"""

import requests
import base64
import email
from email import policy
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


class GraphEmailClient:
    """Email client using Microsoft Graph API (no IMAP needed)"""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, email_user: str):
        """
        Initialize Graph API client

        Args:
            tenant_id: Azure AD Tenant ID
            client_id: Azure AD Client ID
            client_secret: Azure AD Client Secret
            email_user: Email address to monitor
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.email_user = email_user
        self.access_token = None
        self.graph_api_endpoint = "https://graph.microsoft.com/v1.0"

    def get_access_token(self) -> str:
        """Get OAuth2 access token for Microsoft Graph API"""
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }

        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            logger.info("✅ Graph API access token obtained")
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to get Graph API access token: {e}")
            raise

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authorization"""
        if not self.access_token:
            self.get_access_token()

        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def list_unread_messages(self, folder: str = 'inbox', max_results: int = 50) -> List[Dict[str, Any]]:
        """
        List unread messages from mailbox

        Args:
            folder: Folder name (default: 'inbox')
            max_results: Maximum number of messages to return

        Returns:
            List of message metadata dictionaries
        """
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/mailFolders/{folder}/messages"

        params = {
            '$filter': 'isRead eq false',
            '$top': max_results,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,receivedDateTime,hasAttachments,internetMessageId'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            messages = data.get('value', [])
            logger.info(f"Found {len(messages)} unread messages")
            return messages
        except Exception as e:
            logger.error(f"Failed to list messages: {e}")
            raise

    def list_all_messages(self, folder: str = 'inbox', max_results: int = 50) -> List[Dict[str, Any]]:
        """
        List all messages from mailbox (read and unread)

        Args:
            folder: Folder name (default: 'inbox')
            max_results: Maximum number of messages to return

        Returns:
            List of message metadata dictionaries
        """
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/mailFolders/{folder}/messages"

        params = {
            '$top': max_results,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,receivedDateTime,hasAttachments,internetMessageId'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            messages = data.get('value', [])
            logger.info(f"Found {len(messages)} messages (read and unread)")
            return messages
        except Exception as e:
            logger.error(f"Failed to list messages: {e}")
            raise

    def get_message_content(self, message_id: str) -> Dict[str, Any]:
        """
        Get full message content including body and attachments

        Args:
            message_id: Graph API message ID

        Returns:
            Dictionary with message details
        """
        # URL-encode the message ID to handle special characters
        encoded_message_id = quote(message_id, safe='')
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/messages/{encoded_message_id}"

        params = {
            '$select': 'id,subject,from,to,receivedDateTime,body,hasAttachments,internetMessageId'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Don't log full error - it will be handled by MIME fallback
            raise

    def get_message_mime(self, message_id: str) -> str:
        """
        Get message in MIME format (RFC 2822)

        Args:
            message_id: Graph API message ID

        Returns:
            MIME format email string
        """
        # URL-encode the message ID to handle special characters
        encoded_message_id = quote(message_id, safe='')
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/messages/{encoded_message_id}/$value"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get MIME message: {e}")
            raise

    def get_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Get list of attachments for a message

        Args:
            message_id: Graph API message ID

        Returns:
            List of attachment metadata
        """
        # URL-encode the message ID to handle special characters
        encoded_message_id = quote(message_id, safe='')
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/messages/{encoded_message_id}/attachments"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Failed to get attachments: {e}")
            raise

    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark message as read

        Args:
            message_id: Graph API message ID

        Returns:
            True if successful
        """
        # URL-encode the message ID to handle special characters
        encoded_message_id = quote(message_id, safe='')
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/messages/{encoded_message_id}"

        data = {
            'isRead': True
        }

        try:
            response = requests.patch(url, headers=self.get_headers(), json=data, timeout=30)
            response.raise_for_status()
            logger.info(f"Marked message {message_id} as read")
            return True
        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False

    def search_messages(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search messages using query

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of matching messages
        """
        url = f"{self.graph_api_endpoint}/users/{self.email_user}/messages"

        params = {
            '$search': f'"{query}"',
            '$top': max_results,
            '$orderby': 'receivedDateTime desc'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
            raise

    def test_connection(self) -> bool:
        """Test if connection works"""
        try:
            self.get_access_token()
            messages = self.list_unread_messages(max_results=1)
            logger.info(f"✅ Graph API connection successful for {self.email_user}")
            return True
        except Exception as e:
            logger.error(f"❌ Graph API connection failed: {e}")
            return False
