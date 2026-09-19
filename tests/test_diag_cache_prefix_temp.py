import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_diagnostic_temporaire_cache_prefixe():
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "diag_cache_prefix.py")],
                       cwd=ROOT, text=True, capture_output=True, check=True)
    raise AssertionError("DIAGNOSTIC_CACHE_PREFIX\n" + p.stdout)
