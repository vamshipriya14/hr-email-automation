#!/usr/bin/env python3
"""Check what fields are available in Graph API post objects"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from graph_group_client import GraphGroupClient
import json

# Load environment
from dotenv import load_dotenv
load_dotenv()

def main():
    client = GraphGroupClient(
        tenant_id=os.getenv('AZURE_TENANT_ID'),
        client_id=os.getenv('AZURE_CLIENT_ID'),
        client_secret=os.getenv('AZURE_CLIENT_SECRET'),
        group_id=os.getenv('GROUP_ID')
    )

    print("Fetching threads...")
    threads = client.list_threads(max_results=1)

    if not threads:
        print("No threads found")
        return

    thread_id = threads[0]['id']
    topic = threads[0].get('topic', 'No subject')

    print(f"Thread: {topic}")
    print(f"Thread ID: {thread_id}")
    print()

    print("Fetching posts...")
    posts = client.get_thread_posts(thread_id)

    if not posts:
        print("No posts found")
        return

    post = posts[0]

    print("=" * 80)
    print("Available fields in post object:")
    print("=" * 80)
    for key in sorted(post.keys()):
        value = post[key]
        if isinstance(value, (str, int, bool)) and len(str(value)) < 100:
            print(f"  {key:30} : {value}")
        elif isinstance(value, dict):
            print(f"  {key:30} : {{...dict...}}")
        elif isinstance(value, list):
            print(f"  {key:30} : [...list of {len(value)} items...]")
        else:
            print(f"  {key:30} : {type(value).__name__}")

    print()
    print("=" * 80)
    print("Checking for recipient fields:")
    print("=" * 80)

    recipient_fields = ['toRecipients', 'ccRecipients', 'bccRecipients', 'recipients',
                       'conversationThreadId', 'sender', 'from', 'to', 'cc']

    for field in recipient_fields:
        if field in post:
            print(f"  {field}: {post[field]}")
        else:
            print(f"  {field}: NOT FOUND")

    print()
    print("=" * 80)
    print("Full post JSON (first 2000 chars):")
    print("=" * 80)
    print(json.dumps(post, indent=2)[:2000])

if __name__ == '__main__':
    main()
