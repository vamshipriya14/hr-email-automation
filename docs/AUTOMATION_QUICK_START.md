# 🚀 Email Automation Quick Start

Get automatic candidate processing up and running in 5 minutes!

---

## ⚡ Quick Setup (3 Steps)

### Step 1: Add Email Password

Edit `.streamlit/secrets.toml` and add:

```toml
[email]
imap_server = "outlook.office365.com"
user = "rec_team@volibits.com"
password = "YOUR-PASSWORD-HERE"
```

**Get App Password for Office 365:**
1. Go to https://account.microsoft.com/security
2. Click "App passwords"
3. Create new password for "Mail"
4. Copy and paste into secrets.toml

---

### Step 2: Test It

```bash
cd /Users/vamshipriya/supabase/hr-data-ui

# Test connection and process emails once
./email_parser/check_emails_now.sh
```

You should see:
```
✅ Connected to rec_team@volibits.com
📬 Found X new email(s)
📧 Email: BS: SAP Developer...
   🔄 Processing...
   ✅ Processed: 1 candidate(s)
```

---

### Step 3: Start Automatic Monitoring

**Option A: Run in Terminal (Easy, but stops when you close terminal)**

```bash
./email_parser/start_monitor.sh
```

**Option B: Run as Background Service (Recommended - runs forever)**

```bash
# Create the service
cat > ~/Library/LaunchAgents/com.volibits.emailmonitor.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.volibits.emailmonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/vamshipriya/supabase/hr-data-ui/email_parser/email_monitor.py</string>
        <string>--interval</string>
        <string>300</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/vamshipriya/Library/Logs/email_monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/vamshipriya/Library/Logs/email_monitor_error.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/vamshipriya/supabase/hr-data-ui</string>
</dict>
</plist>
EOF

# Start the service
launchctl load ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
launchctl start com.volibits.emailmonitor
```

**Check if it's running:**

```bash
launchctl list | grep emailmonitor
```

**View logs:**

```bash
tail -f ~/Library/Logs/email_monitor.log
```

---

## ✅ What It Does

When a new email arrives at **rec_team@volibits.com** with subject like:

- `BS: SAP Developer`
- `Fw: CE: Power BI Lead`
- `RE: ND: Network Security`

The system **automatically**:

1. ✅ Downloads the email
2. ✅ Extracts all candidates
3. ✅ Inserts into database (marks duplicates)
4. ✅ Marks email as read
5. ✅ Logs the results

**No manual intervention needed!**

---

## 🎛️ Control Panel

### Check Status

```bash
# Is the service running?
launchctl list | grep emailmonitor

# View recent logs
tail -20 ~/Library/Logs/email_monitor.log

# Check for errors
tail -20 ~/Library/Logs/email_monitor_error.log
```

### Stop Monitoring

```bash
launchctl stop com.volibits.emailmonitor
launchctl unload ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
```

### Restart Monitoring

```bash
launchctl load ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
launchctl start com.volibits.emailmonitor
```

### Check Emails Manually

```bash
./email_parser/check_emails_now.sh
```

---

## 📊 Monitoring Schedule

**Default:** Checks every **5 minutes** (300 seconds)

**Change interval:**

Edit the plist file and change `<string>300</string>` to:
- `60` = 1 minute (testing)
- `180` = 3 minutes
- `300` = 5 minutes (recommended)
- `600` = 10 minutes

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
launchctl load ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
```

---

## 🔧 Troubleshooting

### "Authentication failed"

1. Check password in `.streamlit/secrets.toml`
2. Use App Password (not regular password) for Office 365
3. Enable IMAP in email settings

### "No new emails" but emails exist

1. Emails might be marked as read
2. Check subject pattern (must have BS:, CE:, ND:, or GB:)
3. Run `./email_parser/check_emails_now.sh` to debug

### Service not starting

```bash
# Check for errors
cat ~/Library/Logs/email_monitor_error.log

# Verify Python path
which python3  # Should match path in plist file

# Test manually first
python3 email_parser/email_monitor.py --once
```

---

## 📧 Test Workflow

1. **Send test email** to rec_team@volibits.com:
   - Subject: `BS: Test Candidate`
   - Body: Include candidate table format

2. **Wait 5 minutes** (or run `./email_parser/check_emails_now.sh`)

3. **Check logs:**
   ```bash
   tail -f ~/Library/Logs/email_monitor.log
   ```

4. **Verify in database:**
   - Check hrvolibit table
   - Should see new candidate inserted

---

## 🎯 Key Features

- ✅ **Always Running** - Works 24/7 in background
- ✅ **Auto-Duplicate Detection** - Marks duplicates, always inserts
- ✅ **Multi-Candidate Support** - Handles 1-N candidates per email
- ✅ **Both Table Formats** - Vertical and horizontal layouts
- ✅ **Smart Subject Parsing** - Ignores Fw:/RE: prefixes
- ✅ **Audit Trail** - created_by = "email_parser"
- ✅ **Logging** - All actions logged for review

---

## 📞 Need Help?

See [EMAIL_AUTOMATION_SETUP.md](EMAIL_AUTOMATION_SETUP.md) for detailed documentation.
