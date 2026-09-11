# app.py
# Minimal webhook receiver for TradingView V24.3 and polling endpoint for MT5.
# Deploy on any public HTTPS host. Keep TOKEN secret.

from flask import Flask, request, Response
from threading import Lock
from datetime import datetime, timezone
import os, uuid

app = Flask(__name__)

TOKEN = os.environ.get("V243_TOKEN", "CHANGE_ME")
_lock = Lock()
_latest = "NONE"

def parse_pipe(msg: str):
    parts = [p.strip() for p in msg.strip().split("|") if p.strip()]
    side = "BUY" if "BUY" in parts else ("SELL" if "SELL" in parts else "")
    fields = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            fields[k.strip()] = v.strip()
    return side, fields

@app.get("/health")
def health():
    return {"ok": True, "service": "v243-bridge"}

@app.post("/webhook")
def webhook():
    global _latest
    token = request.args.get("token", "")
    if token != TOKEN:
        return Response("unauthorized", status=401)

    msg = request.get_data(as_text=True).strip()
    if not msg.startswith("V24.3|XAUUSD|M5|"):
        return Response("ignored", status=202)

    side, fields = parse_pipe(msg)
    if side not in ("BUY", "SELL"):
        return Response("bad-side", status=400)

    # Basic validation
    required = ["SECTOR", "SL", "TP"]
    if any(k not in fields for k in required):
        return Response("missing-fields", status=400)

    sig_id = str(uuid.uuid4())
    ts = int(datetime.now(timezone.utc).timestamp())

    # Inject immutable bridge fields used by MT5 for de-duplication and age checks.
    final = f"V24.3|ID={sig_id}|TS={ts}|XAUUSD|M5|{side}"
    for p in msg.split("|")[4:]:
        if p.strip():
            final += "|" + p.strip()

    with _lock:
        _latest = final

    return Response("ok", status=200)

@app.get("/signal")
def signal():
    token = request.args.get("token", "")
    if token != TOKEN:
        return Response("unauthorized", status=401)

    with _lock:
        return Response(_latest, status=200, mimetype="text/plain")

if __name__ == "__main__":
    # For local testing only. Public production use should be behind HTTPS.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
