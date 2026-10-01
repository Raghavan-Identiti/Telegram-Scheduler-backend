# Use a base image that contains both Node.js and Python
FROM nikolaik/python-nodejs:python3.11-nodejs22

# Set the working directory
WORKDIR /app

# Install OS dependencies for Puppeteer (Chromium)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Set Puppeteer to use the installed Chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory (which includes whatsapp-service)
COPY . .

# Expose the ports
EXPOSE 8000

# Set the environment variable for Python to not buffer stdout
ENV PYTHONUNBUFFERED=1

# Start the combined backend using the Python runner script
CMD ["python", "run_backend.py"]
