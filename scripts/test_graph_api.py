#!/usr/bin/env python3
"""
Test Microsoft Graph API connection
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from graph_email_client import GraphEmailClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.graph_email_client import GraphEmailClient

def main():
    print("=" * 70)
    print("🔍 MICROSOFT GRAPH API TEST")
    print("=" * 70)
    print()

    # Check environment variables
    print("📋 Checking environment variables...")
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    email_user = os.getenv('EMAIL_USER')

    print(f"   AZURE_TENANT_ID: {'✅ Set' if tenant_id else '❌ Missing'}")
    print(f"   AZURE_CLIENT_ID: {'✅ Set' if client_id else '❌ Missing'}")
    print(f"   AZURE_CLIENT_SECRET: {'✅ Set' if client_secret else '❌ Missing'}")
    print(f"   EMAIL_USER: {'✅ Set' if email_user else '❌ Missing'}")
    if email_user:
        print(f"      Value: {email_user}")
    print()

    if not all([tenant_id, client_id, client_secret, email_user]):
        print("❌ Missing required environment variables!")
        return

    print("🔐 Creating Graph API client...")
    try:
        graph_client = GraphEmailClient(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            email_user=email_user
        )
        print("   ✅ Graph API client created")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()
    print("🎫 Getting access token...")
    try:
        token = graph_client.get_access_token()
        print(f"   ✅ Access token obtained")
        print(f"      Token (first 20 chars): {token[:20]}...")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print()
        print("   Check:")
        print("   1. Credentials are correct")
        print("   2. App has Mail.Read permission in Azure AD")
        print("   3. Permission is granted (green checkmark)")
        return

    print()
    print(f"📬 Fetching unread messages for {email_user}...")
    try:
        messages = graph_client.list_unread_messages(max_results=10)
        print(f"   ✅ Found {len(messages)} unread message(s)")
        print()

        if messages:
            print("   Recent unread messages:")
            for i, msg in enumerate(messages[:5], 1):
                subject = msg.get('subject', 'No subject')
                sender = msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
                received = msg.get('receivedDateTime', 'Unknown')
                print(f"   {i}. From: {sender}")
                print(f"      Subject: {subject[:50]}...")
                print(f"      Received: {received}")
                print()

        print("=" * 70)
        print("✅ ALL TESTS PASSED! Microsoft Graph API is working!")
        print("=" * 70)
        print()
        print("🎉 You can now use Graph API instead of IMAP!")
        print("   No Exchange admin configuration needed!")
        print()

    except Exception as e:
        print(f"   ❌ Failed to fetch messages: {e}")
        print()
        print("   Common causes:")
        print("   1. Mail.Read permission not added")
        print("   2. Permission not granted (needs green checkmark)")
        print("   3. App doesn't have consent for Mail.Read")
        print()
        print("   To fix:")
        print("   - Go to Azure AD → API permissions")
        print("   - Add: Microsoft Graph → Application → Mail.Read")
        print("   - Click 'Grant admin consent'")
        return

if __name__ == '__main__':
    main()
