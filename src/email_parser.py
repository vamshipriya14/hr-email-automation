"""
Email Parser for HR Database Updates
Parses forwarded emails and updates hrvolibit table
"""
import os
import re
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pathlib import Path
import sys
"""
Email Parser for HR Database Updates
Parses forwarded emails and updates hrvolibit table
"""
import os
import re
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .database import PostgresClient
except ImportError:
    from database import PostgresClient


# No predefined company codes - extracted dynamically from email subject
# Any pattern "CODE: Skill" will work (e.g., BS:, CE:, XY:, ABC:, etc.)


class EmailParser:
    """Parse candidate emails and extract structured data"""

    def __init__(self, email_path: str, thread_posts: list = None):
        self.email_path = email_path
        self.raw_email = None
        self.parsed_data = {}
        self.thread_posts = thread_posts or []

    def parse_email_file(self) -> email.message.EmailMessage:
        """Parse .eml file"""
        with open(self.email_path, 'rb') as f:
            self.raw_email = BytesParser(policy=policy.default).parse(f)
        return self.raw_email

    def extract_subject_info(self) -> Tuple[str, str]:
        """
        Extract company code and skill from ORIGINAL subject line in forwarded email

        Since emails are forwarded TO you, the actual subject is in the email body.
        Look for pattern: "Subject: BS: SAP Commerce Cloud(Hybris)"

        Returns:
            (company_code, skill)
        """
        # First try to get from outer subject (if it happens to have the info)
        subject = self.raw_email.get('Subject', '')

        # Remove "[EXTERNAL]:", "Fw:" or "Fwd:" prefix
        subject = re.sub(r'^\[EXTERNAL\]:\s*', '', subject, flags=re.IGNORECASE)
        subject = re.sub(r'^(Fw|Fwd):\s*', '', subject, flags=re.IGNORECASE)
        subject = re.sub(r'^Re:\s*', '', subject, flags=re.IGNORECASE)

        # Try to extract from outer subject first
        match = re.match(r'([A-Z]{2,3}):\s*(.+?)(?:_\d+)?$', subject.strip())

        if match:
            company_code = match.group(1)
            skill = match.group(2).strip()
            return company_code, skill

        # If not found, extract from forwarded email body
        body = self.get_email_body()

        # Look for "Subject: BS: Something" in the forwarded content
        subject_patterns = [
            r'Subject:\s*([A-Z]{2,3}):\s*(.+?)(?:\n|$)',
            r'Subject:\s*([A-Z]{2,3})\s*-\s*(.+?)(?:\n|$)',
        ]

        for pattern in subject_patterns:
            match = re.search(pattern, body, re.MULTILINE | re.IGNORECASE)
            if match:
                company_code = match.group(1)
                skill = match.group(2).strip()
                return company_code, skill

        return None, None

    def extract_jr_from_subject(self) -> Optional[str]:
        """
        Extract JR number from subject line as fallback

        Handles patterns like:
        - "Profiles for Boomi Developer (Jr. 29258)"
        - "Profiles for Boomi Developer (JR 29258)"
        - "Boomi Developer (jr no 29258)"
        - "Boomi Developer (jr.no 29258)"
        - "Boomi Developer JR29258"

        Returns:
            JR number string or None
        """
        # Get subject from email header
        subject = self.raw_email.get('Subject', '')

        # Remove common prefixes
        subject = re.sub(r'^\[EXTERNAL\]:\s*', '', subject, flags=re.IGNORECASE)
        subject = re.sub(r'^(Fw|Fwd):\s*', '', subject, flags=re.IGNORECASE)
        subject = re.sub(r'^Re:\s*', '', subject, flags=re.IGNORECASE)

        # Try to find JR number patterns
        # Pattern 1: (Jr. 29258), (JR 29258), (jr no 29258), (jr.no 29258)
        match = re.search(r'\(Jr[\.\s]*(?:no)?[\.\s]*(\d+)\)', subject, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 2: Jr 29258, JR29258, jr.no 29258, jr no 29258 (without parentheses)
        match = re.search(r'Jr[\.\s]*(?:no)?[\.\s]*(\d{4,6})', subject, re.IGNORECASE)
        if match:
            return match.group(1)

        # Also check in email body for forwarded subject
        body = self.get_email_body()
        match = re.search(r'Subject:.*?\(Jr[\.\s]*(?:no)?[\.\s]*(\d+)\)', body, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def extract_original_sender(self) -> str:
        """
        Extract the original sender from forwarded email content OR email headers
        Returns full email address (e.g., salman.ahmed@volibits.com)

        Looks for patterns like:
        "From: Salman Ahmed <salman.ahmed@volibits.com>"
        """
        body = self.get_email_body()

        # Pattern to find original sender in forwarded email body
        patterns = [
            r'From:\s*([^<]+)\s*<([^>]+)>',
            r'From:\s*([^\n]+@[^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                if len(match.groups()) == 2:
                    email = match.group(2).strip()  # Email address
                else:
                    email = match.group(1).strip()

                # Return full email address
                if '@' in email:
                    return email.strip()

                return email

        # Fallback: Check email headers if not found in body
        # (for Group emails or direct emails, not forwarded)
        if self.raw_email:
            from_header = self.raw_email.get('From', '')
            if from_header:
                # Extract email from "Name <email@domain.com>" or just "email@domain.com"
                email_match = re.search(r'<([^>]+)>|([^\s<>]+@[^\s<>]+)', from_header)
                if email_match:
                    email = email_match.group(1) or email_match.group(2)
                    email = email.strip()
                    if '@' in email:
                        return email

        return None

    def _extract_thread_participant_emails(self) -> List[str]:
        """
        Extract all FROM and TO email addresses from thread posts
        Returns list of unique email addresses
        """
        emails = []

        print(f"  🔍 DEBUG: Extracting emails from {len(self.thread_posts)} thread posts")

        for post in self.thread_posts:
            # Extract FROM email
            from_info = post.get('from', {})
            if isinstance(from_info, dict):
                email_info = from_info.get('emailAddress', {})
                if isinstance(email_info, dict):
                    email = email_info.get('address', '')
                    if email:
                        print(f"    📧 Found FROM: {email}")
                        emails.append(email.lower())

            # Extract TO emails (recipients)
            recipients = post.get('toRecipients', [])
            print(f"    📬 Found {len(recipients)} TO recipients")
            for recipient in recipients:
                if isinstance(recipient, dict):
                    email_info = recipient.get('emailAddress', {})
                    if isinstance(email_info, dict):
                        email = email_info.get('address', '')
                        if email:
                            print(f"    📧 Found TO: {email}")
                            emails.append(email.lower())

        # Return unique emails
        unique_emails = list(set(emails))
        print(f"  ✅ Total unique emails found: {len(unique_emails)}")
        print(f"  📋 Emails: {unique_emails}")
        return unique_emails

    def _find_email_by_name(self, name: str) -> Optional[str]:
        """
        Find email address from thread participants that matches the given name

        Args:
            name: First name extracted from greeting (e.g., "arpita")

        Returns:
            Full email address if found (e.g., "arpita.singh@birlasoft.com")
        """
        print(f"  🔍 DEBUG: Finding email for name: '{name}'")
        print(f"  🔍 DEBUG: thread_posts available: {len(self.thread_posts) if self.thread_posts else 0}")

        if not name or not self.thread_posts:
            print(f"  ❌ DEBUG: Returning None (name={bool(name)}, thread_posts={bool(self.thread_posts)})")
            return None

        # Get all participant emails
        participant_emails = self._extract_thread_participant_emails()

        # Search for email that contains the name
        name_lower = name.lower()
        print(f"  🔍 DEBUG: Searching for '{name_lower}' in {len(participant_emails)} emails")

        for email in participant_emails:
            # Skip volibits emails
            if '@volibits.com' in email or '@volibits' in email:
                print(f"    ⏭️  Skipping volibits email: {email}")
                continue

            # Check if name appears in the email username (before @)
            email_username = email.split('@')[0].lower()
            is_match = name_lower in email_username
            print(f"    🔍 Checking '{name_lower}' in '{email_username}' → {is_match} (full: {email})")
            if is_match:
                print(f"  ✅ DEBUG: MATCH FOUND! Returning: {email}")
                return email

        print(f"  ❌ DEBUG: No matching email found for '{name_lower}'")
        return None

    def extract_client_recruiter(self) -> str:
        """
        Extract client recruiter email from To: field in forwarded email body OR from email greeting
        Returns full email address (e.g., amit.pal@birlasoft.com)

        IMPORTANT: Client recruiter can NEVER be @volibits.com
        Only extract if it's an external client email (NOT volibits domain)

        Looks for:
        1. "To: Nisha Gupta <nisha.gupta@birlasoft.com>" (forwarded emails)
        2. "Hi Ankita," or "Dear Ankita," (Group emails - extract from greeting)
        """
        body = self.get_email_body()

        # Decode HTML entities first (&lt; → <, &gt; → >, &nbsp; → space)
        import html
        body_decoded = html.unescape(body)

        # Try extracting email from To: field (email header, not table data)
        # Strategy: Find all "To:" occurrences, extract emails, return first non-volibits email in angle brackets
        # Angle brackets <email> indicate email header format (not table data)

        # Pattern 1: To: Name <email@domain.com> (most reliable - email headers use this format)
        to_matches = re.finditer(r'To:[^<]{0,100}<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>', body_decoded, re.IGNORECASE)
        for to_match in to_matches:
            email = to_match.group(1).strip()
            # Skip volibits emails
            if '@volibits.com' not in email.lower() and '@volibits' not in email.lower():
                return email

        # Pattern 2: To: email@domain.com (without angle brackets)
        to_matches = re.finditer(r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', body_decoded, re.IGNORECASE)
        for to_match in to_matches:
            email = to_match.group(1).strip()
            # Skip volibits emails and gmail (likely candidate emails)
            if '@volibits.com' not in email.lower() and '@gmail.com' not in email.lower():
                return email

        # If To: not found, try extracting from email greeting (for Group emails)
        # Look for patterns like "Hi Ankita," or "Dear John," at the start
        greeting_patterns = [
            r'(?:Hi|Hello|Dear)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[,:]',
        ]

        for pattern in greeting_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Only use first name
                first_name = name.split()[0].lower()
                print(f"  🔍 DEBUG: Extracted first name from greeting: '{first_name}'")

                # Try to find full email address from thread participants
                full_email = self._find_email_by_name(first_name)
                if full_email:
                    print(f"  ✅ DEBUG: Returning full email: {full_email}")
                    return full_email

                # Fallback: return just the first name if no matching email found
                print(f"  ⚠️  DEBUG: No email found, returning first name: {first_name}")
                return first_name

        return None

    def get_email_body(self) -> str:
        """
        Get email body content (HTML preferred, fallback to plain text)

        Returns HTML content if available (for table parsing),
        otherwise returns plain text
        """
        html_body = None
        text_body = None

        if self.raw_email.is_multipart():
            for part in self.raw_email.walk():
                content_type = part.get_content_type()
                try:
                    if content_type == 'text/html':
                        html_body = part.get_content()
                    elif content_type == 'text/plain':
                        text_body = part.get_content()
                except:
                    try:
                        content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if content_type == 'text/html':
                            html_body = content
                        elif content_type == 'text/plain':
                            text_body = content
                    except:
                        pass
        else:
            try:
                content = self.raw_email.get_content()
                content_type = self.raw_email.get_content_type()
                if content_type == 'text/html':
                    html_body = content
                else:
                    text_body = content
            except:
                try:
                    content = self.raw_email.get_payload(decode=True).decode('utf-8', errors='ignore')
                    content_type = self.raw_email.get_content_type()
                    if content_type == 'text/html':
                        html_body = content
                    else:
                        text_body = content
                except:
                    pass

        # Prefer HTML for table parsing, fallback to text
        return html_body or text_body or ""

    def parse_candidate_table(self) -> List[Dict]:
        """
        Parse candidate data from email table

        Handles TWO formats:
        1. Horizontal HTML table format (standard table with headers in first row)
        2. Vertical column format (headers listed vertically, then values)
        """
        body = self.get_email_body()

        # First try HTML table format (for Group emails and Outlook HTML emails)
        html_candidates = self._parse_tabular_format(body)
        if html_candidates:
            return html_candidates

        # Fallback to vertical format parsing (for plain text .eml files)
        lines = body.split('\n')

        # Find the start of the table (look for "JR No" or similar header)
        headers = []
        values_start_idx = -1

        for i, line in enumerate(lines):
            line = line.strip()

            # Detect table start (look for common first headers)
            line_upper = line.upper()
            if ('JR NO' in line_upper or 'JR NUMBER' in line_upper or 'SI NO' in line_upper or
                'GENERAL SKILL' in line_upper or 'VENDOR NAME' in line_upper or
                (line == 'Date' and i < 50)):
                # Start collecting headers
                header_idx = i
                while header_idx < len(lines):
                    header_line = lines[header_idx].strip()

                    # Skip empty lines
                    if not header_line:
                        header_idx += 1
                        continue

                    # Stop when we hit a value (number, email, or non-header text)
                    # Numbers at start, or emails, or values after we have enough headers
                    if headers and len(headers) > 5:
                        # Check if this looks like a value (number, email, etc)
                        if (re.match(r'^\d{1,2}$', header_line) or  # SI No value
                            re.match(r'^\d{5}', header_line) or  # JR No value
                            re.match(r'^\d{2}-[A-Za-z]{3}-\d{2}', header_line) or  # Date value
                            '@' in header_line or  # Email
                            re.match(r'^\d{10}$', header_line)):  # Phone number
                            values_start_idx = header_idx
                            break

                    # Check if this looks like a header
                    if self._is_header_field(header_line):
                        headers.append(header_line)
                        header_idx += 1
                    elif headers and len(headers) > 3:
                        # We have headers, this doesn't look like a header, must be start of values
                        values_start_idx = header_idx
                        break
                    else:
                        header_idx += 1

                break

        if not headers or values_start_idx == -1:
            return []

        # Debug output (disabled)
        import os
        debug = False
        # if debug:
        #     print(f"DEBUG: Found {len(headers)} headers")
        #     print(f"DEBUG: Headers: {headers}")
        #     print(f"DEBUG: Values start at idx: {values_start_idx}")

        # Extract multiple candidates (values repeat for each candidate)
        all_candidates = []
        value_idx = values_start_idx
        num_headers = len(headers)

        # Keep collecting candidate value sets until we run out of data
        while value_idx < len(lines):
            values = []
            candidate_start_idx = value_idx

            # Collect one set of values (one candidate)
            while len(values) < num_headers and value_idx < len(lines):
                line = lines[value_idx].strip()
                if line:
                    # Check if this looks like a new candidate's SI No (small integer 1-999)
                    # If we already have values and hit a small integer, it's probably the next candidate
                    if values and len(values) >= num_headers * 0.7 and re.match(r'^\d{1,3}$', line) and int(line) <= 999:
                        # This is likely the start of the next candidate, stop here
                        break
                    values.append(line)
                value_idx += 1

                # Safety limit - don't go too far looking for values
                if value_idx - candidate_start_idx > num_headers * 3:
                    break

            # if debug:
            #     print(f"DEBUG: Collected {len(values)} values (needed at least {num_headers * 0.5})")
            #     if values and len(values) >= 3:
            #         print(f"DEBUG: First 5 values: {values[:min(5, len(values))]}")

            # If we got enough values, create a candidate
            if len(values) >= num_headers * 0.5:  # At least 50% of headers filled
                candidate_data = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        db_field = self._map_header_to_field(header)
                        if db_field:
                            candidate_data[db_field] = values[i]

                # Only add if we have essential fields and they look valid
                # if debug:
                #     print(f"DEBUG: Candidate data before validation:")
                #     print(f"  name: {candidate_data.get('name_of_candidate')}")
                #     print(f"  email: {candidate_data.get('email_id')}")
                #     is_valid = self._is_valid_candidate(candidate_data)
                #     print(f"  valid: {is_valid}")
                if self._is_valid_candidate(candidate_data):
                    all_candidates.append(candidate_data)

            # Stop if we didn't collect enough values (end of candidates)
            if len(values) < num_headers * 0.3:
                break

            # Safety limit - max 20 candidates per email
            if len(all_candidates) >= 20:
                break

        return all_candidates

    def _is_valid_candidate(self, candidate: Dict) -> bool:
        """Validate that candidate data looks legitimate (not email signature or garbage)"""

        # Must have either name or email
        name = candidate.get('name_of_candidate', '').strip()
        email = candidate.get('email_id', '').strip()

        if not name and not email:
            return False

        # Check for invalid patterns in email
        if email:
            invalid_email_patterns = [
                '<http', '[Image]', 'Connect with us',
                'Senior', 'Recruiter', 'Subject:', 'From:', 'Sent:',
                '[cid:', 'linkedin.com/company'
            ]
            if any(pattern in email for pattern in invalid_email_patterns):
                return False

            # Clean email for validation (handle mailto: format)
            clean_email = email
            if '<mailto:' in email:
                mailto_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', email)
                if mailto_match:
                    clean_email = mailto_match.group(1)

            # Email should match basic pattern
            if '@' in clean_email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', clean_email):
                return False

        # Check for invalid patterns in name
        if name:
            invalid_name_patterns = [
                'Connect with us', 'Name of Candidate', 'Candidate Name',
                'From:', 'Sent:', 'Subject:', '[Image]', 'Person should',
                'http://', 'https://', '[cid:', 'Best Regards',
                'Senior', 'Recruiter', 'Technical'
            ]
            if any(pattern in name for pattern in invalid_name_patterns):
                return False

            # Name should not be too long (likely garbage)
            if len(name) > 100:
                return False

        return True

    def _is_header_field(self, text: str) -> bool:
        """Check if text looks like a table header field"""
        text_upper = text.upper()
        header_keywords = [
            'JR NO', 'JR NUMBER', 'DATE', 'SKILL', 'NAME', 'CANDIDATE',
            'CONTACT', 'EMAIL', 'PHONE', 'COMPANY', 'EXPERIENCE',
            'CTC', 'NOTICE', 'LOCATION', 'REMARK', 'COMMENT', 'SI NO',
            'CURRENT', 'EXPECTED', 'TOTAL', 'RELEVANT', 'PREFERRED', 'EXP',
            'E-MAIL', 'PERIOD', 'ID', 'QUALIFICATION', 'GENDER', 'VENDOR',
            'ORG', 'LOC', 'TOT', 'REL', 'CURR'
        ]
        return any(keyword in text_upper for keyword in header_keywords)

    def _map_header_to_field(self, header: str) -> Optional[str]:
        """Map email header to database field"""
        mapping = {
            'SI No': None,  # Skip serial number
            'S.No': None,  # Skip serial number
            'Gender': None,  # Skip gender
            'Vendor Name': None,  # Skip vendor
            'Qualification': None,  # Skip qualification
            'Offer If Any': None,  # Skip offer status
            'Source': None,  # Skip source
            'SPOC': None,  # Skip SPOC
            'JR No': 'jr_no',
            'JR Number': 'jr_no',
            'JR NO': 'jr_no',
            'JR': 'jr_no',  # Just "JR" column
            'RH ID': 'jr_no',  # Recruitment/Requisition ID (used by some vendors)
            'Req ID': 'jr_no',  # Requisition ID
            'Job ID': 'jr_no',  # Job ID
            'Date': 'date',
            'Skill': 'general_skill',
            'Skill Name': 'general_skill',  # Added: "Skill Name" variant
            'General Skill': 'general_skill',
            'Candidate Name': 'name_of_candidate',
            'Name of Candidate': 'name_of_candidate',
            'Name': 'name_of_candidate',
            'Contact Number': 'contact_number',
            'Contact': 'contact_number',
            'Phone': 'contact_number',
            'Mob No': 'contact_number',  # Added: "Mob No" variant
            'Mobile': 'contact_number',
            'Email ID': 'email_id',
            'Email Id': 'email_id',
            'E-Mail Id': 'email_id',
            'E-Mail ID': 'email_id',  # Added: capital I and D
            'Email': 'email_id',
            'Current Company': 'current_org',
            'Curr Org': 'current_org',
            'Company': 'current_org',
            'Total Experience': 'total_experience',
            'Total Exp': 'total_experience',
            'Tot Exp': 'total_experience',
            'Relevant Experience': 'relevant_experience',
            'Relevant Exp': 'relevant_experience',
            'Rel Exp': 'relevant_experience',
            'Current CTC': 'current_ctc',
            'C - CTC': 'current_ctc',  # Added: "C - CTC" variant
            'Expected CTC': 'expected_ctc',
            'E - CTC': 'expected_ctc',  # Added: "E - CTC" variant
            'Notice Period': 'notice_period',
            'Current Location': 'current_location',
            'Curr Loc': 'current_location',
            'Preferred Location': 'preferred_location',
            'Exp Loc': 'preferred_location',
            'Remark': 'remarks',
            'Remarks': 'remarks',
            'Comment': 'remarks',
        }

        for key, value in mapping.items():
            if key in header:
                return value

        return None

    def _parse_line_data(self, line: str, data: Dict):
        """Parse a line for field-value pairs"""
        # Map common field names to database columns
        field_mapping = {
            'JR No': 'jr_no',
            'JR Number': 'jr_no',
            'RH ID': 'jr_no',  # Recruitment/Requisition ID
            'Req ID': 'jr_no',  # Requisition ID
            'Job ID': 'jr_no',  # Job ID
            'Date': 'date',
            'Skill': 'general_skill',
            'Candidate Name': 'name_of_candidate',
            'Name': 'name_of_candidate',
            'Contact Number': 'contact_number',
            'Contact': 'contact_number',
            'Phone': 'contact_number',
            'Email ID': 'email_id',
            'E-Mail Id': 'email_id',
            'Email': 'email_id',
            'Current Company': 'current_org',
            'Company': 'current_org',
            'Total Experience': 'total_experience',
            'Total Exp': 'total_experience',
            'Relevant Experience': 'relevant_experience',
            'Relevant Exp': 'relevant_experience',
            'Current CTC': 'current_ctc',
            'Expected CTC': 'expected_ctc',
            'Notice Period': 'notice_period',
            'Current Location': 'current_location',
            'Preferred Location': 'preferred_location',
            'Remark': 'remarks',
            'Remarks': 'remarks',
            'Comment': 'remarks',
        }

        for field_name, db_column in field_mapping.items():
            if field_name in line:
                # Extract value after the field name
                pattern = f"{field_name}[:\\s\\t]+(.*?)(?:\\n|$)"
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value and value != 'N/A':
                        data[db_column] = value

    def _parse_tabular_format(self, body: str) -> List[Dict]:
        """
        Parse data when it's in a horizontal HTML table format

        Handles HTML tables like:
        <table>
          <tr><th>SI No</th><th>RH ID</th><th>Name</th><th>Email</th>...</tr>
          <tr><td>1</td><td>RH123</td><td>John Doe</td><td>john@example.com</td>...</tr>
          <tr><td>2</td><td>RH124</td><td>Jane Smith</td><td>jane@example.com</td>...</tr>
        </table>
        """
        candidates = []

        # Check if this is HTML content
        if '<table' not in body.lower() and '<tr' not in body.lower():
            return candidates

        # Extract each table separately to avoid mixing signature tables with candidate tables
        table_pattern = r'<table[^>]*>.*?</table>'
        tables = re.findall(table_pattern, body, re.DOTALL | re.IGNORECASE)

        # Try parsing each table - return first one that has candidates
        for table_html in tables:
            table_candidates = self._parse_single_table(table_html)
            if table_candidates:
                return table_candidates

        return candidates

    def _parse_single_table(self, table_html: str) -> List[Dict]:
        """Parse a single HTML table"""
        candidates = []

        # Find all <tr>...</tr> sections in THIS table only
        tr_pattern = r'<tr[^>]*>(.*?)</tr>'
        rows = re.findall(tr_pattern, table_html, re.DOTALL | re.IGNORECASE)

        if len(rows) < 2:  # Need at least header + 1 data row
            return candidates

        # Extract headers from first row (look for <th> or <td> tags)
        headers = []
        first_row = rows[0]

        # Try <th> tags first (proper table headers)
        th_pattern = r'<th[^>]*>(.*?)</th>'
        header_cells = re.findall(th_pattern, first_row, re.DOTALL | re.IGNORECASE)

        # If no <th>, try <td> tags (some tables use <td> for headers)
        if not header_cells:
            td_pattern = r'<td[^>]*>(.*?)</td>'
            header_cells = re.findall(td_pattern, first_row, re.DOTALL | re.IGNORECASE)

        # Clean headers (remove HTML tags, trim whitespace)
        for cell in header_cells:
            # Remove any remaining HTML tags
            clean_cell = re.sub(r'<[^>]+>', '', cell).strip()
            # Remove &nbsp; and other HTML entities
            clean_cell = re.sub(r'&nbsp;', ' ', clean_cell)
            clean_cell = re.sub(r'&[a-z]+;', '', clean_cell)
            headers.append(clean_cell)

        if not headers:
            return candidates

        # Determine if first row is actually data (not header)
        # Check if first cell looks like a serial number (1, 2, 3...)
        first_cell = headers[0] if headers else ''
        first_row_is_data = re.match(r'^\d{1,2}$', first_cell)

        # Parse data rows
        start_idx = 0 if first_row_is_data else 1

        # If first row is data, we need to infer headers from field positions
        if first_row_is_data:
            # Common header sequence for candidate tables
            headers = ['SI No', 'Date', 'RH ID', 'Skill', 'Name', 'Contact Number', 'E-Mail Id',
                      'Total Exp', 'Relevant Exp', 'Current CTC', 'Expected CTC', 'Notice Period',
                      'Current Location', 'Preferred Location', 'Current Company']

        td_pattern = r'<td[^>]*>(.*?)</td>'

        for row in rows[start_idx:]:
            # Extract all <td> cells from this row
            cells = re.findall(td_pattern, row, re.DOTALL | re.IGNORECASE)

            if len(cells) < 3:  # Need at least a few fields
                continue

            # Clean cell values
            values = []
            for cell in cells:
                # Remove HTML tags
                clean_cell = re.sub(r'<[^>]+>', '', cell).strip()
                # Remove HTML entities
                clean_cell = re.sub(r'&nbsp;', ' ', clean_cell)
                clean_cell = re.sub(r'&[a-z]+;', '', clean_cell)
                # Remove extra whitespace
                clean_cell = ' '.join(clean_cell.split())
                values.append(clean_cell)

            # Map headers to values
            candidate_data = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    db_field = self._map_header_to_field(header)
                    if db_field:
                        candidate_data[db_field] = values[i]

            # Validate and add candidate
            if self._is_valid_candidate(candidate_data):
                candidates.append(candidate_data)

            # Safety limit
            if len(candidates) >= 20:
                break

        return candidates
        first_row_is_data = re.match(r'^\d{1,2}$', first_cell)

        # Parse data rows
        start_idx = 0 if first_row_is_data else 1

        # If first row is data, we need to infer headers from field positions
        if first_row_is_data:
            # Common header sequence for candidate tables
            headers = ['SI No', 'Date', 'RH ID', 'Skill', 'Name', 'Contact Number', 'E-Mail Id',
                      'Total Exp', 'Relevant Exp', 'Current CTC', 'Expected CTC', 'Notice Period',
                      'Current Location', 'Preferred Location', 'Current Company']

        td_pattern = r'<td[^>]*>(.*?)</td>'

        for row in rows[start_idx:]:
            # Extract all <td> cells from this row
            cells = re.findall(td_pattern, row, re.DOTALL | re.IGNORECASE)

            if len(cells) < 3:  # Need at least a few fields
                continue

            # Clean cell values
            values = []
            for cell in cells:
                # Remove HTML tags
                clean_cell = re.sub(r'<[^>]+>', '', cell).strip()
                # Remove HTML entities
                clean_cell = re.sub(r'&nbsp;', ' ', clean_cell)
                clean_cell = re.sub(r'&[a-z]+;', '', clean_cell)
                # Remove extra whitespace
                clean_cell = ' '.join(clean_cell.split())
                values.append(clean_cell)

            # Map headers to values
            candidate_data = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    db_field = self._map_header_to_field(header)
                    if db_field:
                        candidate_data[db_field] = values[i]

            # Validate and add candidate
            if self._is_valid_candidate(candidate_data):
                candidates.append(candidate_data)

            # Safety limit
            if len(candidates) >= 20:
                break

        return candidates

    def parse(self) -> Dict:
        """Main parse method - orchestrates all parsing"""
        self.parse_email_file()

        # Extract subject info
        company_code, skill = self.extract_subject_info()
        # Use the extracted code directly as company_name (no mapping needed)
        company_name = company_code

        # Extract sender and recipient info
        recruiter_email = self.extract_original_sender()
        client_recruiter = self.extract_client_recruiter()

        # Extract JR number from subject as fallback
        jr_from_subject = self.extract_jr_from_subject()

        # Parse candidate data
        candidates = self.parse_candidate_table()

        # Enrich each candidate with common data
        for candidate in candidates:
            if company_name and 'company_name' not in candidate:
                candidate['company_name'] = company_name

            if skill and 'general_skill' not in candidate:
                candidate['general_skill'] = skill

            if recruiter_email and 'recruiter' not in candidate:
                candidate['recruiter'] = recruiter_email

            if client_recruiter and 'client_recruiter' not in candidate:
                candidate['client_recruiter'] = client_recruiter

            # Use JR from subject as fallback if not in candidate data
            if jr_from_subject and ('jr_no' not in candidate or not candidate.get('jr_no')):
                candidate['jr_no'] = jr_from_subject

            # Do NOT set default status - leave empty (NULL)
            # Status and final_status should be empty when inserting from email

            # Store email metadata
            if recruiter_email:
                candidate['email_from'] = recruiter_email
            if client_recruiter:
                candidate['email_to'] = client_recruiter

            # Set delivery type based on email_from and email_to
            # Internal: both From and To are Volibits emails
            # External: either From or To is not Volibits
            if 'delivery_type' not in candidate:
                email_from = candidate.get('email_from', '')
                email_to = candidate.get('email_to', '')

                # Check if both are volibits emails
                is_from_volibits = '@volibits.com' in email_from.lower() if email_from else False
                is_to_volibits = '@volibits.com' in email_to.lower() if email_to else False

                if is_from_volibits and is_to_volibits:
                    candidate['delivery_type'] = 'Internal'
                else:
                    candidate['delivery_type'] = 'External'

            # Set date to today if not provided (will be overridden by trigger)
            if 'date' not in candidate or not candidate['date']:
                candidate['date'] = datetime.now().strftime('%Y-%m-%d')

            # Clean up email field (extract from mailto: format if present)
            if 'email_id' in candidate and candidate['email_id']:
                # Handle format: email@domain.com<mailto:email@domain.com>
                mailto_match = re.search(r'<mailto:([^>]+)>', candidate['email_id'])
                if mailto_match:
                    candidate['email_id'] = mailto_match.group(1)
                else:
                    # Remove any remaining mailto: artifacts
                    candidate['email_id'] = candidate['email_id'].replace('<mailto:', '').replace('>', '')

        self.parsed_data = {
            'company_code': company_code,
            'company_name': company_name,
            'skill': skill,
            'recruiter': recruiter_email,
            'client_recruiter': client_recruiter,
            'candidates': candidates
        }

        return self.parsed_data


class EmailProcessor:
    """Process emails and update database"""

    def __init__(self, db_client: PostgresClient):
        self.db_client = db_client

    def process_email_file(self, email_path: str, dry_run: bool = False) -> Dict:
        """
        Process a single email file

        Args:
            email_path: Path to .eml file
            dry_run: If True, don't actually update database

        Returns:
            Dict with processing results
        """
        print(f"\n{'='*80}")
        print(f"📧 Processing: {os.path.basename(email_path)}")
        print(f"{'='*80}\n")

        parser = EmailParser(email_path)
        data = parser.parse()

        print(f"Company: {data.get('company_name', 'N/A')}")
        print(f"Skill: {data.get('skill', 'N/A')}")
        print(f"Recruiter: {data.get('recruiter', 'N/A')}")
        print(f"Client Recruiter: {data.get('client_recruiter', 'N/A')}")
        print(f"Candidates found: {len(data.get('candidates', []))}\n")

        results = {
            'file': email_path,
            'candidates_found': len(data.get('candidates', [])),
            'inserted': 0,
            'skipped': 0,
            'errors': []
        }

        for i, candidate in enumerate(data.get('candidates', []), 1):
            print(f"Candidate {i}:")
            print(f"  Name: {candidate.get('name_of_candidate', 'N/A')}")
            print(f"  Email: {candidate.get('email_id', 'N/A')}")
            print(f"  JR No: {candidate.get('jr_no', 'N/A')}")

            if not dry_run:
                try:
                    # Check duplicate type (for display only - we still insert)
                    duplicate_type = self._check_duplicate_type(candidate)

                    # Always insert candidate (duplicates are marked, not skipped)
                    success = self._insert_candidate(candidate)
                    if success:
                        if duplicate_type:
                            print(f"  Status: ✅ INSERTED (marked as {duplicate_type})\n")
                            results['skipped'] += 1  # Count as skipped for summary
                        else:
                            print(f"  Status: ✅ INSERTED\n")
                        results['inserted'] += 1
                    else:
                        print(f"  Status: ❌ FAILED\n")
                        results['errors'].append(f"Failed to insert {candidate.get('name_of_candidate')}")
                except Exception as e:
                    print(f"  Status: ❌ ERROR: {e}\n")
                    results['errors'].append(str(e))
            else:
                # Dry run - check if it would be a duplicate
                duplicate_type = self._check_duplicate_type(candidate)
                if duplicate_type:
                    print(f"  Status: 🔍 DRY RUN (would insert as {duplicate_type})\n")
                else:
                    print(f"  Status: 🔍 DRY RUN (would insert)\n")

        return results

    def _check_duplicate_type(self, candidate: Dict) -> str:
        """
        Check what type of duplicate this candidate is

        Returns:
        - "duplicate" if both email + contact number exist
        - "duplicate email" if only email exists
        - "duplicate cell" if only contact number exists
        - None if no duplicate found
        """
        email = candidate.get('email_id', '').strip()
        contact = candidate.get('contact_number', '').strip()

        # Check if both email and contact exist together
        if email and contact:
            query = """
                SELECT id FROM hrvolibit
                WHERE email_id = %s AND contact_number = %s
                LIMIT 1
            """
            result = self.db_client.execute_query(query, (email, contact))
            if result and len(result) > 0:
                return "duplicate"

        # Check if only email exists
        if email:
            query = """
                SELECT id FROM hrvolibit
                WHERE email_id = %s
                LIMIT 1
            """
            result = self.db_client.execute_query(query, (email,))
            if result and len(result) > 0:
                return "duplicate email"

        # Check if only contact number exists
        if contact:
            query = """
                SELECT id FROM hrvolibit
                WHERE contact_number = %s
                LIMIT 1
            """
            result = self.db_client.execute_query(query, (contact,))
            if result and len(result) > 0:
                return "duplicate cell"

        return None

    def _insert_candidate(self, candidate: Dict) -> bool:
        """
        Insert or update candidate into database

        Rules:
        - Search for existing record by (jr_no + name) or (jr_no + email)
        - If found: UPDATE with new non-NULL fields
        - If not found: INSERT as new record
        - Trim all text fields
        """
        # Try to find existing record
        existing_id = self._find_existing_candidate(candidate)

        if existing_id:
            # Update existing record
            return self._update_candidate(existing_id, candidate)
        else:
            # Insert new record
            return self._insert_new_candidate(candidate)

    def _find_existing_candidate(self, candidate: Dict) -> Optional[int]:
        """
        Find existing candidate record by matching jr_no + (name or email)
        Returns the record ID if found, None otherwise
        """
        jr_no = candidate.get('jr_no')
        name = candidate.get('name_of_candidate')
        email = candidate.get('email_id')

        if not jr_no:
            return None

        # Try to match by jr_no + email (most reliable)
        if email:
            query = """
                SELECT id FROM hrvolibit
                WHERE jr_no = %s AND email_id = %s
                LIMIT 1
            """
            results = self.db_client.execute_query(query, (jr_no, email))
            if results:
                return results[0][0]

        # Fallback: match by jr_no + name (less reliable due to typos/variations)
        if name:
            query = """
                SELECT id FROM hrvolibit
                WHERE jr_no = %s AND name_of_candidate = %s
                LIMIT 1
            """
            results = self.db_client.execute_query(query, (jr_no, name))
            if results:
                return results[0][0]

        return None

    def _update_candidate(self, record_id: int, candidate: Dict) -> bool:
        """
        Update existing candidate record with new non-NULL fields
        Only updates fields that are currently NULL in the database
        """
        # Prepare update query - only update NULL fields with new values
        update_fields = []
        values = []

        allowed_fields = {
            'name_of_candidate', 'email_id', 'contact_number', 'jr_no', 'date',
            'general_skill', 'company_name', 'client_recruiter', 'recruiter',
            'total_experience', 'relevant_experience', 'current_ctc', 'expected_ctc',
            'notice_period', 'current_location', 'preferred_location', 'current_org',
            'status', 'final_status', 'remarks', 'delivery_type',
            'email_from', 'email_to', 'attachment', 'record_status'
        }

        # Process date field
        if 'date' in candidate and candidate['date']:
            candidate['date'] = self._normalize_date(candidate['date'])

        # Build UPDATE SET clause - only for non-null new values
        for field, value in candidate.items():
            if field in allowed_fields and value:
                trimmed_value = value.strip() if isinstance(value, str) else value
                if trimmed_value:
                    # Update field if current value is NULL
                    update_fields.append(f"{field} = COALESCE({field}, %s)")
                    values.append(trimmed_value)

        if not update_fields:
            return True  # Nothing to update

        # Add modified audit fields
        modified_by_value = candidate.get('recruiter', 'email_parser')
        update_fields.append("modified_by = %s")
        update_fields.append("modified_date = %s")
        values.extend([modified_by_value, datetime.now()])

        # Add WHERE clause
        values.append(record_id)

        query = f"""
            UPDATE hrvolibit
            SET {', '.join(update_fields)}
            WHERE id = %s
        """

        try:
            affected = self.db_client.execute_update(query, tuple(values))
            return affected > 0
        except Exception as e:
            print(f"    Error updating: {e}")
            return False

    def _insert_new_candidate(self, candidate: Dict) -> bool:
        """
        Insert new candidate record
        """
        # Check for duplicate type BEFORE insertion
        duplicate_type = self._check_duplicate_type(candidate)
        if duplicate_type:
            candidate['is_duplicate'] = duplicate_type

        # Prepare insert query
        fields = []
        values = []
        placeholders = []

        # Field mapping - all columns from hrvolibit table
        allowed_fields = {
            'name_of_candidate', 'email_id', 'contact_number', 'jr_no', 'date',
            'general_skill', 'company_name', 'client_recruiter', 'recruiter',
            'total_experience', 'relevant_experience', 'current_ctc', 'expected_ctc',
            'notice_period', 'current_location', 'preferred_location', 'current_org',
            'status', 'final_status', 'remarks', 'delivery_type',
            'email_from', 'email_to', 'attachment', 'record_status', 'is_duplicate'
        }

        # Process date field specially (convert various formats to YYYY-MM-DD)
        if 'date' in candidate and candidate['date']:
            candidate['date'] = self._normalize_date(candidate['date'])

        # Trim all text values and add to insert
        for field, value in candidate.items():
            if field in allowed_fields and value:
                # Trim text values (remove leading/trailing spaces)
                trimmed_value = value.strip() if isinstance(value, str) else value
                if trimmed_value:  # Only add if not empty after trimming
                    fields.append(field)
                    values.append(trimmed_value)
                    placeholders.append('%s')

        # Add audit fields (created_by and created_date)
        # Use recruiter email as created_by (email sender)
        # Note: created_date trigger will also set 'date' column if not provided
        created_by_value = candidate.get('recruiter', 'email_parser')  # Use sender email
        fields.extend(['created_by', 'created_date'])
        values.extend([created_by_value, datetime.now()])
        placeholders.extend(['%s', '%s'])

        # Add modified fields
        # Use recruiter email as modified_by (email sender)
        modified_by_value = candidate.get('recruiter', 'email_parser')  # Use sender email
        fields.extend(['modified_by', 'modified_date'])
        values.extend([modified_by_value, datetime.now()])
        placeholders.extend(['%s', '%s'])

        # Simple INSERT for new records
        query = f"""
            INSERT INTO hrvolibit ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
        """

        try:
            affected = self.db_client.execute_update(query, tuple(values))
            return affected > 0
        except Exception as e:
            print(f"    Error: {e}")
            return False

    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize various date formats to YYYY-MM-DD

        Handles:
        - "11-Mar-26" → "2026-03-11"
        - "11-3-2026" → "2026-03-11"
        - "2026-03-11" → "2026-03-11"
        """
        try:
            # Try parsing common formats
            formats = [
                '%d-%b-%y',  # 11-Mar-26
                '%d-%m-%Y',  # 11-03-2026
                '%Y-%m-%d',  # 2026-03-11
                '%d/%m/%Y',  # 11/03/2026
                '%m/%d/%Y',  # 03/11/2026
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            # If all parsing fails, return as-is
            return date_str
        except:
            return date_str

    def process_folder(self, folder_path: str, dry_run: bool = False):
        """Process all emails in a folder"""
        email_files = list(Path(folder_path).glob('*.eml'))

        print(f"\n{'='*80}")
        print(f"📁 Processing folder: {folder_path}")
        print(f"📧 Found {len(email_files)} email file(s)")
        print(f"{'='*80}\n")

        total_results = {
            'files_processed': 0,
            'total_candidates': 0,
            'total_inserted': 0,
            'total_skipped': 0,
            'total_errors': 0
        }

        for email_file in email_files:
            try:
                results = self.process_email_file(str(email_file), dry_run)
                total_results['files_processed'] += 1
                total_results['total_candidates'] += results['candidates_found']
                total_results['total_inserted'] += results['inserted']
                total_results['total_skipped'] += results['skipped']
                total_results['total_errors'] += len(results['errors'])
            except Exception as e:
                print(f"❌ Error processing {email_file}: {e}\n")
                total_results['total_errors'] += 1

        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 PROCESSING SUMMARY")
        print(f"{'='*80}")
        print(f"Files processed: {total_results['files_processed']}")
        print(f"Total candidates found: {total_results['total_candidates']}")
        print(f"Inserted: {total_results['total_inserted']}")
        print(f"Skipped (duplicates): {total_results['total_skipped']}")
        print(f"Errors: {total_results['total_errors']}")
        print(f"{'='*80}\n")


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Parse emails and update HR database')
    parser.add_argument('--folder', default='/Users/vamshipriya/Downloads/emails',
                       help='Folder containing email files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without actually updating database')

    args = parser.parse_args()

    # Connect to database
    db_config = st.secrets.get('postgres', st.secrets.get('supabase', {}))
    client = PostgresClient(
        host=db_config.get('host'),
        port=int(db_config.get('port', 5432)),
        database=db_config.get('database'),
        user=db_config.get('user'),
        password=db_config.get('password')
    )

    print("✅ Database connected\n")

    # Process emails
    processor = EmailProcessor(client)
    processor.process_folder(args.folder, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

