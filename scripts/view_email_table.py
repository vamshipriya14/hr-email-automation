#!/usr/bin/env python3
"""
Test script to view raw table content from emails
Usage: python scripts/view_email_table.py <path_to_eml_file>
"""
import sys
import os
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email_parser import EmailParser


def display_raw_table(body: str):
    """Display the raw table extracted from email body"""
    print("\n" + "=" * 80)
    print("RAW TABLE CONTENT")
    print("=" * 80 + "\n")

    # Check if this is HTML content with table
    if '<table' in body.lower():
        # Extract HTML table
        table_pattern = r'<table[^>]*>.*?</table>'
        tables = re.findall(table_pattern, body, re.DOTALL | re.IGNORECASE)

        if tables:
            print("📋 HTML TABLE FORMAT")
            print("-" * 80)
            for i, table in enumerate(tables, 1):
                print(f"\nTable {i}:")
                print(table[:2000])  # Show first 2000 chars
                if len(table) > 2000:
                    print(f"\n... (truncated, total length: {len(table)} chars)")
            print()
        else:
            print("❌ No HTML table found\n")

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

        print("\n📋 TEXT TABLE FORMAT")
        print("-" * 80)
        for line in lines[table_start:table_end]:
            if line.strip():
                print(line)
        print()
    else:
        print("\n❌ No text-based table found\n")

    print("=" * 80 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/view_email_table.py <path_to_eml_file>")
        print("\nExample:")
        print("  python scripts/view_email_table.py data/emails/sample.eml")
        return 1

    email_path = sys.argv[1]

    if not os.path.exists(email_path):
        print(f"❌ File not found: {email_path}")
        return 1

    print(f"\n📧 Processing: {email_path}")

    # Parse email
    parser = EmailParser(email_path)
    parser.parse_email_file()

    # Get email body
    body = parser.get_email_body()

    # Display raw table
    display_raw_table(body)

    # Also show parsed candidates for comparison
    print("\n" + "=" * 80)
    print("PARSED CANDIDATES")
    print("=" * 80 + "\n")

    candidates = parser.parse_candidate_table()
    if candidates:
        print(f"✅ Found {len(candidates)} candidate(s)\n")
        for i, candidate in enumerate(candidates, 1):
            print(f"Candidate {i}:")
            print(f"  Name: {candidate.get('name_of_candidate', 'N/A')}")
            print(f"  Email: {candidate.get('email_id', 'N/A')}")
            print(f"  Contact: {candidate.get('contact_number', 'N/A')}")
            print(f"  JR No: {candidate.get('jr_no', 'N/A')}")
            print(f"  Skill: {candidate.get('general_skill', 'N/A')}")
            print()
    else:
        print("❌ No candidates parsed\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())