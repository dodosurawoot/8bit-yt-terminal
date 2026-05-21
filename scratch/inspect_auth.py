import os
import tempfile
import json
from pathlib import Path
from yt_terminal.config_manager import ConfigManager
from yt_terminal.music_service import MusicService

print("CONFIG_DIR:", ConfigManager.CONFIG_DIR)
print("CONFIG_FILE exists:", ConfigManager.CONFIG_FILE.exists())
print("OAUTH_FILE exists:", ConfigManager.OAUTH_FILE.exists())

if ConfigManager.CONFIG_FILE.exists():
    try:
        with open(ConfigManager.CONFIG_FILE, "r") as f:
            print("Config:", json.load(f))
    except Exception as e:
        print("Error reading config:", e)

if ConfigManager.OAUTH_FILE.exists():
    try:
        with open(ConfigManager.OAUTH_FILE, "r") as f:
            oauth_data = json.load(f)
            # print keys instead of values for security
            print("OAuth data keys:", list(oauth_data.keys()))
            if "refresh_token" in oauth_data:
                print("Refresh token exists: Yes")
            else:
                print("Refresh token exists: No")
    except Exception as e:
        print("Error reading OAuth file:", e)

log_path = os.path.join(tempfile.gettempdir(), "yt-terminal.log")
print("Log path:", log_path)
if os.path.exists(log_path):
    print("Log size:", os.path.getsize(log_path))
    print("Last 30 lines of log:")
    with open(log_path, "r") as f:
        lines = f.readlines()
        for line in lines[-30:]:
            print(line.strip())
else:
    print("Log file does not exist")
