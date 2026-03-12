# Quick Start Guide - Email to Database Parser

## 🚀 Get Started in 3 Steps

### Step 1: Place Emails in Folder

```bash
# Default folder (already configured):
/Users/vamshipriya/Downloads/emails/
```

Save your forwarded candidate emails as `.eml` files in this folder.

### Step 2: Test with Dry Run

```bash
cd /Users/vamshipriya/supabase/hr-data-ui
python email_parser/email_to_db.py --dry-run
```

This will show you what would be inserted without actually inserting.

### Step 3: Run Actual Import

```bash
python email_parser/email_to_db.py
```

Done! Candidates are now in your database.

---

## ✅ What Gets Auto-Extracted

From **Subject Line**:
- Company (BS → BirlaSOFT, CE → OneCE, etc.)
- Job Skill/Title

From **Email Headers**:
- Recruiter (original sender)
- Client Recruiter (recipient name)

From **Email Body**:
- Candidate Name
- Email ID
- Contact Number
- JR Number
- Date
- Experience details
- CTC information
- Location preferences
- Remarks

---

## 📧 Supported Email Format

**Subject Pattern:**
```
Fw: BS: SAP Commerce Cloud(Hybris)
Fw: CE: Power BI Lead
Fw: ND: Network Security
```

**Body Pattern (Vertical Table):**
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
Amit B Jha
7405242313
amit740jha@gmail.com
...
```

---

## 🔍 Check Results

After running, check:

1. **Console Output** - Shows what was inserted/skipped
2. **Database** - Query hrvolibit table to verify
3. **Summary** - See total processed at the end

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Candidates found: 0" | Check email has table with headers (JR No, Date, etc.) |
| "Company: None" | Add company code to `COMPANY_CODES` in email_to_db.py |
| Duplicate skipped | Candidate with same email already exists (working as expected) |

---

## 🎯 Common Use Cases

### Process Weekly Email Batch

```bash
# 1. Download all candidate emails to Downloads/emails/
# 2. Run parser
python email_parser/email_to_db.py

# 3. Check summary
# 4. Archive processed emails
```

### Test New Email Format

```bash
# Put single email in folder
python email_parser/email_to_db.py --dry-run

# Review output, fix if needed, then:
python email_parser/email_to_db.py
```

### Process Different Folder

```bash
python email_parser/email_to_db.py --folder /path/to/other/emails --dry-run
```

---

## 📝 Next Steps

- See [README.md](README.md) for detailed documentation
- Customize company codes in `email_to_db.py`
- Add new field mappings as needed
- Set up automated processing (cron job, etc.)
