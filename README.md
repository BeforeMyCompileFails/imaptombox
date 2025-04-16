# IMAP to MBOX Converter

**Download and archive your entire IMAP mailbox with ease.**  
This robust Python tool connects to your IMAP email account, downloads all messages (even from 100GB+ mailboxes), and optionally converts them into the standard `mbox` format for backup or migration purposes.

---

## 📦 Features

- ✅ **Download emails from any IMAP server** (e.g., Gmail, Outlook, self-hosted)
- 📂 **Select specific folders**, or download all folders including custom ones
- 🧠 **Smart metadata tracking** to avoid re-downloading emails
- ⚡ **Batch processing** for optimal performance on large mailboxes
- 🔐 **Secure password prompt** using `getpass`
- 🔄 **MBOX conversion** from downloaded `.eml` files
- 🧪 **Debug mode** for verbose logging
- 🧰 CLI with many useful options for full control

---

## 🚀 Quick Installation

Make sure you have **Python 3.6+** installed.

```bash
git clone https://github.com/BeforeMyCompileFails/imaptombox.git
cd imaptombox
pip install -r requirements.txt
```

> All other dependencies are part of the Python standard library.

---

## 🛠 Usage

### Download and convert in one step:
```bash
python3 imaptombox.py --host imap.example.com --username user@example.com --convert
```

### Download only:
```bash
python3 imaptombox.py --host imap.example.com --username user@example.com
```

### Convert previously downloaded emails to mbox:
```bash
python3 imaptombox.py --convert --skip-download --output-dir emails/
```

## 🔧 CLI Options

| Option              | Description                                 |
|---------------------|---------------------------------------------|
| `--host`            | IMAP server hostname (required)             |
| `--port`            | IMAP port (default: 993)                    |
| `--username`        | IMAP account username (required)            |
| `--no-ssl`          | Disable SSL (not recommended)               |
| `--output-dir`      | Where to save downloaded emails             |
| `--folders`         | Download from specific folders              |
| `--inbox-only`      | Download only from INBOX                    |
| `--max-emails`      | Limit emails per folder                     |
| `--download-all`    | Re-download all emails                      |
| `--start-message`   | Message index to start from                 |
| `--batch-size`      | Emails per batch (default: 1000)            |
| `--convert`         | Convert `.eml` files to `.mbox`             |
| `--convert-folder`  | Only convert a specific folder              |
| `--mbox-file`       | Set output `.mbox` filename                 |
| `--skip-download`   | Only run the converter                      |
| `--debug`           | Enable debug logging                        |

---

## 📁 Output Structure

```
emails/
├── INBOX/
│   ├── 12345_Hello_World.eml
│   └── ...
├── Sent/
│   ├── 12346_Sent_Message.eml
│   └── ...
├── metadata.json
└── your_backup.mbox
```

---

## 📌 Requirements

Dependencies are managed via `requirements.txt`:

```txt
email-validator>=1.1.3
python-dateutil>=2.8.2
tqdm>=4.62.3
```

Install with:

```bash
pip install -r requirements.txt
```

---

## ✍️ Author

**Denis (BeforeMyCompileFails)**  
🗓️ 2025
