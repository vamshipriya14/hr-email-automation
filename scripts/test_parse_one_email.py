#!/usr/bin/env python3
"""
Test parsing ONE email from individual mailbox to verify candidate extraction
Dry run - shows what would be inserted WITHOUT actually inserting
Filters: ignores FW:, RE:, and Reminder emails
"""
import os
import sys
import argparse
from pathlib import Path
import email
from email import policy
from io import BytesIO
import re

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from graph_email_client import GraphEmailClient
    from email_parser import EmailParser
    from database import PostgresClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.graph_email_client import GraphEmailClient
    from src.email_parser import EmailParser
    from src.database import PostgresClient


def should_skip_email(subject: str) -> bool:
    """
    Check if email should be skipped based on subject patterns
    
    Returns:
        True if email should be skipped, False otherwise
    """
    if not subject:
        return False
    
    subject_lower = subject.lower().strip()
    
    # Ignore emails with "Reminder" in subject
    if "reminder" in subject_lower:
        return True
    
    # Ignore all forwarded emails (FW: or Fw:)
    if subject_lower.startswith("fw:"):
        return True
    
    # Ignore all replied emails (RE: or Re:)
    if subject_lower.startswith("re:"):
        return True
    
    return False


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
    import argparse
    
    parser = argparse.ArgumentParser(description='Test parsing ONE email from mailbox')
    parser.add_argument('--all-emails', action='store_true',
                       help='Fetch all emails (read and unread), not just unread')
    args = parser.parse_args()
    
    print("=" * 80)
    print("🧪 TEST PARSING ONE EMAIL FROM MAILBOX")
    print("=" * 80)
    print()

    # Get credentials
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    email_user = os.getenv('EMAIL_USER')

    if not all([tenant_id, client_id, client_secret, email_user]):
        print("❌ Missing environment variables!")
        return

    # Create Graph client
    print(f"📧 Connecting to {email_user} mailbox...")
    client = GraphEmailClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        email_user=email_user
    )

    # Get messages (unread only or all, based on flag)
    if args.all_emails:
        print("📬 Fetching all messages (read and unread)...")
        all_messages = client.list_all_messages(max_results=50)
    else:
        print("📬 Fetching unread messages only...")
        all_messages = client.list_unread_messages(max_results=50)

    if not all_messages:
        if args.all_emails:
            print("❌ No messages found!")
        else:
            print("❌ No unread messages found!")
            print("   💡 Tip: Use --all-emails flag to fetch all messages (read and unread)")
        return

    msg_type = "message(s)" if args.all_emails else "unread message(s)"
    print(f"✅ Found {len(all_messages)} {msg_type}")
    
    # Filter out skipped emails
    threads = [msg for msg in all_messages if not should_skip_email(msg.get('subject', ''))]
    
    if not threads:
        print("❌ No eligible emails found after filtering!")
        print("   (All emails are either forwarded/replied or contain 'Reminder')")
        return
    
    print(f"📋 Available emails ({len(threads)} after filtering):")
    print("-" * 80)
    for i, msg in enumerate(threads, 1):
        subject = msg.get('subject', 'No subject')
        received = msg.get('receivedDateTime', 'Unknown')
        sender = msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
        print(f"{i}. {subject}")
        print(f"   From: {sender}")
        print(f"   Received: {received}")
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

    selected_message = threads[idx]
    message_id = selected_message.get('id')
    topic = selected_message.get('subject', 'No subject')

    print()
    print(f"📧 Selected: {topic}")
    print(f"   Message ID: {message_id}")
    print()

    # Get full message content
    print("📨 Fetching email content...")
    try:
        # First try the standard API
        try:
            full_message = client.get_message_content(message_id)
            posts = [full_message]
            print(f"✅ Message retrieved via standard API")
        except Exception as e:
            # If standard API fails (e.g., for group conversation messages),
            # try converting MIME to parsed format
            print(f"⚠️  Standard API failed ({str(e)[:50]}...), trying MIME format...")
            mime_content = client.get_message_mime(message_id)
            
            # Parse MIME content
            msg_obj = email.message_from_string(mime_content, policy=policy.default)
            
            # Extract text content from multipart messages
            body_content = ""
            content_type_found = 'plain'
            
            if msg_obj.is_multipart():
                # Try HTML first (preferred for table extraction), then plain text
                for part in msg_obj.iter_parts():
                    if part.get_content_maintype() == 'text':
                        try:
                            content_type = part.get_content_type()
                            part_content = part.get_content()
                            
                            if content_type == 'text/html':
                                body_content = part_content
                                content_type_found = 'html'
                                break
                            elif content_type == 'text/plain' and not body_content:
                                body_content = part_content
                                content_type_found = 'plain'
                        except Exception as e2:
                            pass
            else:
                # Non-multipart message
                try:
                    body_content = msg_obj.get_content()
                    content_type = msg_obj.get_content_type()
                    if 'html' in content_type:
                        content_type_found = 'html'
                except:
                    try:
                        payload = msg_obj.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body_content = payload.decode('utf-8', errors='ignore')
                        else:
                            body_content = str(payload)
                    except:
                        body_content = str(msg_obj.get_payload())
            
            # Convert to format similar to message_content response
            from_header = msg_obj['From'] or 'Unknown'
            # Parse "Name <email>" format
            from_email = from_header.split('<')[-1].rstrip('>') if '<' in from_header else from_header
            
            full_message = {
                'id': message_id,
                'subject': msg_obj['Subject'] or 'No subject',
                'from': {'emailAddress': {'address': from_email}},
                'receivedDateTime': msg_obj['Date'] or '',
                'body': {
                    'contentType': content_type_found,
                    'content': body_content
                }
            }
            posts = [full_message]
            print(f"✅ Message retrieved via MIME")
        
        print()

        # Parse the message for candidate data
        print("🔍 Parsing message for candidate data...")
        print()

        best_post = None
        best_post_idx = 0
        max_candidates = 0

        for i, post in enumerate(posts):
            body_info = post.get('body', {})
            body_content = body_info.get('content', '')
            body_type = body_info.get('contentType', 'text')

            # Quick check: does this message have a table?
            if '<table' not in body_content.lower():
                continue

            # Try parsing this message
            from_info = post.get('from', {})
            sender = from_info.get('emailAddress', {}).get('address', 'Unknown')

            # Create temporary email message
            msg_obj = email.message.EmailMessage()
            msg_obj['Subject'] = topic
            msg_obj['From'] = sender
            msg_obj['To'] = email_user
            msg_obj.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

            # Save to temporary file
            temp_file = Path('/tmp/test_email_temp.eml')
            with open(temp_file, 'wb') as f:
                f.write(msg_obj.as_bytes())

            # Parse (pass thread posts for participant email matching)
            try:
                parser = EmailParser(str(temp_file), thread_posts=posts)
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

        # Look up real To: email from sender's Sent Items
        mime_to_header = None
        tenant_id = os.getenv('AZURE_TENANT_ID')
        client_id_val = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        if sender and '@volibits.com' in sender.lower():
            try:
                print(f"🔍 Looking up To: from sender's Sent Items ({sender})...")
                user_client = GraphEmailClient(
                    tenant_id=tenant_id,
                    client_id=client_id_val,
                    client_secret=client_secret,
                    email_user=sender
                )
                import requests as req
                url = f"https://graph.microsoft.com/v1.0/users/{sender}/mailFolders/sentitems/messages"
                safe_subject = topic.replace("'", "''")
                params = {
                    '$filter': f"subject eq '{safe_subject}'",
                    '$select': 'id,toRecipients,subject,sentDateTime',
                    '$top': 1
                }
                resp = req.get(url, headers=user_client.get_headers(), params=params, timeout=30)
                resp.raise_for_status()
                messages = resp.json().get('value', [])
                if messages:
                    for r in messages[0].get('toRecipients', []):
                        addr = r.get('emailAddress', {}).get('address', '')
                        name = r.get('emailAddress', {}).get('name', '')
                        if addr and '@volibits.com' not in addr.lower():
                            mime_to_header = addr
                            print(f"✅ Found To: {name} <{addr}>")
                            break
                if not mime_to_header:
                    print(f"⚠️  No external recipient found in Sent Items")
            except Exception as e:
                print(f"⚠️  Sender inbox lookup failed: {e}")

        body_info = best_post.get('body', {})
        body_content = body_info.get('content', '')
        body_type = body_info.get('contentType', 'text')

        print("📋 Email Details:")
        print(f"   From: {sender}")
        print(f"   Subject: {topic}")
        print(f"   Received: {received_date}")
        print(f"   Body Type: {body_type}")
        print(f"   Body Length: {len(body_content)} chars")
        if mime_to_header:
            print(f"   📧 Client Email (from MIME): {mime_to_header}")
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
        msg['To'] = email_user
        msg.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

        # Save to temporary file for parser
        temp_file = Path('/tmp/test_email.eml')
        with open(temp_file, 'wb') as f:
            f.write(msg.as_bytes())

        # Parse with EmailParser (pass thread posts for participant email matching)
        parser = EmailParser(str(temp_file), thread_posts=posts)
        parsed_data = parser.parse()
        candidates = parsed_data.get('candidates', [])

        # Enrich candidates with email_from / email_to / client_recruiter
        for candidate in candidates:
            candidate['email_from'] = sender
            if mime_to_header:
                candidate['email_to'] = mime_to_header
                candidate['client_recruiter'] = mime_to_header.split('@')[0]

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
