import express from "express";
import multer from "multer";
import fs from "fs";
import path from "path";
import pkg from "whatsapp-web.js";
const { Client, LocalAuth, MessageMedia } = pkg;
import qrcode from "qrcode";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

dotenv.config();

// Global process error handlers to stabilize the production Node service
process.on("unhandledRejection", (reason, promise) => {
  console.error("⚠️ Unhandled Rejection at:", promise, "reason:", reason);
});
process.on("uncaughtException", (error) => {
  console.error("⚠️ Uncaught Exception:", error.stack || error);
});

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
const upload = multer({ dest: "uploads/" });

let clientReady = false;
let qrString = null;

// Local cache for channel JIDs
const MAPPINGS_FILE = path.join(__dirname, "channel_mappings.json");
let channelMappings = {};
try {
  if (fs.existsSync(MAPPINGS_FILE)) {
    channelMappings = JSON.parse(fs.readFileSync(MAPPINGS_FILE, "utf8"));
    console.log("Loaded cached channel mappings:", channelMappings);
  }
} catch (e) {
  console.error("Failed to read channel mappings:", e);
}

// Use Edge as the executable for puppeteer-core
const executablePath =
  process.env.PUPPETEER_EXECUTABLE_PATH ||
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

console.log("Initializing WhatsApp Client via whatsapp-web.js...");

const client = new Client({
  authStrategy: new LocalAuth({
    clientId: process.env.WHATSAPP_CLIENT_ID || "telequeue-wwebjs",
  }),
  authTimeoutMs: 180000,
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  puppeteer: {
    executablePath: fs.existsSync(executablePath) ? executablePath : undefined,
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--single-process",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-features=site-per-process",
      "--disable-background-networking",
      "--disable-default-apps",
      "--disable-extensions",
      "--disable-sync",
      "--metrics-recording-only",
      "--mute-audio",
      "--no-default-browser-check",
      "--no-pings",
      "--memory-pressure-off",
    ],
  },
  webVersionCache: {
    type: 'local',
  }
});

client.on("qr", async (qr) => {
  console.log(
    "\n=========================================================================",
  );
  console.log("QR RECEIVED. Go to http://localhost:3001 to scan it.");
  console.log(
    "=========================================================================\n",
  );
  qrString = qr;
});

client.on("authenticated", () => {
  console.log("✅ WhatsApp Web Authenticated (session saved)!");
  qrString = null; // Clear QR immediately so the user knows it worked
});

client.on("auth_failure", (msg) => {
  console.error("❌ WhatsApp Web Authentication Failure:", msg);
});

client.on("disconnected", (reason) => {
  console.log("❌ WhatsApp Web Disconnected:", reason);
  clientReady = false;
});

client.on("ready", async () => {
  console.log("✅ WhatsApp Web connected and ready!");
  clientReady = true;
  qrString = null;

  // Build and cache JID mapping for channels dynamically on startup with an 8-second delay
  console.log("Scheduling JID cache scan in 8 seconds to allow sync...");
  setTimeout(async () => {
    try {
      console.log("Scanning chats to cache channel JID mappings...");
      const chats = await client.getChats();
      console.log(
        `Found ${chats.length} active standard chats loaded in session.`,
      );

      // Query the separate internal WhatsApp Web store dynamically
      console.log(
        "Scanning window.Store collections dynamically for newsletters...",
      );
      const newsletters = await client.pupPage.evaluate(async () => {
        try {
          if (!window.Store) return [];
          const isNewsletterJid = (id) =>
            typeof id === "string" && id.endsWith("@newsletter");
          const results = [];

          for (const key of Object.keys(window.Store)) {
            try {
              const store = window.Store[key];
              if (!store) continue;

              let models = [];
              if (Array.isArray(store.models)) {
                models = store.models;
              } else if (typeof store.toArray === "function") {
                models = store.toArray();
              } else if (Array.isArray(store)) {
                models = store;
              }

              if (models && models.length > 0) {
                const hasNewsletter = models.some((m) => {
                  const idStr =
                    typeof m.id === "object" && m.id
                      ? m.id._serialized
                      : m.id || m.jid || "";
                  return isNewsletterJid(idStr);
                });

                if (hasNewsletter) {
                  console.log(
                    `[Dynamic Scanner] Found newsletter store at key: ${key}`,
                  );
                  models.forEach((m) => {
                    const jid =
                      typeof m.id === "object" && m.id
                        ? m.id._serialized
                        : m.id || m.jid || "";
                    if (isNewsletterJid(jid)) {
                      results.push({
                        name:
                          m.name || m.subject || m.title || "Unnamed Channel",
                        jid: jid,
                      });
                    }
                  });
                }
              }
            } catch (e) {}
          }
          return results;
        } catch (err) {
          console.error("Error inside Puppeteer evaluate:", err);
        }
        return [];
      });

      console.log(
        `Found ${newsletters.length} channels in internal newsletter store.`,
      );

      let updated = false;
      newsletters.forEach((n) => {
        if (n.jid && n.jid.endsWith("@newsletter")) {
          const nameClean = n.name.toLowerCase().trim();
          console.log(`- Detected Channel: "${n.name}" -> ${n.jid}`);
          if (channelMappings[nameClean] !== n.jid) {
            channelMappings[nameClean] = n.jid;
            updated = true;
          }
          const nameWithoutAmazon = nameClean
            .replace("(amazon associates)", "")
            .trim();
          if (channelMappings[nameWithoutAmazon] !== n.jid) {
            channelMappings[nameWithoutAmazon] = n.jid;
            updated = true;
          }
        }
      });

      if (updated || !fs.existsSync(MAPPINGS_FILE)) {
        fs.writeFileSync(
          MAPPINGS_FILE,
          JSON.stringify(channelMappings, null, 2),
        );
        console.log(
          "Updated channel_mappings.json successfully:",
          channelMappings,
        );
      } else {
        console.log("Channel mappings are already fully up to date.");
      }
    } catch (e) {
      console.error("Failed to auto-cache channel JID mappings:", e);
    }
  }, 8000);
});

