"""
Email Monitor for HR Database Auto-Updates
Monitors rec_team@volibits.com mailbox and auto-processes candidate emails
"""
import os
import sys
import imaplib
import email
from email.header import decode_header
import time
from datetime import datetime
from pathlib import Path
import re
import toml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .database import PostgresClient
    from .email_parser import EmailProcessor, EmailParser
except ImportError:
    from database import PostgresClient
    from email_parser import EmailProcessor, EmailParser


class EmailMonitor:
    """Monitor mailbox and auto-process candidate emails"""

    def __init__(self, imap_server: str, email_user: str, email_pass: str, db_client: PostgresClient):
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_pass = email_pass
        self.db_client = db_client
        self.processor = EmailProcessor(db_client)

        # Folder to save processed emails (optional)
        self.save_folder = Path.home() / "Downloads" / "emails" / "processed"
        self.save_folder.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """Connect to IMAP server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_user, self.email_pass)
            print(f"✅ Connected to {self.email_user}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IMAP server"""
        try:
            self.mail.logout()
        except:
            pass

    def is_candidate_email(self, subject: str) -> bool:
        """
        Check if subject matches candidate email pattern

        Pattern: CODE: Skill Name
        - CODE can be any 2-4 letter abbreviation (BS, CE, XY, ABC, etc.)
        - Must have colon and space after code
        - No predefined codes needed - extracted dynamically
        """
        if not subject:
            return False

        # Remove Fw:/Fwd:/RE: prefixes
        clean_subject = re.sub(r'^(Fw|Fwd|RE):\s*', '', subject, flags=re.IGNORECASE).strip()

        # Check if starts with any code pattern (2-4 letters, colon, space, skill)
        # Examples: BS: Java, CE: Power BI, XY: Developer, ABC: Testing
        pattern = r'^[A-Z]{2,4}:\s*.+'

        return bool(re.match(pattern, clean_subject, re.IGNORECASE))

    def decode_subject(self, subject):
        """Decode email subject"""
        decoded_parts = decode_header(subject)
        decoded_subject = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded_subject += part.decode(encoding or 'utf-8')
                except:
                    decoded_subject += part.decode('utf-8', errors='ignore')
            else:
                decoded_subject += part

        return decoded_subject

    def process_new_emails(self, folder="INBOX", mark_as_read=True, move_to_folder=None):
        """
        Check for and process new candidate emails

        Args:
            folder: IMAP folder to check (default: INBOX)
            mark_as_read: Mark processed emails as read
            move_to_folder: Move processed emails to this folder (e.g., "Processed")
        """
        try:
            # Select inbox
            self.mail.select(folder)

            # Search for unread emails
            status, messages = self.mail.search(None, 'UNSEEN')

            if status != 'OK':
                print("No messages found")
                return

            email_ids = messages[0].split()

            if not email_ids:
                print("No new emails")
                return

            print(f"\n{'='*80}")
            print(f"📬 Found {len(email_ids)} new email(s)")
            print(f"{'='*80}\n")

            processed_count = 0
            skipped_count = 0

            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = self.mail.fetch(email_id, '(RFC822)')

                    if status != 'OK':
                        continue

                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Get subject
                    subject = msg.get('Subject', '')
                    subject = self.decode_subject(subject)

                    # Get sender
                    from_email = msg.get('From', '')

                    print(f"📧 Email: {subject[:80]}...")
                    print(f"   From: {from_email}")

                    # Check if it's a candidate email
                    if not self.is_candidate_email(subject):
                        print(f"   ⏭️  Skipped (not a candidate email)\n")
                        skipped_count += 1
                        continue

                    # Save email to temp file
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_subject = re.sub(r'[^\w\s-]', '', subject).strip().replace(' ', '_')[:50]
                    temp_file = self.save_folder / f"{timestamp}_{safe_subject}.eml"

                    with open(temp_file, 'wb') as f:
                        f.write(raw_email)

                    # Process email
                    print(f"   🔄 Processing...")

                    parser = EmailParser(str(temp_file))
                    data = parser.parse()

                    candidates_inserted = 0
                    candidates_duplicate = 0

                    for candidate in data.get('candidates', []):
                        # Check duplicate type
                        duplicate_type = self.processor._check_duplicate_type(candidate)

                        # Insert (always inserts, marks duplicates)
                        success = self.processor._insert_candidate(candidate)

                        if success:
                            if duplicate_type:
                                candidates_duplicate += 1
                            else:
                                candidates_inserted += 1

                    total_candidates = len(data.get('candidates', []))
                    print(f"   ✅ Processed: {total_candidates} candidate(s)")
                    print(f"      - New: {candidates_inserted}")
                    print(f"      - Duplicates: {candidates_duplicate}")

                    # Mark as read
                    if mark_as_read:
                        self.mail.store(email_id, '+FLAGS', '\\Seen')

                    # Move to folder (optional)
                    if move_to_folder:
                        try:
                            self.mail.copy(email_id, move_to_folder)
                            self.mail.store(email_id, '+FLAGS', '\\Deleted')
                            self.mail.expunge()
                        except:
                            pass

                    processed_count += 1
                    print()

                except Exception as e:
                    print(f"   ❌ Error processing email: {e}\n")
                    continue

            print(f"\n{'='*80}")
            print(f"📊 SUMMARY")
            print(f"{'='*80}")
            print(f"Total new emails: {len(email_ids)}")
            print(f"Processed: {processed_count}")
            print(f"Skipped: {skipped_count}")
            print(f"{'='*80}\n")

        except Exception as e:
            print(f"❌ Error: {e}")

    def run_continuous(self, check_interval_seconds=300):
        """
        Run continuous monitoring (checks every N seconds)

        Args:
            check_interval_seconds: How often to check for new emails (default: 300 = 5 minutes)
        """
        print(f"🔄 Starting continuous email monitoring...")
        print(f"   Checking every {check_interval_seconds} seconds")
        print(f"   Press Ctrl+C to stop\n")

        try:
            while True:
                if self.connect():
                    self.process_new_emails()
                    self.disconnect()

                print(f"💤 Waiting {check_interval_seconds} seconds until next check...")
                print(f"   (Next check at: {datetime.now() + timedelta(seconds=check_interval_seconds)})")
                time.sleep(check_interval_seconds)

        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n\n❌ Error in monitoring loop: {e}")
        finally:
            self.disconnect()


