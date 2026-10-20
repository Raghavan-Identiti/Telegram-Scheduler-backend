import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    try:
        import uvicorn
        print(f"[Backend] Starting FastAPI backend on port {port}...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        print(f"[Backend Error] Failed to run backend server: {e}", file=sys.stderr)

