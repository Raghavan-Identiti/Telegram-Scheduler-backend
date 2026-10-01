# WhatsApp Automation Architecture & Guide

This document outlines the architecture, core code components, and operational guide for the WhatsApp automation module built into this system. This guide is designed to help you or AI assistants (like Claude) understand the current setup, replicate it, and extend it.

## 🏗️ Architecture Overview

The WhatsApp automation relies on a **microservice architecture**:
1. **Python FastAPI Backend (`run_backend.py`)**: Handles the scheduling, Google Sheets fetching, and overarching business logic.
2. **Node.js Express Microservice (`whatsapp-service/index.js`)**: A dedicated lightweight server running `whatsapp-web.js`. It runs a headless Chromium browser under the hood to automate WhatsApp Web.
3. **Internal Communication**: The Python backend sends HTTP requests (GET/POST) to the Node.js microservice on `localhost:3001` to check connection status, fetch QR codes, and trigger messages.

### Why a separate Node.js service?
WhatsApp Web automation libraries in Python are often unstable or rely on Selenium. `whatsapp-web.js` is the most robust open-source library for WhatsApp automation, but it requires Node.js. Running it as a sidecar microservice provides maximum stability while allowing the main backend to remain in Python.

---

## 🛠️ Core Components & Code

### 1. The Node.js WhatsApp Microservice (`whatsapp-service/index.js`)
This is the heart of the WhatsApp automation. It exposes a REST API for the Python backend.

**Key API Endpoints:**
* `GET /health` - Returns `{ status: 'ready' }` if WhatsApp is linked and authenticated.
* `GET /qr` - Returns the latest login QR code as a base64 string.
* `POST /send` - Accepts JSON `{ "target": "jid", "message": "text", "media": "base64" }` to send a message.

**Crucial Configuration Fixes Applied:**
To ensure stability against recent WhatsApp Web updates, the `Client` must be initialized with `type: 'local'` for the `webVersionCache`. Hardcoded remote versions will crash if the repository deletes them.

```javascript
// Excerpt from index.js
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");

const client = new Client({
  authStrategy: new LocalAuth({ clientId: "telequeue-wwebjs" }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  },
  webVersionCache: {
    type: 'local', // ⚠️ CRITICAL: Must be local to prevent 404 crashes on WA Web updates
  }
});
```

### 2. The `whatsapp-web.js` Internal Patches
Recent updates to WhatsApp Web broke the sending of media to Newsletter/Channels in `whatsapp-web.js`. Two critical patches were manually applied to `whatsapp-service/node_modules/whatsapp-web.js/src/util/Injected/Utils.js`. 

*Note: If you reinstall `node_modules`, you must re-apply these patches or use a patcher like `patch-package`.*

**Patch 1: Prevent `__x_id` crash when injecting messages**
Around line 483 in `Utils.js`:
```javascript
        ...extraOptions,
    };

    delete message.__x_id; // ⚠️ ADD THIS LINE

    if (botOptions) {
```

**Patch 2: Fix `msg.avParams is not a function` error**
Around line 520 in `Utils.js`:
```javascript
    ...(isMedia
        ? {
            // ⚠️ REPLACE: mediaMetadata: msg.avParams(),
            // ⚠️ WITH THIS:
            mediaMetadata: typeof msg.avParams === 'function' ? msg.avParams() : (msg.avParams || {}),
            mediaHandle: isMedia ? mediaOptions.mediaHandle : null,
          }
        : {}),
```

### 3. The Python Integration (`app/services/whatsapp_utils.py`)
The Python backend uses `requests` to communicate with the Node.js microservice. It sends messages and media using `multipart/form-data`.

**File to Share:** `app/services/whatsapp_utils.py`

```python
import requests
import os
import mimetypes

WHATSAPP_SERVICE_URL = "http://localhost:3001"

def send_via_baileys(post: dict) -> str | None:
    target = post.get("recipient_phone") # e.g., "120363400693925981@newsletter"
    
    url = f"{WHATSAPP_SERVICE_URL}/send"
    data = {
        "target": target,
        "message": post.get("message", "").strip()
    }
    
    image_path = post.get("image_path")
    if image_path and os.path.exists(image_path):
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or 'image/jpeg'
                
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, mime_type)}
            resp = requests.post(url, data=data, files=files, timeout=60)
    else:
        resp = requests.post(url, data=data, timeout=30)
        
    if not resp.ok:
        raise Exception(f"Send failed ({resp.status_code}): {resp.text}")
        
    return resp.json().get('messageId')
```

---

## 🚀 How to Run and Authenticate

### Step 1: Start the Backend Services
The `run_backend.py` script automatically manages both the Python server and the Node.js microservice as subprocesses.
```bash
cd Telegram-Scheduler-backend
python3 run_backend.py
```
*This will start Python on `localhost:8000` and Node.js on `localhost:3001`.*

### Step 2: Start the Frontend
In a new terminal window:
```bash
cd Telegram-Scheduler_frontend
npm run dev
```
*This will start the React UI on `localhost:3000`.*

### Step 3: Authenticate WhatsApp
1. Open the frontend (`http://localhost:3000`) and navigate to the WhatsApp section.
2. The UI will request the QR code from the Python backend, which proxies it from the Node.js microservice.
3. Open the WhatsApp app on your phone -> Settings -> Linked Devices -> Link a Device.
4. Scan the QR code displayed on the screen.
5. The session is saved persistently in `whatsapp-service/.wwebjs_auth/session-telequeue-wwebjs`. You will not need to scan again unless you manually log out from your phone.

### Troubleshooting: "Browser is already running" or 500 Errors
If the backend crashes or WhatsApp refuses to link, the browser session or lockfiles may be corrupted. You can reset it completely by running:
```bash
cd Telegram-Scheduler-backend
pkill -f "python3 run_backend.py"
pkill -f node
pkill -f chrome
rm -rf whatsapp-service/.wwebjs_auth
```
Then restart `python3 run_backend.py` and scan a fresh QR code.
