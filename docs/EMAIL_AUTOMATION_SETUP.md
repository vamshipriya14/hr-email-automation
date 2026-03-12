# Email Automation Setup Guide

Automatically process candidate emails when they arrive at rec_team@volibits.com

---

## 📋 Prerequisites

1. Access to rec_team@volibits.com mailbox
2. IMAP enabled on the email account
3. Email password or app-specific password

---

## 🔧 Step 1: Configure Email Credentials

Add email credentials to `.streamlit/secrets.toml`:

```toml
[email]
imap_server = "outlook.office365.com"  # For Office 365/Outlook
user = "rec_team@volibits.com"
password = "your-email-password-here"
```

**Note:** For Office 365, you may need an **App Password** instead of your regular password:
- Go to Microsoft Account → Security → App passwords
- Create new app password for "Mail"
- Use that password in secrets.toml

---

## 🚀 Step 2: Test the Monitor

### Test Once (Manual Check)

```bash
cd /Users/vamshipriya/supabase/hr-data-ui
python email_parser/email_monitor.py --once
```

This will:
- Connect to rec_team@volibits.com
- Check for unread emails with subject patterns (BS:, CE:, ND:, etc.)
- Process and insert candidates into database
- Mark emails as read
- Exit

### Test Continuous Mode

```bash
python email_parser/email_monitor.py --interval 60
```

This checks every 60 seconds (useful for testing). Press Ctrl+C to stop.

---

## ⚙️ Step 3: Set Up Automatic Monitoring

### Option A: Run as Background Service (Recommended)

Create a launch daemon (macOS) or systemd service (Linux):

**For macOS:**

1. Create launch agent file:

```bash
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
```

2. Load and start the service:

```bash
launchctl load ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
launchctl start com.volibits.emailmonitor
```

3. Check if it's running:

```bash
launchctl list | grep emailmonitor
```

4. View logs:

```bash
tail -f ~/Library/Logs/email_monitor.log
```

5. Stop/Unload service:

```bash
launchctl stop com.volibits.emailmonitor
launchctl unload ~/Library/LaunchAgents/com.volibits.emailmonitor.plist
```

---

### Option B: Cron Job (Linux/Mac)

Run every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (checks every 5 minutes)
*/5 * * * * cd /Users/vamshipriya/supabase/hr-data-ui && /usr/local/bin/python3 email_parser/email_monitor.py --once >> /Users/vamshipriya/email_monitor.log 2>&1
```

---

### Option C: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. **Trigger:** On a schedule → Every 5 minutes
4. **Action:** Start a program
   - Program: `python.exe`
   - Arguments: `email_parser/email_monitor.py --once`
   - Start in: `C:\path\to\hr-data-ui`
5. Save and enable

---

## 🎛️ Configuration Options

### Command Line Options

```bash
# Check once and exit
python email_monitor.py --once

# Check every 300 seconds (5 minutes) - continuous
python email_monitor.py --interval 300

# Check specific folder
python email_monitor.py --folder "Candidate Emails"

# Move processed emails to folder
python email_monitor.py --move-to "Processed"

# Don't mark as read (keep as unread)
python email_monitor.py --no-mark-read
```

### Recommended Settings

**For Production:**
```bash
# Check every 5 minutes
python email_monitor.py --interval 300
```

**For Testing:**
```bash
# Check every 30 seconds
python email_monitor.py --interval 30
```

**For Manual Processing:**
```bash
# Check once, useful for cron jobs
python email_monitor.py --once
```

---

## 📊 How It Works

1. **Connects** to rec_team@volibits.com via IMAP
2. **Searches** for unread emails
3. **Filters** emails with subject patterns:
   - `BS: Skill Name` (BirlaSOFT)
   - `CE: Skill Name` (OneCE)
   - `ND: Skill Name` (NTT Data)
   - `GB: Skill Name` (GenBio)
   - Ignores `Fw:`, `Fwd:`, `RE:` prefixes
4. **Downloads** matching emails as .eml files
5. **Processes** candidates using email_to_db parser
6. **Inserts** into hrvolibit table (marks duplicates)
7. **Marks** email as read (optional)
8. **Moves** to processed folder (optional)

---

## 🔍 Monitoring & Logs

### View Logs (macOS LaunchAgent)

```bash
# Standard output
tail -f ~/Library/Logs/email_monitor.log

# Errors
tail -f ~/Library/Logs/email_monitor_error.log
```

### View Logs (Cron)

```bash
tail -f ~/email_monitor.log
```

### Check Service Status (macOS)

```bash
launchctl list | grep emailmonitor
```

---

## 🛠️ Troubleshooting

### Issue: "Authentication failed"

**Solutions:**
1. Check password in `.streamlit/secrets.toml`
2. For Office 365, use App Password instead of regular password
3. Enable IMAP in email settings
4. Check if 2FA is enabled (requires app password)

### Issue: "No new emails" but emails exist

**Solutions:**
1. Check if emails are marked as read
2. Verify subject pattern matches (BS:, CE:, ND:, GB:)
3. Check IMAP folder name (might be "Inbox" not "INBOX")

### Issue: "Module not found"

**Solution:**
```bash
cd /Users/vamshipriya/supabase/hr-data-ui
pip install -r requirements.txt
```

### Issue: Service not starting (macOS)

**Solution:**
```bash
# Check for errors
launchctl error com.volibits.emailmonitor

# Verify plist file
plutil -lint ~/Library/LaunchAgents/com.volibits.emailmonitor.plist

# Check Python path
which python3  # Update path in plist if different
```

---

## 🔐 Security Notes

1. **Email Password**: Never commit secrets.toml to git (already in .gitignore)
2. **App Passwords**: Use app-specific passwords, not your main email password
3. **File Permissions**: Ensure secrets.toml is readable only by you:
   ```bash
   chmod 600 .streamlit/secrets.toml
   ```

---

## 📧 Email Server Settings

### Microsoft Office 365 / Outlook.com
```toml
[email]
imap_server = "outlook.office365.com"
user = "rec_team@volibits.com"
password = "app-password-here"
```

### Gmail
```toml
[email]
imap_server = "imap.gmail.com"
user = "rec_team@volibits.com"
password = "app-password-here"  # Must use App Password with 2FA
```

### Other IMAP Servers
```toml
[email]
imap_server = "imap.your-domain.com"
user = "rec_team@volibits.com"
password = "password-here"
```

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Email credentials added to secrets.toml
- [ ] Test run successful: `python email_monitor.py --once`
- [ ] Service/cron job configured
- [ ] Logs are being written
- [ ] Test email processed correctly
- [ ] Duplicates marked correctly
- [ ] Database records created

---

## 📞 Support

If you encounter issues:

1. Check logs first
2. Test with `--once` flag manually
3. Verify email credentials
4. Check IMAP settings in email account
5. Review error messages in logs