def main():
    """Main entry point"""
    import argparse
    from datetime import timedelta

    parser = argparse.ArgumentParser(description='Monitor rec_team@volibits.com for candidate emails')
    parser.add_argument('--once', action='store_true', help='Check once and exit (default: continuous)')
    parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds (default: 300)')
    parser.add_argument('--folder', default='INBOX', help='IMAP folder to check (default: INBOX)')
    parser.add_argument('--mark-read', action='store_true', default=True, help='Mark processed emails as read')
    parser.add_argument('--move-to', help='Move processed emails to this folder')

    args = parser.parse_args()

    # Load configuration from config.toml
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')

    if not os.path.exists(config_path):
        print("❌ Error: config.toml not found")
        print(f"   Expected at: {config_path}")
        print("   Please copy config.example.toml to config.toml and fill in credentials")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = toml.load(f)
    except Exception as e:
        print(f"❌ Error loading config.toml: {e}")
        sys.exit(1)

    # Get email credentials from config
    try:
        email_config = config.get('email', {})
        imap_server = email_config.get('imap_server', 'outlook.office365.com')
        email_user = email_config.get('user')
        email_pass = email_config.get('password')

        if not email_pass or not email_user:
            print("❌ Error: Email credentials not found in config.toml")
            print("   Please add to config/config.toml:")
            print("   [email]")
            print("   imap_server = 'outlook.office365.com'")
            print("   user = 'your-email@company.com'")
            print("   password = 'your-password'")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error loading email config: {e}")
        sys.exit(1)

    # Initialize database client
    try:
        db_config = config.get('database', {})
        db_client = PostgresClient(
            host=db_config.get('host'),
            port=db_config.get('port', 5432),
            database=db_config.get('database'),
            user=db_config.get('user'),
            password=db_config.get('password')
        )
        print("✅ Database connected\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Create monitor
    monitor = EmailMonitor(imap_server, email_user, email_pass, db_client)

    # Run
    if args.once:
        # Check once and exit
        if monitor.connect():
            monitor.process_new_emails(
                folder=args.folder,
                mark_as_read=args.mark_read,
                move_to_folder=args.move_to
            )
            monitor.disconnect()
    else:
        # Continuous monitoring
        monitor.run_continuous(check_interval_seconds=args.interval)


if __name__ == '__main__':
    main()
