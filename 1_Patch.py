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
        'APP_VERSION = "2026-04-02-patch4"',
        'APP_VERSION = "2026-04-02-patch5"',
        "APP_VERSION",
    )

    # 2) добавляем кеш обработанных update_id сразу после COOKIE_FILE
    old = '''COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookies.txt")
'''
    new = '''COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookies.txt")

PROCESSED_UPDATE_IDS = set()
PROCESSED_UPDATE_IDS_LIMIT = 1000
'''
    text = replace_once(text, old, new, "processed update ids storage")

    # 3) вставляем helper-функции после build_user_friendly_error_message
    marker = '''def build_user_friendly_error_message(error_text: str) -> str:
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
    addition = '''

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
'''
    if "def is_duplicate_update(update_id) -> bool:" not in text:
        if marker not in text:
            raise RuntimeError("Не найдено место для вставки duplicate helpers")
        text = text.replace(marker, marker + addition, 1)
        print("[OK] duplicate helpers")
    else:
        print("[SKIP] duplicate helpers уже есть")

    # 4) в webhook добавляем update_id и проверку на дубль
    old = '''        update = request.get_json(force=True, silent=True) or {}
        log(f"[webhook] update={update}")

        message = update.get("message") or {}
'''
    new = '''        update = request.get_json(force=True, silent=True) or {}
        log(f"[webhook] update={update}")

        update_id = update.get("update_id")
        if is_duplicate_update(update_id):
            log(f"[webhook] duplicate update_id={update_id} - skip")
            return jsonify({"ok": True, "skip": "duplicate update"})

        message = update.get("message") or {}
'''
    text = replace_once(text, old, new, "webhook duplicate check")

    # 5) после успешной отправки результата помечаем апдейт обработанным
    old = '''        finally:
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({"ok": True})
'''
    new = '''        finally:
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

        mark_update_processed(update_id)
        return jsonify({"ok": True})
'''
    text = replace_once(text, old, new, "mark processed on success")

    # 6) в except тоже помечаем апдейт и главное возвращаем 200, а не 500
    old = '''    except Exception as e:
        log("[webhook] exception:")
        log(traceback.format_exc())

        try:
            update = request.get_json(force=True, silent=True) or {}
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            message_id = message.get("message_id")
            if chat_id:
                user_error_text = build_user_friendly_error_message(str(e))
                send_message(chat_id, user_error_text)
        except Exception:
            log("[webhook] failed to send error message to telegram")
            log(traceback.format_exc())

        return jsonify({"ok": False, "error": str(e)}), 500
'''
    new = '''    except Exception as e:
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
'''
    text = replace_once(text, old, new, "except returns 200")

    APP_FILE.write_text(text, encoding="utf-8")
    print("\\n[DONE] app.py пропатчен")
    print("[INFO] Теперь один и тот же update не будет спамиться по кругу")
    print("[INFO] После ошибки webhook будет отвечать Telegram'у 200, не 500")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
    input("\\nНажми Enter для выхода...")