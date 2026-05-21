import json
import time
from ytmusicapi import OAuthCredentials, YTMusic
from yt_terminal.config_manager import ConfigManager

ConfigManager.ensure_dirs()
client_id, client_secret = ConfigManager.get_credentials()

with open(ConfigManager.OAUTH_FILE, "r") as f:
    token_data = json.load(f)

creds = OAuthCredentials(client_id, client_secret)

client_names = ["WEB_REMIX", "ANDROID_MUSIC", "TVHTML5", "TV_HTML5", "WEB"]

for name in client_names:
    print(f"\n--- Testing clientName: {name} ---")
    try:
        yt = YTMusic(str(ConfigManager.OAUTH_FILE), oauth_credentials=creds)
        
        # Override clientName and clientVersion
        yt.context["context"]["client"]["clientName"] = name
        if name == "ANDROID_MUSIC":
            yt.context["context"]["client"]["clientVersion"] = "17.05.33"
        elif name in ["TVHTML5", "TV_HTML5"]:
            yt.context["context"]["client"]["clientVersion"] = "7.20230521.01.00"
            
        print(f"Requesting get_library_playlists using {name}...")
        playlists = yt.get_library_playlists(limit=2)
        print(f"SUCCESS with {name}! Fetched playlists: {len(playlists)}")
        break
    except Exception as e:
        print(f"FAILED with {name}: {e}")
