"""会话JSON读写；原子替换避免异常中断时留下半个文件。"""
import json
import os
import tempfile


def load(path):
    try:
        with open(path, encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save(path, state):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".session-", suffix=".tmp", delete=False) as file:
            temporary = file.name
            json.dump(state, file, ensure_ascii=False, indent=1)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)
