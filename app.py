import glob
import os
import re
import shutil
import tempfile
import traceback
from urllib.parse import urlparse, urlunparse

import requests
import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

APP_VERSION = "2026-04-02-patch5"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookies.txt")

PROCESSED_UPDATE_IDS = set()
PROCESSED_UPDATE_IDS_LIMIT = 1000


def log(msg):
    print(msg, flush=True)


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


def is_supported_instagram_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if "instagram.com" not in host:
            return False

        return any(part in path for part in ("/reel/", "/reels/", "/p/", "/tv/"))
    except Exception:
        return False


def is_probably_public_instagram_url(url: str) -> bool:
    return is_supported_instagram_url(url)


def find_instagram_media_url(text: str):
    if not text:
        return None

    m = re.search(
        r"(?:https?://)?(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+/?[^\s]*",
        text,
        re.I,
    )
    if not m:
        return None

    url = normalize_url(m.group(0))
    if not is_supported_instagram_url(url):
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


def send_message(chat_id: int, text: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
        "text": text,
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    return telegram("sendMessage", payload=payload)


def send_video_file(chat_id: int, file_path: str, caption=None):
    payload = {
        "chat_id": str(chat_id),
        "supports_streaming": "true",
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        return telegram("sendVideo", payload=payload, files=files)


def send_document_file(chat_id: int, file_path: str, caption=None):
    payload = {
        "chat_id": str(chat_id),
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"

    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        return telegram("sendDocument", payload=payload, files=files)


def build_result_caption():
    return '<a href="https://t.me/zalivreel">Nice_ig - автоматизация инстаграма</a>'


def build_user_friendly_error_message(error_text: str) -> str:
    s = (error_text or "").lower()

    restricted_markers = [
        "this content may be inappropriate",
        "unavailable for certain audiences",
        "private",
        "login required",
        "requested content is not available",
        "not available",
    ]

    if any(marker in s for marker in restricted_markers):
        return "Аккаунт приватный или контент 18+ - не получится скачать"

    return f"Ошибка: {error_text}"


def is_duplicate_update(update_id) -> bool:
    if update_id is None:
        return False
    return update_id in PROCESSED_UPDATE_IDS


def mark_update_processed(update_id):
    if update_id is None:
        return
    PROCESSED_UPDATE_IDS.add(update_id)
    if len(PROCESSED_UPDATE_IDS) > PROCESSED_UPDATE_IDS_LIMIT:
        PROCESSED_UPDATE_IDS.clear()


def build_ydl_opts(temp_dir: str, use_cookies: bool):
    output_template = os.path.join(temp_dir, "%(uploader)s_%(title).80B_%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "noplaylist": True,
        "format": "best",
        "merge_output_format": "mp4",
        "windowsfilenames": True,
        "quiet": False,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.instagram.com/",
        },
    }

    if use_cookies:
        ydl_opts["cookiefile"] = COOKIE_FILE

    return ydl_opts


def collect_downloaded_files(temp_dir: str):
    candidates = []
    for pattern in (
        "*.mp4", "*.mkv", "*.webm", "*.mov",
        "*.jpg", "*.jpeg", "*.png", "*.gif"
    ):
        candidates.extend(glob.glob(os.path.join(temp_dir, pattern)))

    candidates = [p for p in candidates if os.path.isfile(p)]
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates


def try_download_instagram_media(url: str, use_cookies: bool) -> str:
    temp_dir = tempfile.mkdtemp(prefix="igdl_")
    ydl_opts = build_ydl_opts(temp_dir, use_cookies=use_cookies)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        candidates = collect_downloaded_files(temp_dir)
        log(f"[download] use_cookies={use_cookies} found files={candidates}")

        if not candidates:
            raise RuntimeError("Файл после скачивания не найден")

        return candidates[0]
    except Exception:
        log(f"[download] exception use_cookies={use_cookies}:")
        log(traceback.format_exc())
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def download_instagram_media(url: str) -> str:
    log(f"[download] start url={url}")
    log(f"[download] cookie file path={COOKIE_FILE}")
    log(f"[download] cookie exists={os.path.exists(COOKIE_FILE)}")

    cookie_exists = os.path.exists(COOKIE_FILE)
    last_error = None

    if cookie_exists:
        try:
            return try_download_instagram_media(url, use_cookies=True)
        except Exception as e:
            last_error = e
            log("[download] download with cookies failed")

            if is_probably_public_instagram_url(url):
                log("[download] trying fallback without cookies for public instagram url")
                try:
                    return try_download_instagram_media(url, use_cookies=False)
                except Exception as e2:
                    last_error = e2
    else:
        log("[download] cookies.txt not found, trying without cookies")
        try:
            return try_download_instagram_media(url, use_cookies=False)
        except Exception as e:
            last_error = e

    if last_error is not None:
        raise last_error

    raise RuntimeError("Скачать media не удалось")



@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "service": "ig-reel-bot",
        "version": APP_VERSION,
    })


@app.get("/debug")
def debug():
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "bot_token_set": bool(BOT_TOKEN),
        "cookie_file_path": COOKIE_FILE,
        "cookie_exists": os.path.exists(COOKIE_FILE),
        "cwd": os.getcwd(),
        "script_dir": SCRIPT_DIR,
        "files_in_script_dir": sorted(os.listdir(SCRIPT_DIR)),
    })


@app.post("/webhook")
def webhook():
    try:
        update = request.get_json(force=True, silent=True) or {}
        log(f"[webhook] update={update}")

        update_id = update.get("update_id")
        if is_duplicate_update(update_id):
            log(f"[webhook] duplicate update_id={update_id} - skip")
            return jsonify({"ok": True, "skip": "duplicate update"})

        message = update.get("message") or {}
        text = (message.get("text") or message.get("caption") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")

        log(f"[webhook] chat_id={chat_id} message_id={message_id} text={text!r}")

        if not chat_id:
            return jsonify({"ok": True, "skip": "no chat_id"})

        media_url = find_instagram_media_url(text)
        log(f"[webhook] media_url={media_url}")

        if not media_url:
            return jsonify({"ok": True, "skip": "no instagram url"})

        send_message(chat_id, "Начинаю скачивание")
        file_path = download_instagram_media(media_url)
        result_caption = build_result_caption()
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".mp4", ".mkv", ".webm", ".mov"):
                send_video_file(chat_id, file_path, caption=result_caption)
            else:
                send_document_file(chat_id, file_path, caption=result_caption)
        finally:
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

        mark_update_processed(update_id)
        return jsonify({"ok": True})
    except Exception as e:
        log("[webhook] exception:")
        log(traceback.format_exc())

        try:
            update = request.get_json(force=True, silent=True) or {}
            update_id = update.get("update_id")
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id:
                user_error_text = build_user_friendly_error_message(str(e))
                send_message(chat_id, user_error_text)
            mark_update_processed(update_id)
        except Exception:
            log("[webhook] failed to send error message to telegram")
            log(traceback.format_exc())

        return jsonify({"ok": True, "error": str(e)}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)