import os
import sys
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle (.exe)
    _APP_DIR = os.path.dirname(sys.executable)
else:
    # Running in a normal Python environment
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = os.path.dirname(_HERE)

load_dotenv(os.path.join(_APP_DIR, ".env"))

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
