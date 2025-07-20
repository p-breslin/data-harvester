from pathlib import Path

# Package root
PACKAGE_ROOT = Path(__file__).resolve().parent

# Project root
PROJECT_ROOT = PACKAGE_ROOT.parent.parent

# Paths relative to those roots
DATA_DIR = PROJECT_ROOT.parent / "data"
CONFIG_DIR = PROJECT_ROOT / "src/core/configs"
