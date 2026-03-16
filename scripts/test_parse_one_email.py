#!/usr/bin/env python3
"""
Test parsing ONE email from the group to verify candidate extraction
Dry run - shows what would be inserted WITHOUT actually inserting
"""
import os
import sys
from pathlib import Path
import email
from email import policy
from io import BytesIO
import re

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from graph_group_client import GraphGroupClient
    from email_parser import EmailParser
    from database import PostgresClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.graph_group_client import GraphGroupClient
    from src.email_parser import EmailParser
    from src.database import PostgresClient


def display_raw_table(body: str):
    """Display the raw table extracted from email body"""
    print("\n" + "=" * 80)
    print("📋 RAW TABLE CONTENT")
    print("=" * 80 + "\n")

    # Check if this is HTML content with table
    if '<table' in body.lower():
        # Extract HTML table
        table_pattern = r'<table[^>]*>.*?</table>'
        tables = re.findall(table_pattern, body, re.DOTALL | re.IGNORECASE)

        if tables:
            print("HTML TABLE FORMAT")
            print("-" * 80)
            for i, table in enumerate(tables, 1):
                print(f"\nTable {i}:")
                # Show first 2000 chars
                table_preview = table[:2000]
                print(table_preview)
                if len(table) > 2000:
                    print(f"\n... (truncated, total length: {len(table)} chars)")
            print("-" * 80)
        else:
            print("❌ No HTML table found")

    # Also try to find text-based table
    lines = body.split('\n')
    table_start = -1
    table_end = -1

    # Find table boundaries (look for headers)
    for i, line in enumerate(lines):
        line_upper = line.strip().upper()
        if ('JR NO' in line_upper or 'JR NUMBER' in line_upper or
            'SI NO' in line_upper or 'GENERAL SKILL' in line_upper or
            'VENDOR NAME' in line_upper):
            table_start = i
            break

    if table_start >= 0:
        # Find table end (look for signature or footer)
        for i in range(table_start, min(table_start + 200, len(lines))):
            line_lower = lines[i].lower()
            if any(keyword in line_lower for keyword in
                   ['regards', 'thanks', 'sincerely', 'best', 'signature',
                    'volibits', 'confidential', 'disclaimer']):
                table_end = i
                break

        if table_end < 0:
            table_end = min(table_start + 100, len(lines))

        print("\nTEXT TABLE FORMAT")
        print("-" * 80)
        for line in lines[table_start:table_end]:
            if line.strip():
                print(line)
        print("-" * 80)
    else:
        if '<table' not in body.lower():
            print("\n❌ No text-based table found")

    print("\n" + "=" * 80 + "\n")

