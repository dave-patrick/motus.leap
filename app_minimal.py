"""Minimal test app for debugging."""

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Tube Manager Minimal")
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def index():
    return FileResponse("web/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/test")
async def test():
    return FileResponse("web/test.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)