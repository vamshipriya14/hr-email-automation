#!/usr/bin/env python3
"""
Find Microsoft 365 Group ID for rec_team@volibits.com
"""
import os
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from graph_email_client import GraphEmailClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.graph_email_client import GraphEmailClient

def main():
    print("=" * 70)
    print("🔍 FINDING MICROSOFT 365 GROUP ID")
    print("=" * 70)
    print()

    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    email_user = os.getenv('EMAIL_USER')

    print(f"📧 Searching for: {email_user}")
    print()

    # Get token
    graph_client = GraphEmailClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        email_user=email_user
    )

    token = graph_client.get_access_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Search for group by email
    print("🔎 Searching for group...")
    url = f"https://graph.microsoft.com/v1.0/groups?$filter=mail eq '{email_user}'"

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 403:
            print("❌ Permission denied!")
            print()
            print("   You need to add Group.Read.All permission:")
            print("   1. Azure AD → API permissions → Add permission")
            print("   2. Microsoft Graph → Application → Group.Read.All")
            print("   3. Grant admin consent")
            return

        response.raise_for_status()
        data = response.json()
        groups = data.get('value', [])

        if not groups:
            print("❌ Group not found!")
            print()
            print("   Possible reasons:")
            print("   1. Email address is incorrect")
            print("   2. It's not a Microsoft 365 Group")
            print("   3. App doesn't have permission to see groups")
            return

        print(f"✅ Found {len(groups)} group(s)!\n")

        for group in groups:
            group_id = group.get('id')
            display_name = group.get('displayName')
            mail = group.get('mail')
            group_types = group.get('groupTypes', [])

            print(f"   📋 Group Details:")
            print(f"      ID: {group_id}")
            print(f"      Name: {display_name}")
            print(f"      Email: {mail}")
            print(f"      Type: {group_types}")
            print()

            # Test accessing group conversations
            print("   🧪 Testing access to group conversations...")
            conv_url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/conversations"

            try:
                conv_response = requests.get(conv_url, headers=headers, timeout=30)

                if conv_response.status_code == 200:
                    conv_data = conv_response.json()
                    conversations = conv_data.get('value', [])
                    print(f"      ✅ Can access conversations! Found {len(conversations)} conversation(s)")

                    # Save group ID to a file for easy reference
                    config_file = Path(__file__).parent.parent / 'GROUP_ID.txt'
                    with open(config_file, 'w') as f:
                        f.write(f"GROUP_ID={group_id}\n")
                        f.write(f"GROUP_EMAIL={mail}\n")
                        f.write(f"GROUP_NAME={display_name}\n")

                    print()
                    print(f"   💾 Saved group ID to: {config_file}")

                elif conv_response.status_code == 403:
                    print("      ❌ Permission denied for conversations")
                    print("         Need: Group.Read.All or Mail.Read permission")
                else:
                    print(f"      ❌ Cannot access conversations (status: {conv_response.status_code})")

            except Exception as e:
                print(f"      ❌ Error accessing conversations: {e}")

        print()
        print("=" * 70)
        print("✅ NEXT STEPS:")
        print("=" * 70)
        print()
        print("1. Copy the Group ID above")
        print("2. Add to GitHub Codespaces secrets:")
        print(f"   GROUP_ID = {group_id}")
        print()
        print("3. Or update .env file:")
        print(f"   GROUP_ID={group_id}")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("   Check:")
        print("   1. Group.Read.All permission is added and granted")
        print("   2. Email address is correct")

if __name__ == '__main__':
    main()
