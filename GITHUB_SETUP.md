# 🚀 GitHub Setup Guide

Quick guide to push this repository to GitHub.

---

## ⚡ Quick Setup (1 Command)

I've created an automated script that will:
1. Initialize git repository
2. Create GitHub repository via API
3. Push all code to GitHub

### Run This Command:

```bash
cd /Users/vamshipriya/hr-email-automation

./scripts/setup_github.sh "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"
```

**That's it!** The script will create the repo and push everything.

---

## 🔐 Manual Setup (If You Prefer)

### Step 1: Initialize Git

```bash
cd /Users/vamshipriya/hr-email-automation

git init
git add .
git commit -m "Initial commit: HR Email Automation System

- Email parser with multi-candidate support
- IMAP monitoring for automatic processing
- Duplicate detection
- Background service support
- Complete documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Step 2: Create GitHub Repository

Go to https://github.com/new and create a new repository named `hr-email-automation`

### Step 3: Push to GitHub

```bash
# Add remote (replace YOUR-USERNAME)
git remote add origin https://github.com/YOUR-USERNAME/hr-email-automation.git

# Push
git branch -M main
git push -u origin main
```

**When prompted for password, use your GitHub token:**
```
Username: your-github-username
Password: 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
```

---

## ✅ Verify

After pushing, check:

- [ ] Repository created on GitHub
- [ ] All files visible (src/, docs/, scripts/, etc.)
- [ ] README.md displays correctly
- [ ] `.gitignore` working (no config.toml or *.eml files)

---

## 🔒 Security Notes

**IMPORTANT:**

1. ✅ **config.toml is in .gitignore** - Your passwords are safe
2. ✅ **Only example config committed** - No real credentials
3. ✅ **Token only used once** - For this initial push
4. ⚠️ **Token has expiry** - Will need new one for future updates

### For Future Updates:

```bash
# Add changes
git add .
git commit -m "Update: description of changes"

# Push (will ask for token again)
git push
```

Or set up SSH keys for password-free pushing:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh

---

## 🎯 What Gets Committed

✅ **Safe to commit:**
- All `.py` source files
- Documentation (`.md` files)
- Shell scripts (`.sh` files)
- `requirements.txt`
- `.gitignore`
- `config.example.toml`

❌ **Never committed (in .gitignore):**
- `config/config.toml` (contains passwords!)
- `*.eml` files (candidate emails)
- `*.log` files
- `processed/` folder

---

## 📞 Help

If the automated script fails, use the manual method above or check:

- Token is valid and not expired
- You have permission to create repos
- Network connection is working

