import subprocess
import sys
import threading
import os
import signal

def stream_output(pipe, prefix, color_code):
    for line in iter(pipe.readline, ''):
        if not line:
            break
        try:
            line_str = line.rstrip()
            print(f"\033[{color_code}m[{prefix}]\033[0m {line_str}", flush=True)
        except Exception:
            pass

def main():
    # Enable ANSI escape sequences on Windows
    os.system("")
    print("\033[92mStarting backend services...\033[0m")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = base_dir
    whatsapp_dir = os.path.join(base_dir, "whatsapp-service")
    
    # Set UTF-8 encoding for the Python subprocess so it doesn't crash on emojis in Windows
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    port = os.environ.get("PORT", "8000")
    print(f"\033[92mStarting Uvicorn on port {port}...\033[0m", flush=True)
    
    # Start Python Backend (FastAPI)
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1
    )
    
    # Threads to stream output (34 = blue for API)
    t1 = threading.Thread(target=stream_output, args=(backend_process.stdout, "FASTAPI", "34"))
    
    t1.daemon = True
    t1.start()

    # Start WhatsApp Node Service (32 = green for WhatsApp)
    whatsapp_process = subprocess.Popen(
        ["node", "index.js"],
        cwd=whatsapp_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1
    )
    t2 = threading.Thread(target=stream_output, args=(whatsapp_process.stdout, "WHATSAPP", "32"))
    t2.daemon = True
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
