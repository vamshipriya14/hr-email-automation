"""
Email Tracking System
Tracks processed emails to prevent duplicate processing
"""
import json
from pathlib import Path
from typing import Set, Dict
from datetime import datetime


class EmailTracker:
    """Track processed emails using internetMessageId"""

    def __init__(self, tracking_file: str = None):
        if tracking_file is None:
            tracking_file = str(Path(__file__).parent.parent / 'data' / 'processed_emails.json')

        self.tracking_file = Path(tracking_file)
        self.tracking_file.parent.mkdir(parents=True, exist_ok=True)

        self.processed_emails = self._load_tracking_data()

    def _load_tracking_data(self) -> Dict:
        """Load tracking data from file"""
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load tracking file: {e}")
                return {}
        return {}

    def _save_tracking_data(self):
        """Save tracking data to file"""
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(self.processed_emails, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save tracking file: {e}")

    def is_processed(self, message_id: str) -> bool:
        """Check if email has been processed"""
        return message_id in self.processed_emails

    def mark_processed(self, message_id: str, thread_id: str = None,
                      subject: str = None, num_candidates: int = 0,
                      status: str = "success", error: str = None):
        """Mark email as processed"""
        self.processed_emails[message_id] = {
            'thread_id': thread_id,
            'subject': subject,
            'processed_at': datetime.now().isoformat(),
            'num_candidates': num_candidates,
            'status': status,
            'error': error
        }
        self._save_tracking_data()

    def get_stats(self) -> Dict:
        """Get processing statistics"""
        total = len(self.processed_emails)
        success = sum(1 for e in self.processed_emails.values() if e.get('status') == 'success')
        failed = sum(1 for e in self.processed_emails.values() if e.get('status') == 'error')
        total_candidates = sum(e.get('num_candidates', 0) for e in self.processed_emails.values())

        return {
            'total_processed': total,
            'successful': success,
            'failed': failed,
            'total_candidates': total_candidates
        }

    def clear_old_entries(self, days: int = 30):
        """Clear tracking entries older than X days"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        old_count = len(self.processed_emails)
        self.processed_emails = {
            k: v for k, v in self.processed_emails.items()
            if datetime.fromisoformat(v['processed_at']) > cutoff
        }
        new_count = len(self.processed_emails)

        if old_count != new_count:
            self._save_tracking_data()
            print(f"🗑️  Cleared {old_count - new_count} old entries (older than {days} days)")
