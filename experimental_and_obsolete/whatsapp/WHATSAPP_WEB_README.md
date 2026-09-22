# QPilot WhatsApp Web Automation

This is a separate, unofficial WhatsApp Web sender. It does not require Meta Business verification, but it depends on WhatsApp Web staying logged in and working.

It does not change the existing Telegram scheduler files.

## Install

From `E:\TeleQueue\backend`:

```powershell
C:\Python313\python.exe -m pip install -r whatsapp_web_requirements.txt
C:\Python313\python.exe -m playwright install chromium
```

## Run

```powershell
cd E:\TeleQueue\backend
C:\Python313\python.exe -m uvicorn whatsapp_web_service:app --host 127.0.0.1 --port 8010
```

Open:

```text
http://127.0.0.1:8010/health
```

The first run opens WhatsApp Web. Scan the QR code. The session is saved in:

```text
E:\TeleQueue\backend\whatsapp_web_session
```

Usually you do not need to scan QR again unless WhatsApp logs out.

## Send Immediately

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/send-now `
  -ContentType application/json `
  -Body '{"target":"Marketing Group","message":"Test from QPilot"}'
```

With image:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/send-now `
  -ContentType application/json `
  -Body '{"target":"Marketing Group","message":"Caption here","image_path":"E:\\TeleQueue\\backend\\uploads\\post1.jpg"}'
```

## Schedule

Use local ISO time or timezone ISO time:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/schedule `
  -ContentType application/json `
  -Body '{"target":"Marketing Group","message":"Scheduled post","run_at":"2026-05-25T20:30:00+05:30"}'
```

List jobs:

```text
http://127.0.0.1:8010/jobs
```

## Environment Options

Optional values:

```env
WHATSAPP_WEB_HEADLESS=false
WHATSAPP_WEB_SESSION_DIR=whatsapp_web_session
WHATSAPP_WEB_POLL_SECONDS=15
WHATSAPP_WEB_MAX_ATTEMPTS=5
```

Keep `WHATSAPP_WEB_HEADLESS=false` for setup, because you need to see the QR code.

## Important Notes

- This is unofficial automation.
- Use a dedicated WhatsApp Business number, not a personal account.
- Avoid bulk/spam behavior.
- WhatsApp can log out the session.
- WhatsApp Web UI changes may require selector fixes.
- For production reliability, official WhatsApp Cloud API or a BSP is still safer.
