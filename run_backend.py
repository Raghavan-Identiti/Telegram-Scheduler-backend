import subprocess
import sys
import threading
import os
import signal

def stream_output(pipe, prefix, color_code):
    for line in iter(pipe.readline, b''):
        try:
            line_str = line.decode('utf-8').rstrip()
            print(f"\033[{color_code}m[{prefix}]\033[0m {line_str}", flush=True)
        except Exception:
            pass

def main():
    # Enable ANSI escape sequences on Windows
    os.system("")
    print("\033[92mStarting combined backend services...\033[0m")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = base_dir
    whatsapp_dir = os.path.join(base_dir, "whatsapp-service")
    
    # Set UTF-8 encoding for the Python subprocess so it doesn't crash on emojis in Windows
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    port = os.environ.get("PORT", "8000")
    # Start Python Backend (FastAPI)
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )
    
    # Start Node.js WhatsApp Service directly using node (better for graceful shutdown)
    whatsapp_process = subprocess.Popen(
        ["node", "index.js"],
        cwd=whatsapp_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    # Threads to stream output (34 = blue for API, 35 = magenta for WhatsApp)
    t1 = threading.Thread(target=stream_output, args=(backend_process.stdout, "FASTAPI", "34"))
    t2 = threading.Thread(target=stream_output, args=(whatsapp_process.stdout, "WHATSAPP", "35"))
    
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()
    
    def cleanup(signum=None, frame=None):
        print("\n\033[91mShutting down all services...\033[0m")
        backend_process.terminate()
        whatsapp_process.terminate()
        backend_process.wait()
        whatsapp_process.wait()
        print("\033[92mAll services stopped gracefully.\033[0m")
        sys.exit(0)

    # Register cleanup for termination signals
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        backend_process.wait()
        whatsapp_process.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
