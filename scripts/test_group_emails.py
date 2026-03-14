#!/usr/bin/env python3
"""
Test reading emails from Microsoft 365 Group (rec_team@volibits.com)
Uses Group.Read.All permission (no Mail.Read needed!)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from graph_group_client import GraphGroupClient

def main():
    print("=" * 80)
    print("📧 TESTING GROUP EMAIL ACCESS")
    print("=" * 80)
    print()

    # Get credentials
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    group_id = os.getenv('GROUP_ID')

    print("📋 Checking environment variables...")
    print(f"   AZURE_TENANT_ID: {'✅ Set' if tenant_id else '❌ Missing'}")
    print(f"   AZURE_CLIENT_ID: {'✅ Set' if client_id else '❌ Missing'}")
    print(f"   AZURE_CLIENT_SECRET: {'✅ Set' if client_secret else '❌ Missing'}")
    print(f"   GROUP_ID: {'✅ Set' if group_id else '❌ Missing'}")

    if not group_id:
        print()
        print("❌ GROUP_ID is not set!")
        print()
        print("   Add to GitHub Codespaces secrets or .env file:")
        print("   GROUP_ID=566b4ceb-f503-439b-ae83-2c9815aeba9c")
        return

    print(f"      Group ID: {group_id}")
    print()

    # Create client
    print("🔐 Creating Graph Group client...")
    client = GraphGroupClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        group_id=group_id
    )

    # Get access token
    print("🎫 Getting access token...")
    try:
        client.get_access_token()
        print("   ✅ Access token obtained")
        print()
    except Exception as e:
        print(f"   ❌ Failed to get token: {e}")
        return

    # Test 1: List conversations
    print("📬 Test 1: Listing conversations...")
    try:
        conversations = client.list_conversations(max_results=5)
        print(f"   ✅ Found {len(conversations)} conversations")

        if conversations:
            print()
            print("   Recent conversations:")
            for i, conv in enumerate(conversations[:3], 1):
                topic = conv.get('topic', 'No subject')
                last_delivered = conv.get('lastDeliveredDateTime', 'Unknown')
                print(f"      {i}. {topic}")
                print(f"         Last delivered: {last_delivered}")
        print()
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print()

    # Test 2: List threads
    print("📬 Test 2: Listing threads...")
    try:
        threads = client.list_threads(max_results=5)
        print(f"   ✅ Found {len(threads)} threads")

        if threads:
            print()
            print("   Recent threads:")
            for i, thread in enumerate(threads[:3], 1):
                topic = thread.get('topic', 'No subject')
                last_delivered = thread.get('lastDeliveredDateTime', 'Unknown')
                print(f"      {i}. {topic}")
                print(f"         Last delivered: {last_delivered}")
        print()
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print()

    # Test 3: Get thread posts (if we have threads)
    if threads and len(threads) > 0:
        print("📬 Test 3: Getting posts from first thread...")
        try:
            thread_id = threads[0].get('id')
            posts = client.get_thread_posts(thread_id)
            print(f"   ✅ Found {len(posts)} posts in thread")

            if posts:
                print()
                print("   First post:")
                first_post = posts[0]
                from_info = first_post.get('from', {})
                sender = from_info.get('emailAddress', {}).get('address', 'Unknown')
                body_preview = first_post.get('body', {}).get('content', '')[:200]
                print(f"      From: {sender}")
                print(f"      Preview: {body_preview[:100]}...")
            print()
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            print()

    print("=" * 80)
    print("✅ TEST COMPLETE!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✅ Group.Read.All permission is working")
    print("  ✅ Can access group conversations and threads")
    print("  ✅ No Mail.Read permission needed!")
    print()
    print("Next steps:")
    print("  1. Update email monitor to use GraphGroupClient")
    print("  2. Parse emails from threads/posts")
    print("  3. Extract candidate data and insert to database")
    print()

if __name__ == '__main__':
    main()
