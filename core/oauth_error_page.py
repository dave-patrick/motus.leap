"""Readable OAuth callback failures with safe text and a recovery path."""
from html import escape

from fastapi.responses import HTMLResponse


def oauth_error_page(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    title, message = escape(title), escape(message)
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — motus.leap</title>
<style>
body{{margin:0;background:#0f1115;color:#f3f5f8;font:16px/1.6 system-ui,sans-serif;min-height:100vh;display:grid;place-items:center}}
main{{max-width:480px;padding:32px 24px}}h1{{font-size:28px;line-height:1.25}}p{{color:#b8c0cc;overflow-wrap:anywhere}}
nav{{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}}a{{padding:12px 20px;background:#2374a6;color:white;border-radius:10px;text-decoration:none}}
a:focus-visible{{outline:2px solid #9bcbff;outline-offset:4px}}nav a:last-child{{background:#20242c}}
</style></head><body><main><p>motus.leap</p><h1>{title}</h1><p>{message}</p>
<nav aria-label="Sign-in recovery"><a href="/auth">Try sign-in again</a><a href="/settings">Connection settings</a></nav>
<p>If you started in the Android app, return to the app and start sign-in again.</p>
</main></body></html>""", status_code=status_code)
