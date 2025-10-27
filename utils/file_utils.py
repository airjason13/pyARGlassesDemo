import os
import random
import string

from global_def import *
import json


def replace_lines_in_file(filename: str, replacements: dict):
    """
    用 replacements dict 更新檔案內容。
    如果某行以 k= 開頭，就整行替換成 k=v
    """
    new_lines = []
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        updated = False
        for k, v in replacements.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated = True
                break
        if not updated:
            new_lines.append(line)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        f.truncate()
        f.flush()
        f.close()
        os.sync()

def file_to_dict(filename: str, splitter: str = "=") -> dict:
    """ 讀取檔案內容，每行用 splitter 分割成 key/value，並回傳 dict。 遇到空行或沒有 splitter 的行會跳過。 """

    result = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or splitter not in line:
                continue
            key, value = line.split(splitter, 1)
            result[key.strip()] = value.strip()
    return result


def replace_lines_in_file_with_dict(filename: str, replacements: dict):
    """
    用 replacements dict 更新檔案內容。
    如果某行以 k= 開頭，就整行替換成 k=v
    """
    new_lines = []
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        updated = False
        for k, v in replacements.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated = True
                break
        if not updated:
            new_lines.append(line)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        f.truncate()
        f.flush()
        f.close()
        os.sync()


def list_files_by_ext(root_path: str, **kwargs) -> str:
    """
    遍歷 root_path 下的所有檔案，根據副檔名條件回傳 JSON 格式 (保留目錄層級)

    :param root_path: 目錄路徑
    :param kwargs: 例如 ext=[".mp4", ".jpg"]
    :return: JSON 字串
    """
    # 如果 kwargs 為空，表示不過濾
    exts = None
    if kwargs:
        exts = kwargs.get("ext", None)
        if exts is not None:
            exts = [e.lower() for e in exts]

    def walk_dir(path):
        tree = {}
        for entry in sorted(os.listdir(path)):
            fullpath = os.path.join(path, entry)
            if os.path.isdir(fullpath):
                tree[entry] = walk_dir(fullpath)
            else:
                # 沒有過濾條件 → 全部列出
                if exts is None or os.path.splitext(entry)[1].lower() in exts:
                    tree.setdefault("files", []).append(entry)
        return tree

    result = walk_dir(root_path)
    return json.dumps(result, indent=2, ensure_ascii=False)

def gen_string(length: int) -> str:
    chars = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    return ''.join(random.choice(chars) for _ in range(length))


# 範例：
if __name__ == "__main__":
    root = "."
    print("=== 列出所有檔案 ===")
    print(list_files_by_ext(root))   # kwargs 為空，列出所有檔案

    print("\n=== 只列出 mp4/jpg ===")
    print(list_files_by_ext(root, ext=[".mp4", ".jpg"]))


# example
'''if __name__ == "__main__":
    replacements = {
        "ssid": "MyWiFi",
        "channel": "6",
        "wpa_passphrase": "newpassword123"
    }
    replace_lines_in_file("uap0_hostapd.conf", replacements)
    log.debug("檔案已更新完成！")'''

