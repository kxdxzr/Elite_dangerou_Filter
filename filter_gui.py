"""Compatibility launcher: python filter_gui.py [--smoke-test / --session-test]."""
from pathlib import Path
import runpy
import sys


if __name__ == '__main__':
    source = Path(__file__).resolve().parent / 'src'
    sys.path.insert(0, str(source))
    runpy.run_path(str(source / 'filter_gui.py'), run_name='__main__')
