import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(cmd):
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def get_output(cmd):
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "command failed")
    return result.stdout.strip()


def main():
    try:
        branch = get_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    except Exception as e:
        print(f"Не удалось определить ветку git: {e}")
        raise SystemExit(1)

    message = "update"
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:]).strip() or "update"

    print(f"Текущая ветка: {branch}")
    print(f"Сообщение коммита: {message}")

    run(["git", "add", "."])

    status = get_output(["git", "status", "--porcelain"])
    if not status:
        print("Нет изменений для коммита.")
        return

    run(["git", "commit", "-m", message])
    run(["git", "push", "origin", branch])

    print("Готово: commit + push выполнены.")


if __name__ == "__main__":
    main()