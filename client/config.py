import os
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Single project-root .env takes priority; local client/.env is a fallback.
load_dotenv(os.path.join(_ROOT, ".env"))
load_dotenv(os.path.join(_HERE, ".env"), override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
APP_NAME = os.getenv("APP_NAME", "SetuLink")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# Demo accounts for login helper display
DEMO_ACCOUNTS = [
    ("System Owner", "#fef3c7", "#92400e", "owner@setulink.io",    "Admin@123"),
    ("Master",       "#ede9fe", "#5b21b6", "master@setulink.io",   "master123"),
    ("2nd Master",   "#dbeafe", "#1e40af", "second@setulink.io",   "second123"),
    ("Admin",        "#dcfce7", "#166534", "admin@setulink.io",    "admin123"),
    ("Trusted",      "#fce7f3", "#9d174d", "trusted@setulink.io",  "trusted123"),
]
