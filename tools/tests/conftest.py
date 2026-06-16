import sys
from pathlib import Path

# Корень репозитория в sys.path, чтобы работал `from tools.<module> import ...`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
