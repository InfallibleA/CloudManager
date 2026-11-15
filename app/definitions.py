from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
ENV_FILE = ROOT_DIR / '.env'
