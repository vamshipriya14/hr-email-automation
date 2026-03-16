#!/usr/bin/env python3
"""
Automated Email Monitor for HR Database
Monitors rec_team@volibits.com group for new candidate emails
Automatically parses and inserts candidates into database
"""
import os
import sys
import time
import email
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from graph_group_client import GraphGroupClient
from graph_email_client import GraphEmailClient
from email_parser import EmailParser
from database import PostgresClient
from email_tracker import EmailTracker


class EmailMonitor:
    """Automated email monitoring and processing"""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 group_id: str, db_client: PostgresClient, table_name: str = 'hrvolibit'):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.graph_client = GraphGroupClient(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            group_id=group_id
        )
        self.db_client = db_client
        self.tracker = EmailTracker()
        self.table_name = table_name
        self._user_clients: Dict[str, GraphEmailClient] = {}  # cache per sender

    def _get_user_client(self, email_user: str) -> GraphEmailClient:
        """Get or create a GraphEmailClient for a specific user (cached)."""
        if email_user not in self._user_clients:
            self._user_clients[email_user] = GraphEmailClient(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
                email_user=email_user
            )
        return self._user_clients[email_user]

    def _get_to_email_from_sender_inbox(self, sender_email: str, subject: str) -> str:
        """
        Look up the sent message in the sender's mailbox to get real toRecipients.
        Uses /users/{sender}/mailFolders/sentitems/messages filtered by subject.
        Returns first external (non-volibits) recipient email, or None.
        """
        try:
            client = self._get_user_client(sender_email)
            url = f"{client.graph_api_endpoint}/users/{sender_email}/mailFolders/sentitems/messages"
            safe_subject = subject.replace("'", "''")
            params = {
                '$filter': f"subject eq '{safe_subject}'",
                '$select': 'id,toRecipients,subject,sentDateTime',
                '$top': 1
            }
            response = requests.get(url, headers=client.get_headers(), params=params, timeout=30)
            response.raise_for_status()
            messages = response.json().get('value', [])
            if messages:
                for r in messages[0].get('toRecipients', []):
                    addr = r.get('emailAddress', {}).get('address', '')
                    if addr and '@volibits.com' not in addr.lower():
                        return addr
        except Exception as e:
            print(f"         ⚠️  Sender inbox lookup failed: {e}")
        return None

    def process_new_emails(self, max_emails: int = 50, dry_run: bool = False, today_only: bool = False) -> Dict:
        """
        Process new emails from the group

        Args:
            max_emails: Maximum number of emails to check
            dry_run: If True, don't actually insert to database
            today_only: If True, only process emails from today

        Returns:
            Dict with processing statistics
        """
        stats = {
            'checked': 0,
            'new': 0,
            'processed': 0,
            'candidates_inserted': 0,
            'errors': 0,
            'skipped_no_candidates': 0
        }

        print("\n" + "=" * 80)
        print(f"📧 EMAIL MONITORING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if today_only:
            print("   (Processing today's emails only)")
        print("=" * 80)
        print()

        # Get recent threads
        try:
            print(f"📬 Fetching up to {max_emails} recent threads" + (" from today..." if today_only else "..."))
            threads = self.graph_client.list_threads(max_results=max_emails, today_only=today_only)
            print(f"   ✅ Found {len(threads)} threads")
            print()
        except Exception as e:
            print(f"   ❌ Failed to fetch threads: {e}")
            stats['errors'] += 1
            return stats

        # Process each thread
        for i, thread in enumerate(threads, 1):
            thread_id = thread.get('id')
            topic = thread.get('topic', 'No subject')
            last_delivered = thread.get('lastDeliveredDateTime', 'Unknown')

            stats['checked'] += 1

            print(f"[{i}/{len(threads)}] {topic}")
            print(f"         Thread ID: {thread_id[:40]}...")
            print(f"         Last delivered: {last_delivered}")

            # Get posts to find the internetMessageId
            try:
                posts = self.graph_client.get_thread_posts(thread_id)
                if not posts:
                    print(f"         ⚠️  No posts found, skipping")
                    print()
                    continue

                # Find the post with candidate data (search all posts)
                best_post = self._find_best_post(posts)
                if not best_post:
                    print(f"         ⚠️  No post with table found, skipping")
                    print()
                    continue

                # Use thread_id as the unique identifier for tracking
                # Each thread represents a unique email conversation
                if self.tracker.is_processed(thread_id):
                    print(f"         ✓ Already processed")
                    print()
                    continue

                stats['new'] += 1
                print(f"         🆕 NEW EMAIL - Processing...")

                # Look up real To: email from sender's Sent Items (most reliable)
                mime_to_email = None
                sender_addr = best_post.get('from', {}).get('emailAddress', {}).get('address', '')
                if sender_addr and '@volibits.com' in sender_addr.lower():
                    mime_to_email = self._get_to_email_from_sender_inbox(sender_addr, topic)
                    if mime_to_email:
                        print(f"         📧 Real To (from sender inbox): {mime_to_email}")
                    else:
                        print(f"         ⚠️  No external To: found in sender inbox")

                # Process the email (pass all posts for email lookup)
                result = self._process_email(best_post, posts, thread_id, topic, dry_run, mime_to_email)

                if result['success']:
                    stats['processed'] += 1
                    stats['candidates_inserted'] += result['candidates_inserted']

                    if result['candidates_inserted'] > 0:
                        print(f"         ✅ Processed {result['candidates_inserted']} candidate(s)")
                    else:
                        print(f"         ✓ Processed (no candidates found)")
                        stats['skipped_no_candidates'] += 1

                    # Mark as processed using thread_id
                    self.tracker.mark_processed(
                        message_id=thread_id,
                        thread_id=thread_id,
                        subject=topic,
                        num_candidates=result['candidates_inserted'],
                        status='success'
                    )
                else:
                    stats['errors'] += 1
                    print(f"         ❌ Error: {result['error']}")

                    # Mark as processed with error
                    self.tracker.mark_processed(
                        message_id=thread_id,
                        thread_id=thread_id,
                        subject=topic,
                        num_candidates=0,
                        status='error',
                        error=result['error']
                    )

                print()

            except Exception as e:
                print(f"         ❌ Unexpected error: {e}")
                stats['errors'] += 1
                print()
                continue

        # Print summary
        print("=" * 80)
        print("📊 PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Threads checked: {stats['checked']}")
        print(f"New emails found: {stats['new']}")
        print(f"Successfully processed: {stats['processed']}")
        print(f"Candidates inserted: {stats['candidates_inserted']}")
        print(f"Skipped (no candidates): {stats['skipped_no_candidates']}")
        print(f"Errors: {stats['errors']}")
        print()

        # Show tracker stats
        tracker_stats = self.tracker.get_stats()
        print("📈 TOTAL STATS (All Time)")
        print("=" * 80)
        print(f"Total emails processed: {tracker_stats['total_processed']}")
        print(f"Total candidates inserted: {tracker_stats['total_candidates']}")
        print(f"Success rate: {tracker_stats['successful']}/{tracker_stats['total_processed']}")
        print("=" * 80)
        print()

        return stats

    def _find_external_participant(self, all_posts: List[Dict]) -> str:
        """
        Fallback: find the first external (non-volibits) email address
        from thread post senders or toRecipients.
        Used when sender inbox lookup fails.
        """
        seen = set()
        for post in all_posts:
            for addr_info in [post.get('from', {})] + post.get('toRecipients', []):
                email_info = addr_info.get('emailAddress', {})
                addr = email_info.get('address', '')
                if addr and addr not in seen:
                    seen.add(addr)
                    if '@volibits.com' not in addr.lower():
                        return addr
        return None

    def _find_best_post(self, posts: List[Dict]) -> Dict:
        """
        Find the post with candidate data by actually parsing each post
        Returns the post with the most candidates
        """
        best_post = None
        max_candidates = 0

        for i, post in enumerate(posts):
            body_content = post.get('body', {}).get('content', '')

            # Quick check: does this post have a table?
            if '<table' not in body_content.lower():
                continue

            # Try parsing this post to count candidates
            try:
                from_info = post.get('from', {})
                sender = from_info.get('emailAddress', {}).get('address', 'Unknown')

                # Create temporary email message
                msg = email.message.EmailMessage()
                msg['Subject'] = 'Test'
                msg['From'] = sender
                msg['To'] = 'rec_team@volibits.com'
                body_type = post.get('body', {}).get('contentType', 'text')
                msg.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

                # Save to temporary file
                temp_file = Path('/tmp/find_best_post_temp.eml')
                with open(temp_file, 'wb') as f:
                    f.write(msg.as_bytes())

                # Parse to count candidates (pass posts for participant matching)
                parser = EmailParser(str(temp_file), thread_posts=posts)
                parsed_data = parser.parse()
                num_candidates = len(parsed_data.get('candidates', []))

                if num_candidates > max_candidates:
                    max_candidates = num_candidates
                    best_post = post

                # Cleanup
                if temp_file.exists():
                    temp_file.unlink()

            except Exception as e:
                # If parsing fails, skip this post
                continue

        return best_post

    def _process_email(self, post: Dict, all_posts: List[Dict], thread_id: str, topic: str,
                      dry_run: bool = False, mime_to_email: str = None) -> Dict:
        """
        Process a single email post

        Returns:
            Dict with processing result
        """
        result = {
            'success': False,
            'candidates_inserted': 0,
            'error': None
        }

        try:
            # Extract email details
            from_info = post.get('from', {})
            sender = from_info.get('emailAddress', {}).get('address', 'Unknown')

            # If sender is external (client reply), find the volibits recruiter from thread
            volibits_recruiter = None
            if '@volibits.com' not in sender.lower():
                for p in all_posts:
                    p_addr = p.get('from', {}).get('emailAddress', {}).get('address', '')
                    if '@volibits.com' in p_addr.lower():
                        volibits_recruiter = p_addr
                        break

            body_info = post.get('body', {})
            body_content = body_info.get('content', '')
            body_type = body_info.get('contentType', 'text')

            # Create temporary email message for parser
            msg = email.message.EmailMessage()
            msg['Subject'] = topic
            # Use volibits recruiter as From if sender is external, so parser sets recruiter correctly
            msg['From'] = volibits_recruiter if volibits_recruiter else sender
            msg['To'] = 'rec_team@volibits.com'
            msg.set_content(body_content, subtype='html' if body_type == 'html' else 'plain')

            # Save to temporary file
            temp_file = Path('/tmp/email_monitor_temp.eml')
            with open(temp_file, 'wb') as f:
                f.write(msg.as_bytes())

            # Parse email (pass all_posts for participant email matching)
            parser = EmailParser(str(temp_file), thread_posts=all_posts)
            parsed_data = parser.parse()
            candidates = parsed_data.get('candidates', [])

            # Get sender email — use volibits recruiter if the post sender is external (client reply)
            sender_full_email = volibits_recruiter if volibits_recruiter else from_info.get('emailAddress', {}).get('address', sender)

            # Determine email_to: priority order:
            # 1. Sender inbox API (most accurate)
            # 2. Actual sender if this is a client-reply thread
            # 3. First external participant in the thread (fallback)
            if not mime_to_email and volibits_recruiter:
                mime_to_email = sender  # client who replied IS the external contact
            if not mime_to_email:
                mime_to_email = self._find_external_participant(all_posts)

            # Enrich candidates with email metadata
            for candidate in candidates:
                candidate['email_from'] = sender_full_email
                if mime_to_email:
                    candidate['email_to'] = mime_to_email
                    candidate['client_recruiter'] = mime_to_email.split('@')[0]

            # Normalize client_recruiter to always be username (before @), never full email
            for candidate in candidates:
                cr = candidate.get('client_recruiter', '')
                if cr and '@' in cr:
                    candidate['client_recruiter'] = cr.split('@')[0]

            # Debug: Show enriched fields for first candidate
            if candidates and dry_run:
                sample = candidates[0]
                print(f"         📋 Sample candidate fields:")
                print(f"            email_from: {sample.get('email_from', 'N/A')}")
                print(f"            email_to: {sample.get('email_to', 'N/A')}")
                print(f"            client_recruiter: {sample.get('client_recruiter', 'N/A')}")
                print(f"            jr_no: {sample.get('jr_no', 'N/A')}")
                print(f"            created_by/modified_by: {sample.get('email_from', 'N/A')}")

            # Process candidates
            if candidates:
                if dry_run:
                    # Dry run: just count what would be inserted
                    result['candidates_inserted'] = len(candidates)
                else:
                    # Live mode: actually insert to database
                    print(f"         💾 Inserting {len(candidates)} candidate(s) to database...")
                    for i, candidate in enumerate(candidates, 1):
                        try:
                            print(f"            [{i}/{len(candidates)}] Inserting {candidate.get('name_of_candidate', 'Unknown')}...")
                            success = self._insert_candidate(candidate)
                            if success:
                                result['candidates_inserted'] += 1
                                print(f"            [{i}/{len(candidates)}] ✅ Inserted successfully")
                            else:
                                print(f"            [{i}/{len(candidates)}] ❌ Insert returned False (0 rows affected)")
                        except Exception as e:
                            print(f"            [{i}/{len(candidates)}] ⚠️  Exception: {e}")
                            import traceback
                            traceback.print_exc()

            # Cleanup temp file
            if temp_file.exists():
                temp_file.unlink()

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        return result

    def _insert_candidate(self, candidate: Dict) -> bool:
        """Insert candidate into database"""
        # Check for duplicates
        duplicate_type = self._check_duplicate_type(candidate)
        if duplicate_type:
            candidate['is_duplicate'] = duplicate_type

        # Prepare insert query
        fields = []
        values = []
        placeholders = []

        allowed_fields = {
            'name_of_candidate', 'email_id', 'contact_number', 'jr_no', 'date',
            'general_skill', 'company_name', 'client_recruiter', 'recruiter',
            'total_experience', 'relevant_experience', 'current_ctc', 'expected_ctc',
            'notice_period', 'current_location', 'preferred_location', 'current_org',
            'status', 'final_status', 'remarks', 'delivery_type',
            'email_from', 'email_to', 'attachment', 'record_status', 'is_duplicate'
        }

        # Add candidate fields
        for field, value in candidate.items():
            if field in allowed_fields and value:
                trimmed_value = value.strip() if isinstance(value, str) else value
                if trimmed_value:
                    fields.append(field)
                    values.append(trimmed_value)
                    placeholders.append('%s')

        # Add audit fields (use email_from for full email address)
        created_by_value = candidate.get('email_from', 'email_monitor')
        fields.extend(['created_by', 'created_date'])
        values.extend([created_by_value, datetime.now()])
        placeholders.extend(['%s', '%s'])

        modified_by_value = candidate.get('email_from', 'email_monitor')
        fields.extend(['modified_by', 'modified_date'])
        values.extend([modified_by_value, datetime.now()])
        placeholders.extend(['%s', '%s'])

        query = f"""
            INSERT INTO {self.table_name} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
        """

        try:
            affected = self.db_client.execute_update(query, tuple(values))
            return affected > 0
        except Exception as e:
            raise e

    def _check_duplicate_type(self, candidate: Dict) -> str:
        """Check if candidate is duplicate"""
        email = candidate.get('email_id', '').strip()
        contact = candidate.get('contact_number', '').strip()

        if email and contact:
            query = f"SELECT id FROM {self.table_name} WHERE email_id = %s AND contact_number = %s LIMIT 1"
            result = self.db_client.execute_query(query, (email, contact))
            if result and len(result) > 0:
                return "DuplicateFound"

        if email:
            query = f"SELECT id FROM {self.table_name} WHERE email_id = %s LIMIT 1"
            result = self.db_client.execute_query(query, (email,))
            if result and len(result) > 0:
                return "DuplicateFound - Email"

        if contact:
            query = f"SELECT id FROM {self.table_name} WHERE contact_number = %s LIMIT 1"
            result = self.db_client.execute_query(query, (contact,))
            if result and len(result) > 0:
                return "DuplicateFound - Contact"

        return None

    def run_continuous(self, interval_seconds: int = 300, dry_run: bool = False, today_only: bool = False):
        """
        Run monitor continuously

        Args:
            interval_seconds: Time between checks (default: 300 = 5 minutes)
            dry_run: If True, don't actually insert to database
            today_only: If True, only process emails from today
        """
        print("=" * 80)
        print("🚀 STARTING CONTINUOUS EMAIL MONITORING")
        print("=" * 80)
        print(f"Check interval: {interval_seconds} seconds ({interval_seconds/60} minutes)")
        print(f"Dry run mode: {dry_run}")
        print(f"Today only: {today_only}")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 80)
        print()

        try:
            while True:
                self.process_new_emails(max_emails=50, dry_run=dry_run, today_only=today_only)

                print(f"⏰ Waiting {interval_seconds} seconds until next check...")
                print()
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print()
            print("=" * 80)
            print("🛑 MONITORING STOPPED")
            print("=" * 80)
            print()


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Automated HR Email Monitor')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously (default: run once)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300 = 5 minutes)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run - do not insert to database')
    parser.add_argument('--max-emails', type=int, default=50,
                       help='Maximum emails to check per run (default: 50)')
    parser.add_argument('--today-only', action='store_true',
                       help='Only process emails from today (current day)')

    args = parser.parse_args()

    # Get credentials from environment
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    group_id = os.getenv('GROUP_ID')

    db_host = os.getenv('DB_HOST')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    table_name = os.getenv('TABLE_NAME', 'hrvolibit')  # Default to 'hrvolibit' if not set

    # Validate credentials
    if not all([tenant_id, client_id, client_secret, group_id]):
        print("❌ Missing Azure credentials!")
        print("   Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, GROUP_ID")
        return 1

    if not all([db_host, db_name, db_user, db_password]):
        print("❌ Missing database credentials!")
        print("   Set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        return 1

    # Connect to database
    try:
        db_client = PostgresClient(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        print("✅ Database connected")
        print()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return 1

    # Create monitor
    monitor = EmailMonitor(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        group_id=group_id,
        db_client=db_client,
        table_name=table_name
    )

    # Run monitor
    if args.continuous:
        monitor.run_continuous(interval_seconds=args.interval, dry_run=args.dry_run, today_only=args.today_only)
    else:
        monitor.process_new_emails(max_emails=args.max_emails, dry_run=args.dry_run, today_only=args.today_only)

    return 0


if __name__ == '__main__':
    sys.exit(main())
