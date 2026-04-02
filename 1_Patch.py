from pathlib import Path

APP_FILE = Path("app.py")


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок для замены: {label}")
    text = text.replace(old, new, 1)
    print(f"[OK] {label}")
    return text


def main():
    print("[START] Патчу app.py...")

    if not APP_FILE.exists():
        raise FileNotFoundError("В текущей папке не найден app.py")

    text = APP_FILE.read_text(encoding="utf-8")
    original = text

    # 1. send_video_file
    old = '''def send_video_file(chat_id: int, file_path: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
        "supports_streaming": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        return telegram("sendVideo", payload=payload, files=files)
'''
    new = '''def send_video_file(chat_id: int, file_path: str, caption=None):
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
'''
    text = must_replace(text, old, new, "send_video_file")

    # 2. send_document_file
    old = '''def send_document_file(chat_id: int, file_path: str, reply_to_message_id=None):
    payload = {
        "chat_id": str(chat_id),
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(reply_to_message_id)

    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        return telegram("sendDocument", payload=payload, files=files)
'''
    new = '''def send_document_file(chat_id: int, file_path: str, caption=None):
    payload = {
        "chat_id": str(chat_id),
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"

    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        return telegram("sendDocument", payload=payload, files=files)
'''
    text = must_replace(text, old, new, "send_document_file")

    # 3. функция подписи
    insert_after = '''def send_document_file(chat_id: int, file_path: str, caption=None):
    payload = {
        "chat_id": str(chat_id),
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"

    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        return telegram("sendDocument", payload=payload, files=files)
'''
    addition = '''

def build_result_caption():
    return '<a href="https://t.me/zalivreel">Nice_ig - автоматизация инстаграма</a>'
'''
    if 'def build_result_caption()' not in text:
        if insert_after not in text:
            raise RuntimeError("Не найдено место для вставки build_result_caption")
        text = text.replace(insert_after, insert_after + addition, 1)
        print("[OK] build_result_caption")
    else:
        print("[SKIP] build_result_caption уже есть")

    # 4. убираем сообщение если нет ссылки
    old = '''        if not media_url:
            send_message(chat_id, "Кинь ссылку на Instagram post/reel.", reply_to_message_id=message_id)
            return jsonify({"ok": True, "skip": "no instagram url"})
'''
    new = '''        if not media_url:
            return jsonify({"ok": True, "skip": "no instagram url"})
'''
    text = must_replace(text, old, new, "remove no-url reply")

    # 5. убираем "Скачиваю..."
    old = '''        send_message(chat_id, "Скачиваю...", reply_to_message_id=message_id)

'''
    new = ''
    text = must_replace(text, old, new, "remove downloading message")

    # 6. меняем отправку результата
    old = '''        file_path = download_instagram_media(media_url)
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
    new = '''        file_path = download_instagram_media(media_url)
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
'''
    text = must_replace(text, old, new, "send result without echo + with caption")

    if text == original:
        raise RuntimeError("Изменений нет")

    APP_FILE.write_text(text, encoding="utf-8")
    print("[DONE] app.py успешно пропатчен")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
    input("\\nНажми Enter для выхода...")