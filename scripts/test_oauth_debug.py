#!/usr/bin/env python3
"""
Debug OAuth2 email connection with detailed logging
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from oauth_email_client import OAuth2EmailClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.oauth_email_client import OAuth2EmailClient

def main():
    print("=" * 70)
    print("🔍 OAUTH2 CONNECTION DEBUG")
    print("=" * 70)
    print()

    # Check environment variables
    print("📋 Checking environment variables...")
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    email_user = os.getenv('EMAIL_USER')

    print(f"   AZURE_TENANT_ID: {'✅ Set' if tenant_id else '❌ Missing'}")
    if tenant_id:
        print(f"      Value: {tenant_id[:10]}...")

    print(f"   AZURE_CLIENT_ID: {'✅ Set' if client_id else '❌ Missing'}")
    if client_id:
        print(f"      Value: {client_id[:10]}...")

    print(f"   AZURE_CLIENT_SECRET: {'✅ Set' if client_secret else '❌ Missing'}")
    if client_secret:
        print(f"      Value: {client_secret[:10]}...")

    print(f"   EMAIL_USER: {'✅ Set' if email_user else '❌ Missing'}")
    if email_user:
        print(f"      Value: {email_user}")

    print()

    if not all([tenant_id, client_id, client_secret, email_user]):
        print("❌ Missing required environment variables!")
        print("   Make sure all secrets are added in GitHub Codespaces settings")
        return

    print("🔐 Creating OAuth2 client...")
    try:
        oauth_client = OAuth2EmailClient(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            email_user=email_user
        )
        print("   ✅ OAuth2 client created")
    except Exception as e:
        print(f"   ❌ Failed to create OAuth2 client: {e}")
        return

    print()
    print("🎫 Getting access token...")
    try:
        token = oauth_client.get_access_token()
        print(f"   ✅ Access token obtained")
        print(f"      Token (first 20 chars): {token[:20]}...")
    except Exception as e:
        print(f"   ❌ Failed to get access token: {e}")
        print()
        print("   Common causes:")
        print("   1. Incorrect Tenant ID, Client ID, or Client Secret")
        print("   2. App permissions not granted in Azure AD")
        print("   3. Network/firewall blocking Azure AD")
        return

    print()
    print("📧 Connecting to IMAP server (outlook.office365.com)...")
    try:
        mail = oauth_client.connect_imap()
        print(f"   ✅ Connected successfully!")
        print(f"   📬 Mailbox: {email_user}")

        # Try to select inbox
        mail.select('INBOX')
        print("   ✅ INBOX selected")

        # Count messages
        status, messages = mail.search(None, 'ALL')
        if status == 'OK':
            msg_count = len(messages[0].split())
            print(f"   📊 Total messages in INBOX: {msg_count}")

        mail.logout()
        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED! OAuth2 is working correctly!")
        print("=" * 70)

    except Exception as e:
        print(f"   ❌ IMAP connection failed: {e}")
        print()
        print("   Common causes:")
        print("   1. IMAP not enabled on mailbox (run: Set-CASMailbox -Identity rec_team@volibits.com -ImapEnabled $true)")
        print("   2. Application Access Policy not configured")
        print("   3. Modern Authentication not enabled in Exchange Online")
        print("   4. Permissions not yet propagated (wait 5-15 minutes)")
        print()
        print("   See documentation: docs/AZURE_AD_OAUTH_SETUP.md")
        return

if __name__ == '__main__':
    main()
