"""源码运行保留项目内数据，单文件EXE使用持久可写的用户数据目录。"""
import os
import sys


def data_directory():
    override = os.environ.get("ELITE_FILTER_DATA_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
        return os.path.join(base, "EliteDangerousFilter")
    return os.path.dirname(os.path.abspath(__file__))


def data_file(filename):
    directory = data_directory()
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)