// Dynamic self-healing listener to capture channel JIDs instantly when any activity happens in them
client.on("message_create", async (msg) => {
  try {
    const jid = msg.to?.endsWith("@newsletter")
      ? msg.to
      : msg.from?.endsWith("@newsletter")
        ? msg.from
        : null;
    if (jid) {
      console.log(`\n==================================================`);
      console.log(`📢 [CHANNEL ACTIVITY DETECTED]`);
      console.log(`Channel JID: ${jid}`);

      const chat = await msg.getChat();
      if (chat && chat.name) {
        console.log(`Channel Name: "${chat.name}"`);
        const nameClean = chat.name.toLowerCase().trim();
        let changed = false;

        if (channelMappings[nameClean] !== jid) {
          channelMappings[nameClean] = jid;
          changed = true;
        }
        const nameWithoutAmazon = nameClean
          .replace("(amazon associates)", "")
          .trim();
        if (channelMappings[nameWithoutAmazon] !== jid) {
          channelMappings[nameWithoutAmazon] = jid;
          changed = true;
        }

        if (changed) {
          fs.writeFileSync(
            MAPPINGS_FILE,
            JSON.stringify(channelMappings, null, 2),
          );
          console.log(
            `Successfully mapped and cached "${chat.name}" -> ${jid}`,
          );
        } else {
          console.log(`Channel is already mapped in cache.`);
        }
      } else {
        // Safe fallback mapping by extracting name cleanups
        console.log("Chat name not fully resolved yet in message_create.");
      }
      console.log(`==================================================\n`);
    }
  } catch (e) {
    console.error("Error in message_create JID capture:", e);
  }
});

client.on("authenticated", () => {
  console.log("✅ WhatsApp Web authenticated!");
});

client.on("auth_failure", (msg) => {
  console.error("❌ Authentication failure", msg);
  clientReady = false;
});

client.on("disconnected", (reason) => {
  console.log("Client was logged out", reason);
  clientReady = false;
});

client.initialize().catch((err) => {
  console.error("Failed to initialize WhatsApp client:", err);
});

// QR code serving endpoint
app.get("/", async (req, res) => {
  if (clientReady) {
    return res.send(
      `<h2>WhatsApp Web is connected!</h2><p>You can close this window.</p>`,
    );
  }
  if (!qrString) {
    return res.send(
      `<h2>Starting WhatsApp Client...</h2><p>Please wait, generating QR Code...</p>
      <script>setTimeout(() => window.location.reload(), 3000);</script>`,
    );
  }
  try {
    const qrImage = await qrcode.toDataURL(qrString);
    res.send(`
        <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
            <h2>Scan this QR code with WhatsApp Linked Devices</h2>
            <img id="qr-img" src="${qrImage}" alt="QR Code" style="width: 300px; height: 300px; border: 1px solid #ccc; border-radius: 10px; padding: 10px;" />
            <p>Status: Waiting for scan...</p>
            <script>
                // Smoothly update QR code without blinking the screen
                setInterval(async () => {
                    try {
                        const response = await fetch('/qr-only');
                        const data = await response.json();
                        if (data.ready) {
                            window.location.reload();
                        } else if (data.qr) {
                            document.getElementById('qr-img').src = data.qr;
                        } else {
                            // qrString is null, meaning authenticated but syncing
                            document.getElementById('qr-img').style.display = 'none';
                            document.querySelector('p').innerHTML = '<b>Authenticated! Syncing chats... please wait.</b>';
                        }
                    } catch (e) {}
                }, 5000);
            </script>
        </div>
    `);
  } catch (err) {
    res.status(500).send("Error generating QR code");
  }
});

