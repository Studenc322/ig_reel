from pathlib import Path

APP_FILE = Path("app.py")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Фрагмент не найден для замены:\\n{old[:400]}")
    return text.replace(old, new, 1)


def main():
    text = APP_FILE.read_text(encoding="utf-8")

    # 1) Добавляем версию рядом с app = Flask(__name__)
    if 'APP_VERSION = "2026-04-02-patch2"' not in text:
        text = replace_once(
            text,
            'app = Flask(__name__)\n',
            'app = Flask(__name__)\n\nAPP_VERSION = "2026-04-02-patch2"\n',
        )

    # 2) Расширяем поддержку ссылок + делаем парсер терпимее
    old_block = '''def is_supported_instagram_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if "instagram.com" not in host:
            return False

        return any(part in path for part in ("/reel/", "/p/", "/tv/"))
    except Exception:
        return False


def is_probably_public_instagram_url(url: str) -> bool:
    return is_supported_instagram_url(url)


def find_instagram_media_url(text: str):
    if not text:
        return None

    m = re.search(
        r"https?://(?:www\\.)?instagram\\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+/?[^\\s]*",
        text,
        re.I,
    )
    if not m:
        return None

    url = normalize_url(m.group(0))
    if not is_supported_instagram_url(url):
        return None
    return url
'''
    new_block = '''def is_supported_instagram_url(url: str) -> bool:
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
        r"(?:https?://)?(?:www\\.)?instagram\\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+/?[^\\s]*",
        text,
        re.I,
    )
    if not m:
        return None

    url = normalize_url(m.group(0))
    if not is_supported_instagram_url(url):
        return None
    return url
'''
    if old_block in text:
        text = text.replace(old_block, new_block, 1)
    elif new_block not in text:
        raise RuntimeError("Не найден блок функций instagram url для замены")

    # 3) Убираем двойной декоратор над health
    text = text.replace('\n\n@app.get("/")\n\n\n@app.get("/")\ndef health():\n', '\n\n@app.get("/")\ndef health():\n', 1)

    # 4) Обновляем health endpoint, чтобы было видно версию
    old_health = '''@app.get("/")
def health():
    return jsonify({"ok": True, "service": "ig-reel-bot"})
'''
    new_health = '''@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "service": "ig-reel-bot",
        "version": APP_VERSION,
    })
'''
    if old_health in text:
        text = text.replace(old_health, new_health, 1)
    elif new_health not in text:
        raise RuntimeError("Не найден блок health() для замены")

    # 5) Обновляем debug endpoint, чтобы было видно версию
    old_debug = '''@app.get("/debug")
def debug():
    return jsonify({
        "ok": True,
        "bot_token_set": bool(BOT_TOKEN),
        "cookie_file_path": COOKIE_FILE,
        "cookie_exists": os.path.exists(COOKIE_FILE),
        "cwd": os.getcwd(),
        "script_dir": SCRIPT_DIR,
        "files_in_script_dir": sorted(os.listdir(SCRIPT_DIR)),
    })
'''
    new_debug = '''@app.get("/debug")
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
'''
    if old_debug in text:
        text = text.replace(old_debug, new_debug, 1)
    elif new_debug not in text:
        raise RuntimeError("Не найден блок debug() для замены")

    # 6) В webhook читаем text ИЛИ caption
    old_webhook_piece = '''        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")

        log(f"[webhook] chat_id={chat_id} message_id={message_id} text={text!r}")
'''
    new_webhook_piece = '''        message = update.get("message") or {}
        text = (message.get("text") or message.get("caption") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")

        log(f"[webhook] chat_id={chat_id} message_id={message_id} text={text!r}")
'''
    if old_webhook_piece in text:
        text = text.replace(old_webhook_piece, new_webhook_piece, 1)
    elif new_webhook_piece not in text:
        raise RuntimeError("Не найден кусок webhook с text/caption для замены")

    APP_FILE.write_text(text, encoding="utf-8")
    print("OK: app.py patched")
    print("Проверка после деплоя:")
    print("1) /debug должен показать version = 2026-04-02-patch2")
    print("2) /debug покажет cookie_exists true/false")
    print("3) бот должен принимать /p/, /reel/, /reels/, /tv/")


if __name__ == "__main__":
    main()