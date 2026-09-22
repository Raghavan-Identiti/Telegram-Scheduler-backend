from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import pandas as pd

router = APIRouter()
LOGS_DIR = "logs"

@router.get("/logs")
def list_log_files():
    files = []
    for filename in os.listdir(LOGS_DIR):
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            path = os.path.join(LOGS_DIR, filename)
            files.append({
                "name": filename,
                "size": os.path.getsize(path),
                "timestamp": os.path.getmtime(path)
            })
    return sorted(files, key=lambda f: f["timestamp"], reverse=True)

@router.get("/logs/{filename}")
def preview_excel_file(filename: str):
    path = os.path.join(LOGS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    
    df = pd.read_excel(path)
    return df.fillna("").to_dict(orient="records")

@router.get("/logs/download/{filename}")
def download_excel_file(filename: str):
    path = os.path.join(LOGS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=filename)
