import os
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Single project-root .env takes priority; local client/.env is a fallback.
# load_dotenv does not override already-set vars, so the root file wins.
load_dotenv(os.path.join(_ROOT, ".env"))
load_dotenv(os.path.join(_HERE, ".env"), override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
APP_NAME = os.getenv("APP_NAME", "ProjectX")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

ZEROTIER_LOCAL_URL = "http://localhost:9993"
ZEROTIER_AUTH_FILE = r"C:\ProgramData\ZeroTier\One\authtoken.secret"

TUNNEL_MODE = os.getenv("TUNNEL_MODE", "zerotier")  # "zerotier" | "wireguard"
WG_INTERFACE = os.getenv("WG_INTERFACE", "wg-client")
WG_CONFIG_DIR = os.getenv("WG_CONFIG_DIR", os.path.join(os.path.expanduser("~"), ".projectx"))
WG_KEY_STORAGE = os.path.join(os.path.expanduser("~"), ".projectx", "wg_keys.json")
