#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Node dependencies for WhatsApp Service..."
cd whatsapp-service
npm install

echo "Installing OS dependencies for Puppeteer (Chromium)..."
# This automatically installs the necessary shared libraries on Render's Linux containers
npx playwright install-deps

cd ..
echo "Build complete!"
