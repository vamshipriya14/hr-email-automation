#!/usr/bin/env python3
"""Test if we can access Group messages with full headers"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from graph_group_client import GraphGroupClient
from dotenv import load_dotenv
import json

load_dotenv()

def main():
    client = GraphGroupClient(
        tenant_id=os.getenv('AZURE_TENANT_ID'),
        client_id=os.getenv('AZURE_CLIENT_ID'),
        client_secret=os.getenv('AZURE_CLIENT_SECRET'),
        group_id=os.getenv('GROUP_ID')
    )

    print("Testing messages endpoint...")
    print("=" * 80)

    try:
        # Try to get messages from inbox
        messages = client.list_messages(folder='inbox', max_results=1)

        if messages:
            print(f"✅ Messages endpoint works! Found {len(messages)} message(s)")
            print()

            msg = messages[0]
            print("Message fields:")
            for key in sorted(msg.keys()):
                value = msg[key]
                if isinstance(value, (str, int, bool)) and len(str(value)) < 100:
                    print(f"  {key:30} : {value}")
                elif isinstance(value, dict):
                    print(f"  {key:30} : {{...}}")
                elif isinstance(value, list):
                    print(f"  {key:30} : [...{len(value)} items...]")

            print()
            print("Checking for To/Cc recipients:")
            if 'toRecipients' in msg:
                print(f"  toRecipients: {msg['toRecipients']}")
            if 'ccRecipients' in msg:
                print(f"  ccRecipients: {msg['ccRecipients']}")

        else:
            print("⚠️  No messages found in inbox")

    except Exception as e:
        print(f"❌ Messages endpoint failed: {e}")
        print()
        print("This might mean:")
        print("  1. Group doesn't have a mailbox (uses conversations instead)")
        print("  2. We need Mail.Read permission (currently have Group.Read.All)")
        print("  3. Need to use a different approach")

if __name__ == '__main__':
    main()
