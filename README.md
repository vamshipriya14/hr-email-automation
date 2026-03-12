# 📧 HR Email Automation System

Automated candidate email processing system that monitors an email inbox, extracts candidate information from structured emails, and inserts records into a PostgreSQL database.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What It Does

This system automatically:

1. **Monitors** email inbox (IMAP) for new candidate emails
2. **Parses** candidate information from email tables (vertical & horizontal formats)
3. **Extracts** multiple candidates per email
4. **Detects** duplicates (marks them, always inserts)
5. **Inserts** into PostgreSQL database with audit trail
6. **Runs** 24/7 as background service

---

## ✨ Features

- ✅ **Auto Email Monitoring** - IMAP polling with configurable intervals
- ✅ **Multi-Candidate Support** - Handles 1-N candidates per email
- ✅ **Duplicate Detection** - Email + contact number matching
- ✅ **Both Table Formats** - Vertical and horizontal layouts
- ✅ **Smart Subject Parsing** - Ignores Fw:/RE: prefixes
- ✅ **Company Code Mapping** - BS→BirlaSOFT, CE→OneCE, etc.
- ✅ **Date Normalization** - Converts various formats to YYYY-MM-DD
- ✅ **Text Trimming** - Cleans all fields before insertion
- ✅ **Delivery Type Detection** - Internal vs External
- ✅ **Audit Trail** - created_by, created_date, modified_by, modified_date
- ✅ **Background Service** - Runs as daemon/systemd service
- ✅ **Comprehensive Logging** - All actions logged

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/hr-email-automation.git
cd hr-email-automation
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Copy example config and add your credentials:

```bash
cp config/config.example.toml config/config.toml
```

Edit `config/config.toml`:

```toml
[email]
imap_server = "outlook.office365.com"
user = "your-email@company.com"
password = "your-app-password"

[database]
host = "your-db-host.com"
port = 5432
database = "hrdb"
user = "dbuser"
password = "dbpassword"

[settings]
check_interval = 300  # seconds (5 minutes)
mark_as_read = true
```

### 4. Test Connection

```bash
# Test email connection and process once
python scripts/check_emails_now.sh
```

### 5. Start Monitoring

```bash
# Start continuous monitoring
./scripts/start_monitor.sh
```

---

## 📊 Supported Email Formats

### Subject Line Patterns

The system accepts **ANY** company code in the subject - no predefined codes needed!

**Pattern:** `CODE: Skill Name`

**Examples:**
```
BS: SAP Commerce Cloud Developer
CE: Power BI Lead Consultant
ND: Network Security Engineer
XY: Java Full Stack Developer
ABC: Testing Engineer
```

**How it works:**
- Extracts any 2-4 letter code before the colon
- Uses the code **directly** as `company_name` in database
- No validation against predefined list
- Works with ANY code automatically!

**Common codes:**
- `BS` → Usually BirlaSOFT
- `CE` → Usually OneCE
- `ND` → Usually NTT Data
- `GB` → Usually GenBio
- **But any code works!** (XY, ZZ, ABC, etc.)

**Prefixes ignored:** `Fw:`, `Fwd:`, `RE:`

### Table Format (Vertical)

```
JR No
Date
Skill
Candidate Name
Contact Number
Email ID
...
33841
11-Mar-26
SAP Hybris
John Doe
9876543210
john@example.com
...
```

### Table Format (Horizontal)

```
Vendor Name    | General Skill | JR NO | Name           | Email
---------------|---------------|-------|----------------|------------------
Volibits       | Testing       | 33083 | Jane Smith     | jane@example.com
```

---

## 🗄️ Database Schema

Inserts into `hrvolibit` table:

```sql
CREATE TABLE hrvolibit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter VARCHAR(255),
    date DATE,
    jr_no VARCHAR(50),
    client_recruiter VARCHAR(255),
    general_skill VARCHAR(255),
    name_of_candidate VARCHAR(255),
    contact_number VARCHAR(50),
    email_id VARCHAR(255),
    total_experience VARCHAR(100),
    relevant_experience VARCHAR(100),
    current_ctc VARCHAR(100),
    expected_ctc VARCHAR(100),
    notice_period VARCHAR(100),
    current_org VARCHAR(255),
    current_location VARCHAR(255),
    preferred_location VARCHAR(255),
    status VARCHAR(100),
    remarks TEXT,
    delivery_type VARCHAR(50),
    company_name VARCHAR(255),
    is_duplicate VARCHAR(50),
    created_by VARCHAR(100),
    created_date TIMESTAMP,
    modified_by VARCHAR(100),
    modified_date TIMESTAMP,
    final_status VARCHAR(100)
);
```

---

## 🔧 Business Rules

### Duplicate Detection

