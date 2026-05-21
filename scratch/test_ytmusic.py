import logging
import sys
from pathlib import Path
from ytmusicapi import YTMusic, OAuthCredentials
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("test")

ConfigManager.ensure_dirs()
client_id, client_secret = ConfigManager.get_credentials()
print("Client ID:", client_id)
print("Client Secret exists:", bool(client_secret))
print("OAUTH_FILE:", ConfigManager.OAUTH_FILE)

try:
    if client_id and client_secret:
        creds = OAuthCredentials(client_id, client_secret)
        yt = YTMusic(str(ConfigManager.OAUTH_FILE), oauth_credentials=creds)
    else:
        yt = YTMusic(str(ConfigManager.OAUTH_FILE))
    
    print("YTMusic client initialized successfully.")
    
    # Try an authenticated call
    print("Fetching library playlists...")
    playlists = yt.get_library_playlists(limit=5)
    print("Successfully fetched playlists:", len(playlists))
    
except Exception as e:
    log.exception("Error during YTMusic initialization or request")
