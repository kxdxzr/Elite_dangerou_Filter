"""Move legacy root-level runtime files without overwriting existing destinations."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_paths import migrate_legacy_files


if __name__ == '__main__':
    report = migrate_legacy_files()
    print(json.dumps(report, ensure_ascii=True))
    raise SystemExit(bool(report['conflicts']))
