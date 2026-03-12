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

    def __init__(self, email_path: str):
        self.email_path = email_path
        self.raw_email = None
        self.parsed_data = {}

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

        # Remove "Fw:" or "Fwd:" prefix
        subject = re.sub(r'^(Fw|Fwd):\s*', '', subject, flags=re.IGNORECASE)

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

    def extract_original_sender(self) -> str:
        """
        Extract the original sender from forwarded email content
        Returns username before @ (e.g., salman.ahmed from salman.ahmed@volibits.com)

        Looks for patterns like:
        "From: Salman Ahmed <salman.ahmed@volibits.com>"
        """
        body = self.get_email_body()

        # Pattern to find original sender in forwarded email
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

                # Extract username before @ sign
                if '@' in email:
                    username = email.split('@')[0].strip()
                    return username

                return email

        return None

    def extract_client_recruiter(self) -> str:
        """
        Extract client recruiter from To: field in forwarded email
        Returns username before @ (e.g., amit.pal from amit.pal@birlasoft.com)

        Looks for:
        "To: Nisha Gupta <nisha.gupta@birlasoft.com>"
        """
        body = self.get_email_body()

        patterns = [
            r'To:\s*([^<]+)\s*<([^>]+)>',
            r'To:\s*([^\n]+@[^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                if len(match.groups()) == 2:
                    email = match.group(2).strip()  # Email address
                else:
                    email = match.group(1).strip()

                # Extract username before @ sign
                if '@' in email:
                    username = email.split('@')[0].strip()
                    return username

                return email

        return None

    def get_email_body(self) -> str:
        """Get plain text body of email"""
        if self.raw_email.is_multipart():
            for part in self.raw_email.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        return part.get_content()
                    except:
                        return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            try:
                return self.raw_email.get_content()
            except:
                return self.raw_email.get_payload(decode=True).decode('utf-8', errors='ignore')

        return ""

    def parse_candidate_table(self) -> List[Dict]:
        """
        Parse candidate data from email table

        Handles vertical column format where headers are listed vertically
        followed by values vertically:
        JR No
        Date
        Skill
        ...
        33841
        11-Mar-26
        SAP Hybris
        ...
        """
        body = self.get_email_body()
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
            'Gender': None,  # Skip gender
            'Vendor Name': None,  # Skip vendor
            'Qualification': None,  # Skip qualification
            'JR No': 'jr_no',
            'JR Number': 'jr_no',
            'JR NO': 'jr_no',
            'Date': 'date',
            'Skill': 'general_skill',
            'General Skill': 'general_skill',
            'Candidate Name': 'name_of_candidate',
            'Name of Candidate': 'name_of_candidate',
            'Name': 'name_of_candidate',
            'Contact Number': 'contact_number',
            'Contact': 'contact_number',
            'Phone': 'contact_number',
            'Email ID': 'email_id',
            'Email Id': 'email_id',
            'E-Mail Id': 'email_id',
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
            'Expected CTC': 'expected_ctc',
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
        """Parse data when it's in a clear tabular format"""
        # This is a simplified parser - you may need to enhance it
        # based on actual email formats
        candidates = []
        lines = body.split('\n')

        # Find the table headers and data
        # Implementation depends on your specific email format

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

            # Set default status
            if 'status' not in candidate:
                candidate['status'] = 'Delivered'

            if 'final_status' not in candidate:
                candidate['final_status'] = 'Screen Pending'

            # Set delivery type based on sender and receiver domains
            if 'delivery_type' not in candidate:
                # Get full email addresses to check domains
                sender_email = self.raw_email.get('From', '')
                receiver_email = self.raw_email.get('To', '')

                # Check if both are volibits emails
                is_sender_volibits = '@volibits.com' in sender_email.lower() or '@volibits' in sender_email.lower()
                is_receiver_volibits = '@volibits.com' in receiver_email.lower() or '@volibits' in receiver_email.lower()

                if is_sender_volibits and is_receiver_volibits:
                    candidate['delivery_type'] = 'Internal'
                else:
                    candidate['delivery_type'] = 'External'

            # Store email metadata
            if recruiter_email:
                candidate['email_from'] = recruiter_email
            if client_recruiter:
                candidate['email_to'] = client_recruiter

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
        Insert candidate into database (always inserts, marks duplicates)

        Rules:
        - Always insert, never skip
        - Check for duplicates and mark in is_duplicate column
        - Trim all text fields
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
        # Note: created_date trigger will also set 'date' column if not provided
        fields.extend(['created_by', 'created_date'])
        values.extend(['email_parser', datetime.now()])
        placeholders.extend(['%s', '%s'])

        # Add modified fields
        fields.extend(['modified_by', 'modified_date'])
        values.extend(['email_parser', datetime.now()])
        placeholders.extend(['%s', '%s'])

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