| Condition | is_duplicate Value |
|-----------|-------------------|
| Email + Contact exist | "duplicate" |
| Only Email exists | "duplicate email" |
| Only Contact exists | "duplicate cell" |
| No match | NULL |

**Note:** System always inserts, never skips. Duplicates are marked for review.

### Field Derivation

- **recruiter**: Username before @ from sender email (e.g., `john.doe`)
- **client_recruiter**: Username before @ from recipient email
- **delivery_type**: `Internal` if both sender/receiver are @volibits.com, else `External`
- **status**: Default = "Delivered"
- **final_status**: Default = "Screen Pending"
- **created_by / modified_by**: "email_parser"
- **Text fields**: Trimmed (leading/trailing spaces removed)

---

## 🎛️ Usage

### Manual Check (One-Time)

```bash
# Check for new emails once and exit
./scripts/check_emails_now.sh
```

### Continuous Monitoring

```bash
# Run in foreground (stops when terminal closes)
./scripts/start_monitor.sh

# Run as background service (keeps running)
# See docs/DEPLOYMENT.md for systemd/launchd setup
```

### Command Line Options

```bash
# Check once
python src/email_monitor.py --once

# Custom interval (seconds)
python src/email_monitor.py --interval 60

# Specific IMAP folder
python src/email_monitor.py --folder "Candidate Emails"

# Move processed emails to folder
python src/email_monitor.py --move-to "Processed"
```

---

## 📁 Project Structure

```
hr-email-automation/
├── src/
│   ├── email_parser.py      # Email parsing logic
│   ├── email_monitor.py     # IMAP monitoring
│   └── database.py          # Database operations
├── scripts/
│   ├── start_monitor.sh     # Start continuous monitoring
│   └── check_emails_now.sh  # Manual check
├── config/
│   ├── config.example.toml  # Example configuration
│   └── config.toml          # Your config (not committed)
├── docs/
│   ├── QUICK_START.md       # Quick setup guide
│   ├── AUTOMATION_SETUP.md  # Detailed setup
│   └── DEPLOYMENT.md        # Production deployment
├── tests/
│   └── test_parser.py       # Unit tests
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 🔒 Security

- ✅ **No Hardcoded Credentials** - All secrets in config file
- ✅ **Config in .gitignore** - Credentials never committed
- ✅ **App Passwords** - Use app-specific passwords, not main password
- ✅ **Email Sanitization** - mailto: artifacts removed
- ✅ **PII Protection** - Email files not committed

---

## 📖 Documentation

- [Quick Start Guide](docs/QUICK_START.md) - 5-minute setup
- [Automation Setup](docs/AUTOMATION_SETUP.md) - Detailed configuration
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment

---

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/

# Test with sample emails
python tests/test_parser.py
```

---

## 🛠️ Troubleshooting

### Authentication Failed

- Use App Password (not regular password) for Office 365/Gmail
- Enable IMAP in email settings
- Check credentials in config.toml

### No Emails Found

- Check subject pattern (must have BS:, CE:, ND:, or GB:)
- Verify emails are unread
- Check IMAP folder name

### Database Connection Failed

- Verify database credentials
- Check network connectivity
- Ensure database user has INSERT permissions

See [docs/AUTOMATION_SETUP.md](docs/AUTOMATION_SETUP.md) for detailed troubleshooting.

---

## 📊 Monitoring & Logs

### View Logs

```bash
# Linux/Mac
tail -f ~/Library/Logs/email_monitor.log

# Or check working directory
tail -f email_monitor.log
```

### Check Service Status

```bash
# macOS
launchctl list | grep emailmonitor

# Linux
systemctl status email-monitor
```

---

## 🔄 Updates & Maintenance

### Company Codes (Dynamic)

**No configuration needed!** Company codes are extracted automatically from email subjects.

- Subject: `XY: Developer` → company_name = "XY"
- Subject: `ABC: Tester` → company_name = "ABC"
- Subject: `BS: Java` → company_name = "BS"

The system works with **ANY** code - no updates required for new companies!

### Update Field Mappings

Edit `_map_header_to_field()` method in `src/email_parser.py`.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -m 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Open Pull Request

---

## 📝 License

MIT License - See LICENSE file for details

---

## 👥 Authors

- **Volibits Team** - HR Automation System
- **Claude Sonnet 4.5** - Code generation and documentation

---

## 📞 Support

For issues or questions:
- Open an issue on GitHub
- Contact: hr-automation@volibits.com

---

## 🎯 Roadmap

- [ ] Web dashboard for monitoring
- [ ] Email templates for auto-responses
- [ ] ML-based duplicate matching
- [ ] Resume parsing integration
- [ ] Slack notifications
- [ ] Multi-language support

---

**Built with ❤️ by Volibits**
