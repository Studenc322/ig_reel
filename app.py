import glob
import os
import re
import shutil
import tempfile
from urllib.parse import urlparse, urlunparse

import requests
import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookies.txt")


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""

    parsed = urlparse(url)

    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)

    cleaned = parsed._replace(query="", fragment="")
    url = urlunparse(cleaned)

    if not url.endswith("/"):
        url += "/"

    return url


def is_public_instagram_reel(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if "instagram.com" not in host:
            return False

        return "/reel/" in path
    except Exception:
        return False


def find_instagram_reel_url(text: str) -> str | None:
    if not text:
        return None

    m = re.search(r"https?://(?:www\.)?instagram\.com/reel/[A-Za-z0-9_-]+/?[^\s]*", text, re.I)
    if not m:
        return None

    url = normalize_url(m.group(0))
    if not is_public_instagram_reel(url):
        return None
    return url


def telegram(method: str, payload=None, files=None):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    resp = requests.post(
        f"{BASE_URL}/{method}",
        data=payload,
        files=files,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")

    return data


def send_message(chat_id: int, text: str, reply_to_message_id: int | None = None):
    payload = {
        "chat_id": str(chat_id),
        "text": text,
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    return telegram("sendMessage", payload=payload)


def send_video_file(chat_id: int, file_path: str, reply_to_message_id: int | None = None):
    payload = {
        "chat_id": str(chat_id),
        "supports_streaming": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        return telegram("sendVideo", payload=payload, files=files)


def download_reel(url: str) -> str:
    if not os.path.exists(COOKIE_FILE):
        raise FileNotFoundError("cookies.txt не найден рядом с app.py")

    temp_dir = tempfile.mkdtemp(prefix="igdl_")
    output_template = os.path.join(temp_dir, "%(uploader)s_%(title).80B_%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "noplaylist": True,
        "format": "best",
        "merge_output_format": "mp4",
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "cookiefile": COOKIE_FILE,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.instagram.com/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        candidates = []
        for pattern in ("*.mp4", "*.mkv", "*.webm", "*.mov"):
            candidates.extend(glob.glob(os.path.join(temp_dir, pattern)))

        if not candidates:
            raise RuntimeError("Файл после скачивания не найден")

        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "ig-reel-bot"})


@app.post("/webhook")
def webhook():
    try:
        update = request.get_json(force=True, silent=True) or {}
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")

        if not chat_id:
            return jsonify({"ok": True, "skip": "no chat_id"})

        reel_url = find_instagram_reel_url(text)
        if not reel_url:
            send_message(chat_id, "Кинь ссылку на Instagram reel.", reply_to_message_id=message_id)
            return jsonify({"ok": True, "skip": "no reel url"})

        send_message(chat_id, "Скачиваю...", reply_to_message_id=message_id)

        file_path = download_reel(reel_url)
        try:
            send_video_file(chat_id, file_path, reply_to_message_id=message_id)
        finally:
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({"ok": True})
    except Exception as e:
        try:
            update = request.get_json(force=True, silent=True) or {}
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            message_id = message.get("message_id")
            if chat_id:
                send_message(chat_id, f"Ошибка: {e}", reply_to_message_id=message_id)
        except Exception:
            pass

        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)