def main():
    print("=" * 80)
    print("🧪 TEST PARSING ONE EMAIL FROM GROUP")
    print("=" * 80)
    print()

    # Get credentials
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    group_id = os.getenv('GROUP_ID')

    if not all([tenant_id, client_id, client_secret, group_id]):
        print("❌ Missing environment variables!")
        return

    # Create Graph client
    print("📧 Connecting to rec_team@volibits.com group...")
    client = GraphGroupClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        group_id=group_id
    )

    # Get threads (today only)
    print("📬 Fetching recent threads (today only)...")
    threads = client.list_threads(max_results=50, today_only=True)

    if not threads:
        print("❌ No threads found!")
        return

    print(f"✅ Found {len(threads)} threads")
    print()

    # Show available threads
    print("Available emails:")
    print("-" * 80)
    for i, thread in enumerate(threads, 1):
        topic = thread.get('topic', 'No subject')
        last_delivered = thread.get('lastDeliveredDateTime', 'Unknown')
        print(f"{i}. {topic}")
        print(f"   Delivered: {last_delivered}")
    print("-" * 80)
    print()

    # Let user choose or default to first
    choice = input("Which email to test? (1-{}, press Enter for 1): ".format(len(threads)))

    if not choice.strip():
        choice = "1"

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(threads):
            print("❌ Invalid choice!")
            return
    except ValueError:
        print("❌ Invalid choice!")
        return

    selected_thread = threads[idx]
    thread_id = selected_thread.get('id')
    topic = selected_thread.get('topic', 'No subject')

    print()
    print(f"📧 Selected: {topic}")
    print(f"   Thread ID: {thread_id}")
    print()

    # Get posts from this thread
    print("📨 Fetching email content...")
    try:
        posts = client.get_thread_posts(thread_id)

        if not posts:
            print("❌ No posts in this thread!")
            return

        print(f"✅ Found {len(posts)} post(s) in thread")
        print()

        # Try to find a post with candidate data by parsing ALL posts
        # Some threads have replies/forwards with no data
        print("🔍 Searching all posts for candidate data...")
        print()

        best_post = None
        best_post_idx = 0
        max_candidates = 0

        for i, post in enumerate(posts):
            body_info = post.get('body', {})
            body_content = body_info.get('content', '')
            body_type = body_info.get('contentType', 'text')

            # Quick check: does this post have a table?
            if '<table' not in body_content.lower():
                continue

            # Try parsing this post
            from_info = post.get('from', {})
            sender = from_info.get('emailAddress', {}).get('address', 'Unknown')

            # Create temporary email message
            msg = email.message.EmailMessage()
            msg['Subject'] = topic
            msg['From'] = sender
            msg['To'] = 'rec_team@volibits.com'
            msg.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

            # Save to temporary file
            temp_file = Path('/tmp/test_email_temp.eml')
            with open(temp_file, 'wb') as f:
                f.write(msg.as_bytes())

            # Parse
            try:
                parser = EmailParser(str(temp_file))
                parsed_data = parser.parse()
                num_candidates = len(parsed_data.get('candidates', []))

                if num_candidates > max_candidates:
                    max_candidates = num_candidates
                    best_post = post
                    best_post_idx = i
            except:
                pass

        if best_post is None:
            # No post with candidates found, use first post
            best_post = posts[0]
            best_post_idx = 0

        if max_candidates > 0:
            print(f"📝 Found {max_candidates} candidate(s) in post #{best_post_idx + 1}")
        else:
            print(f"📝 No candidates found in any post, using post #{best_post_idx + 1}")
        print()

        # Extract email details from best post
        from_info = best_post.get('from', {})
        sender = from_info.get('emailAddress', {}).get('address', 'Unknown')

        received_date = best_post.get('receivedDateTime', '')

        body_info = best_post.get('body', {})
        body_content = body_info.get('content', '')
        body_type = body_info.get('contentType', 'text')

        print("📋 Email Details:")
        print(f"   From: {sender}")
        print(f"   Subject: {topic}")
        print(f"   Received: {received_date}")
        print(f"   Body Type: {body_type}")
        print(f"   Body Length: {len(body_content)} chars")
        print()

        # Show body preview
        print("📄 Body Preview (first 500 chars):")
        print("-" * 80)
        preview = body_content[:500].replace('\n', ' ').replace('\r', '')
        print(preview + "...")
        print("-" * 80)
        print()

        # Display raw table
        display_raw_table(body_content)

        # Try to parse candidates from best post
        print("🔍 Attempting to parse candidates...")
        print()

        # Create email message
        msg = email.message.EmailMessage()
        msg['Subject'] = topic
        msg['From'] = sender
        msg['To'] = 'rec_team@volibits.com'
        msg.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

        # Save to temporary file for parser
        temp_file = Path('/tmp/test_email.eml')
        with open(temp_file, 'wb') as f:
            f.write(msg.as_bytes())

        # Parse with EmailParser
        parser = EmailParser(str(temp_file))
        parsed_data = parser.parse()
        candidates = parsed_data.get('candidates', [])

        print(f"📊 Parsing Results:")
        print(f"   Company Code: {parsed_data.get('company_code', 'N/A')}")
        print(f"   Company Name: {parsed_data.get('company_name', 'N/A')}")
        print(f"   Skill: {parsed_data.get('skill', 'N/A')}")
        print(f"   Recruiter: {parsed_data.get('recruiter', 'N/A')}")
        print(f"   Client Recruiter: {parsed_data.get('client_recruiter', 'N/A')}")
        print(f"   Candidates found: {len(candidates)}")
        print()

        if candidates:
            print("✅ CANDIDATE DATA EXTRACTED:")
            print("=" * 80)

            for i, candidate in enumerate(candidates, 1):
                print(f"\n🧑 Candidate {i}:")
                print("-" * 80)

                # Show all fields
                for field, value in sorted(candidate.items()):
                    if value:
                        print(f"   {field:25} : {value}")

                print("-" * 80)

            print()
            print("=" * 80)
            print("✅ PARSING SUCCESSFUL!")
            print("=" * 80)
            print()
            print("Summary:")
            print(f"  ✅ Extracted {len(candidates)} candidate(s)")
            print(f"  ✅ Company: {candidates[0].get('company_name', 'N/A')}")
            print(f"  ✅ Skill: {candidates[0].get('general_skill', 'N/A')}")
            print(f"  ✅ Recruiter: {candidates[0].get('recruiter', 'N/A')}")
            print()
            print("Next steps:")
            print("  1. Verify the data looks correct")
            print("  2. If correct, we can enable auto-insertion to database")
            print("  3. Set up email tracking to prevent duplicates")
            print()

        else:
            print("⚠️  NO CANDIDATES FOUND!")
            print()
            print("Possible reasons:")
            print("  1. Email doesn't have candidate table")
            print("  2. Table format not recognized")
            print("  3. Required fields missing (Name, Email, Contact)")
            print()
            print("Let me show the full email body for debugging...")
            print()
            print("=" * 80)
            print("FULL EMAIL BODY:")
            print("=" * 80)
            print(body_content)
            print("=" * 80)

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
