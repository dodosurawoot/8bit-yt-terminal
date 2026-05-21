import json
import time
from ytmusicapi import YTMusic
from yt_terminal.config_manager import ConfigManager

ConfigManager.ensure_dirs()
with open(ConfigManager.OAUTH_FILE, "r") as f:
    token_data = json.load(f)

# Create a mock headers auth dictionary
auth_headers = {
    "Authorization": f"Bearer {token_data['access_token']}",
}

print("Testing with OAUTH_CUSTOM_FULL...")
try:
    yt = YTMusic(auth=auth_headers)
    print("Auth Type:", yt.auth_type)
    print("Requesting get_library_playlists...")
    playlists = yt.get_library_playlists(limit=5)
    print("SUCCESS! Fetched playlists:", len(playlists))
except Exception as e:
    print("FAILED with OAUTH_CUSTOM_FULL:", e)
