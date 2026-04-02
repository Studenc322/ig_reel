from pathlib import Path

APP_FILE = Path("app.py")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Фрагмент не найден для замены:\n{old[:300]}")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, new_block: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise RuntimeError(f"Не найден start_marker:\n{start_marker}")

    end = text.find(end_marker, start)
    if end == -1:
        raise RuntimeError(f"Не найден end_marker:\n{end_marker}")

    return text[:start] + new_block + text[end:]


text = APP_FILE.read_text(encoding="utf-8")


# 1) reel -> reel/p/tv
text = replace_once(
    text,
    '''def is_public_instagram_reel(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if "instagram.com" not in host:
            return False

        return "/reel/" in path
    except Exception:
        return False


def find_instagram_reel_url(text: str):
    if not text:
        return None

    m = re.search(r"https?://(?:www\\.)?instagram\\.com/reel/[A-Za-z0-9_-]+/?[^\\s]*", text, re.I)
    if not m:
        return None

    url = normalize_url(m.group(0))
    if not is_public_instagram_reel(url):
        return None
    return url
''',
    '''def is_supported_instagram_url(url: str) -> bool:
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
)


# 2) sendDocument
text = replace_once(
    text,
    '''def send_video_file(chat_id: int, file_path: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
        "supports_streaming": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        return telegram("sendVideo", payload=payload, files=files)
''',
    '''def send_video_file(chat_id: int, file_path: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
        "supports_streaming": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        return telegram("sendVideo", payload=payload, files=files)


def send_document_file(chat_id: int, file_path: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        return telegram("sendDocument", payload=payload, files=files)
'''
)


# 3) download_reel -> новый блок без regex
new_download_block = '''def build_ydl_opts(temp_dir: str, use_cookies: bool):
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


'''

text = replace_block(
    text,
    'def download_reel(url: str) -> str:\n',
    '\n\n@app.get("/")\n',
    new_download_block + '\n@app.get("/")\n'
)


# 4) webhook
text = replace_once(
    text,
    '''        reel_url = find_instagram_reel_url(text)
        log(f"[webhook] reel_url={reel_url}")

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
''',
    '''        media_url = find_instagram_media_url(text)
        log(f"[webhook] media_url={media_url}")

        if not media_url:
            send_message(chat_id, "Кинь ссылку на Instagram post/reel.", reply_to_message_id=message_id)
            return jsonify({"ok": True, "skip": "no instagram url"})

        send_message(chat_id, "Скачиваю...", reply_to_message_id=message_id)

        file_path = download_instagram_media(media_url)
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".mp4", ".mkv", ".webm", ".mov"):
                send_video_file(chat_id, file_path, reply_to_message_id=message_id)
            else:
                send_document_file(chat_id, file_path, reply_to_message_id=message_id)
        finally:
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
'''
)


APP_FILE.write_text(text, encoding="utf-8")
print("OK: app.py patched")