const express = require('express');
const app = express();
const port = process.env.PORT || 3001;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ connected: true, status: 'ready', provider: 'baileys' });
});

app.get('/qr-only', (req, res) => {
  res.json({ qr: null, ready: true });
});

app.listen(port, () => {
  console.log(`WhatsApp Baileys service listening on port ${port}`);
});