// New endpoint to fetch just the QR code base64
app.get("/qr-only", async (req, res) => {
    if (clientReady) {
        return res.json({ ready: true });
    }
    if (!qrString) {
        return res.json({ qr: null });
    }
    try {
        const qrImage = await qrcode.toDataURL(qrString);
        res.json({ qr: qrImage });
    } catch (e) {
        res.status(500).json({ error: "Failed" });
    }
});

app.get("/status", (req, res) => {
  if (clientReady) {
    res.json({ connected: true });
  } else {
    res.json({ connected: false });
  }
});

app.post("/logout", async (req, res) => {
  try {
    if (clientReady) {
      await client.logout();
      clientReady = false;
    }
    // Delete the local session directory forcefully if they really want to reset
    const sessionPath = path.join(
      __dirname,
      ".wwebjs_auth",
      `session-${process.env.WHATSAPP_CLIENT_ID || "telequeue-wwebjs"}`,
    );
    if (fs.existsSync(sessionPath)) {
      fs.rmSync(sessionPath, { recursive: true, force: true });
    }
    qrString = null;
    res.json({
      success: true,
      message: "Logged out. Restart the server or wait for new QR code.",
    });
    client.initialize().catch(console.error);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/list-chats", async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    const chats = await client.getChats();
    const list = chats.map((c) => ({
      name: c.name || "Unnamed",
      jid: c.id._serialized,
      isGroup: c.isGroup,
      isNewsletter: c.isNewsletter || c.id._serialized.endsWith("@newsletter"),
    }));

    // Scan internal window.Store.Newsletter as well
    const newsletters = await client.pupPage.evaluate(() => {
      try {
        if (
          window.Store &&
          window.Store.Newsletter &&
          window.Store.Newsletter.models
        ) {
          return window.Store.Newsletter.models.map((n) => ({
            name: n.name || n.subject || "Unnamed Channel",
            jid: n.id || n.id._serialized || n.serializeId || "",
            isNewsletter: true,
          }));
        }
      } catch (err) {}
      return [];
    });

    res.json({
      standardChatsCount: list.length,
      newsletterStoreCount: newsletters.length,
      chats: [...list, ...newsletters],
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send", upload.single("image"), async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }

  try {
    const { target, target_name, message } = req.body || {};

    if (!target) {
      return res.status(400).json({ error: "Target is required" });
    }

    let chatToSend = null;

    // 1. Check cached channel mappings first (super fast and robust)
    if (target_name) {
      const nameClean = target_name.toLowerCase().trim();
      const nameWithoutAmazon = nameClean
        .replace("(amazon associates)", "")
        .trim();
      const mappedJid =
        channelMappings[nameClean] || channelMappings[nameWithoutAmazon];
      if (mappedJid) {
        console.log(
          `Using cached JID mapping for channel ${target_name}: ${mappedJid}`,
        );
        chatToSend = { id: { _serialized: mappedJid } };
      }
    }

    // Check if it's a Channel Invite Link or Group Link
    const channelMatch = target.match(/(?:channel\/|)([A-Za-z0-9]{15,25})/);

    // 3. DYNAMIC ON-THE-FLY RESOLUTION via WWebJS.getChannelMetadata (holy grail!)
    if (!chatToSend && channelMatch) {
      const inviteCode = channelMatch[1];
      console.log(
        `Attempting to dynamically resolve Channel JID from invite code: ${inviteCode}`,
      );
      try {
        const metadata = await client.pupPage.evaluate(async (code) => {
          // window.WWebJS.getChannelMetadata is currently broken due to getRoleByIdentifier missing.
          // We call the internal WhatsApp Web API directly!
          const response = await window
            .require("WAWebNewsletterMetadataQueryJob")
            .queryNewsletterMetadataByInviteCode(code, "GUEST");
          return {
            id: response.idJid,
            title: response.newsletterNameMetadataMixin?.nameElementValue,
          };
        }, inviteCode);

        if (metadata && metadata.id) {
          console.log(
            `Successfully resolved Channel JID: "${metadata.title || "Unnamed"}" -> ${metadata.id}`,
          );
          chatToSend = { id: { _serialized: metadata.id } };

          // Cache it for subsequent requests so we don't have to resolve it again
          let updated = false;
          if (target_name) {
            const nameClean = target_name.toLowerCase().trim();
            if (channelMappings[nameClean] !== metadata.id) {
              channelMappings[nameClean] = metadata.id;
              updated = true;
            }
            const nameWithoutAmazon = nameClean
              .replace("(amazon associates)", "")
              .trim();
            if (channelMappings[nameWithoutAmazon] !== metadata.id) {
              channelMappings[nameWithoutAmazon] = metadata.id;
              updated = true;
            }
          }
          if (metadata.title) {
            const serverNameClean = metadata.title.toLowerCase().trim();
            if (channelMappings[serverNameClean] !== metadata.id) {
              channelMappings[serverNameClean] = metadata.id;
              updated = true;
            }
            const serverNameWithoutAmazon = serverNameClean
              .replace("(amazon associates)", "")
              .trim();
            if (channelMappings[serverNameWithoutAmazon] !== metadata.id) {
              channelMappings[serverNameWithoutAmazon] = metadata.id;
              updated = true;
            }
          }

          if (updated) {
            fs.writeFileSync(
              MAPPINGS_FILE,
              JSON.stringify(channelMappings, null, 2),
            );
            console.log("Cached new channel mapping dynamically!");
          }
        }
      } catch (err) {
        console.error(
          "Failed to dynamically resolve channel invite metadata:",
          err.message || err,
        );
      }
    }

    let chats = [];
    if (!chatToSend) {
      try {
        chats = await client.getChats();
      } catch (e) {
        console.warn("getChats() failed, falling back to mapping cache", e);
      }
    }

    if (!chatToSend && (channelMatch || target_name)) {
      // First, try to match by name (most reliable for channels)
      if (target_name) {
        const nameClean = target_name
          .replace("(Amazon Associates)", "")
          .trim()
          .toLowerCase();
        chatToSend = chats.find(
          (c) =>
            c.name &&
            (c.name.toLowerCase() === nameClean ||
              c.name.toLowerCase().includes(nameClean)),
        );
      }

      // If not found by name, try looking for the invite link in messages
      if (!chatToSend && channelMatch) {
        console.log(
          "Could not find channel by name, looking for invite link in chats...",
        );
        chatToSend = chats.find((c) => {
          return c.description?.includes(channelMatch[1]) || false;
        });
      }
    }

    // Basic name resolution logic for Groups if it wasn't a channel
    if (!chatToSend && !target.includes("@")) {
      chatToSend = chats.find(
        (g) => g.name === target || g.name === target_name,
      );
    }

    let finalJid = chatToSend ? chatToSend.id._serialized : target;

    // Fallback to assuming it's a phone number ONLY if it is not a channel URL
    if (!chatToSend) {
      if (target.includes("http") || target.includes("channel")) {
        console.error(
          `Could not resolve WhatsApp JID for channel URL: ${target}`,
        );
        return res.status(404).json({
          error: `Could not resolve WhatsApp Channel JID for name '${target_name || ""}'. Make sure the channel exists in your chat list on your phone and restart the Node server to let it re-scan.`,
        });
      }
      if (!finalJid.includes("@")) {
        finalJid = target.replace(/[^0-9]/g, "") + "@c.us";
      }
    }

    if (!finalJid || finalJid === "@c.us" || finalJid.trim() === "") {
      console.error(`Invalid WhatsApp target: ${target}`);
      return res.status(400).json({
        error:
          "Invalid WhatsApp target or destination. Please configure a valid phone number, group name, or channel invite link.",
      });
    }

    console.log(`Sending message to ${finalJid}`);

    let sentMsg;
    if (req.file) {
      console.log(
        `Sending media: ${req.file.originalname} (${req.file.mimetype}) - ${req.file.size} bytes`,
      );
      const fileData = fs.readFileSync(req.file.path).toString("base64");
      const media = new MessageMedia(
        req.file.mimetype,
        fileData,
        req.file.originalname,
        req.file.size,
      );

      sentMsg = await client.sendMessage(finalJid, media, {
        caption: message,
      });

      // cleanup uploaded file
      fs.unlink(req.file.path, (err) => {
        if (err) console.error("Failed to delete temp file", err);
      });
    } else {
      sentMsg = await client.sendMessage(finalJid, message);
    }

    if (sentMsg) {
      console.log(
        `Message successfully sent with ID: ${sentMsg.id._serialized}`,
      );
      res.json({
        success: true,
        messageId: sentMsg.id._serialized,
        target: finalJid,
      });
    } else {
      res
        .status(500)
        .json({ error: "Failed to send message: client returned undefined" });
    }
  } catch (error) {
    console.error("Send error:", error.stack || error);
    res
      .status(500)
      .json({ error: error.message || error.toString(), stack: error.stack });
  }
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(
    `🚀 whatsapp-web.js microservice running on http://localhost:${PORT}`,
  );
});
