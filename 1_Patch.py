from pathlib import Path

APP_FILE = Path("app.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок: {label}")
    print(f"[OK] {label}")
    return text.replace(old, new, 1)


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError("app.py не найден в текущей папке")

    text = APP_FILE.read_text(encoding="utf-8")

    # 1) версия
    text = replace_once(
        text,
        'APP_VERSION = "2026-04-02-patch2"',
        'APP_VERSION = "2026-04-02-patch4"',
        "APP_VERSION",
    )

    # 2) вставляем helper для нормального текста ошибки
    marker = '''def build_result_caption():
    return '<a href="https://t.me/zalivreel">Nice_ig - автоматизация инстаграма</a>'
'''
    if "def build_user_friendly_error_message(error_text: str) -> str:" not in text:
        addition = '''

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
'''
        if marker not in text:
            raise RuntimeError("Не найдено место для вставки build_user_friendly_error_message")
        text = text.replace(marker, marker + addition, 1)
        print("[OK] build_user_friendly_error_message")
    else:
        print("[SKIP] build_user_friendly_error_message уже есть")

    # 3) добавляем отбивку перед скачиванием
    old = '''        if not media_url:
            return jsonify({"ok": True, "skip": "no instagram url"})

        file_path = download_instagram_media(media_url)
'''
    new = '''        if not media_url:
            return jsonify({"ok": True, "skip": "no instagram url"})

        send_message(chat_id, "Начинаю скачивание")
        file_path = download_instagram_media(media_url)
'''
    text = replace_once(text, old, new, "start download message")

    # 4) меняем сырой текст ошибки на человеческий
    old = '''            if chat_id:
                send_message(chat_id, f"Ошибка: {e}", reply_to_message_id=message_id)
'''
    new = '''            if chat_id:
                user_error_text = build_user_friendly_error_message(str(e))
                send_message(chat_id, user_error_text)
'''
    text = replace_once(text, old, new, "friendly error message")

    APP_FILE.write_text(text, encoding="utf-8")
    print("\\n[DONE] app.py пропатчен")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
    input("\\nНажми Enter для выхода...")