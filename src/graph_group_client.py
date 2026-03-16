#!/usr/bin/env python3
"""
Microsoft Graph API Client for Microsoft 365 Groups
Handles group mailboxes (like rec_team@volibits.com)
"""

import requests
import base64
import email
from email import policy
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GraphGroupClient:
    """Email client for Microsoft 365 Groups using Graph API"""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, group_id: str):
        """
        Initialize Graph API client for groups

        Args:
            tenant_id: Azure AD Tenant ID
            client_id: Azure AD Client ID
            client_secret: Azure AD Client Secret
            group_id: Microsoft 365 Group ID
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.group_id = group_id
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

    def list_conversations(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        List conversations (email threads) in the group

        Args:
            max_results: Maximum number of conversations

        Returns:
            List of conversation metadata
        """
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/conversations"

        params = {
            '$top': max_results,
            '$orderby': 'lastDeliveredDateTime desc'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            conversations = data.get('value', [])
            logger.info(f"Found {len(conversations)} conversations")
            return conversations
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            raise

    def list_threads(self, max_results: int = 50, today_only: bool = False) -> List[Dict[str, Any]]:
        """
        List email threads in the group

        Args:
            max_results: Maximum number of threads to return
            today_only: If True, only return threads from today (client-side filter)

        Returns:
            List of thread metadata
        """
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/threads"

        # Fetch more threads if filtering for today (to ensure we get enough after filtering)
        fetch_count = max_results * 3 if today_only else max_results

        params = {
            '$top': fetch_count,
            '$orderby': 'lastDeliveredDateTime desc'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            threads = data.get('value', [])

            # Client-side filter for today's threads
            if today_only:
                from datetime import datetime, timezone
                today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

                filtered_threads = []
                for thread in threads:
                    last_delivered = thread.get('lastDeliveredDateTime', '')
                    if last_delivered:
                        # Parse the datetime string
                        thread_time = datetime.fromisoformat(last_delivered.replace('Z', '+00:00'))
                        if thread_time >= today_start:
                            filtered_threads.append(thread)
                            if len(filtered_threads) >= max_results:
                                break

                threads = filtered_threads
                logger.info(f"Found {len(threads)} threads (today only)")
            else:
                logger.info(f"Found {len(threads)} threads")

            return threads[:max_results]  # Limit to max_results
        except Exception as e:
            logger.error(f"Failed to list threads: {e}")
            raise

    def get_thread_posts(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get posts/messages in a thread

        Args:
            thread_id: Thread ID

        Returns:
            List of posts in the thread
        """
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/threads/{thread_id}/posts"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            posts = data.get('value', [])
            return posts
        except Exception as e:
            logger.error(f"Failed to get thread posts: {e}")
            raise

    def list_messages(self, folder: str = 'inbox', max_results: int = 50) -> List[Dict[str, Any]]:
        """
        List messages in group mailbox folder (if available)

        Args:
            folder: Folder name
            max_results: Maximum number of messages

        Returns:
            List of message metadata
        """
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/mailFolders/{folder}/messages"

        params = {
            '$top': max_results,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,receivedDateTime,hasAttachments,internetMessageId,isRead'
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            messages = data.get('value', [])
            logger.info(f"Found {len(messages)} messages in {folder}")
            return messages
        except Exception as e:
            logger.error(f"Failed to list messages: {e}")
            raise

    def list_unread_messages(self, folder: str = 'inbox', max_results: int = 50) -> List[Dict[str, Any]]:
        """List unread messages from group mailbox"""
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/mailFolders/{folder}/messages"

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
            logger.error(f"Failed to list unread messages: {e}")
            raise

    def get_message_content(self, message_id: str) -> Dict[str, Any]:
        """Get full message content"""
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/messages/{message_id}"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get message content: {e}")
            raise

    def get_message_mime(self, message_id: str) -> str:
        """Get message in MIME format"""
        url = f"{self.graph_api_endpoint}/groups/{self.group_id}/messages/{message_id}/$value"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get MIME message: {e}")
            raise

    def test_connection(self) -> bool:
        """Test if connection works"""
        try:
            self.get_access_token()
            messages = self.list_messages(max_results=1)
            logger.info(f"✅ Graph API connection successful for group {self.group_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Graph API connection failed: {e}")
            return False
