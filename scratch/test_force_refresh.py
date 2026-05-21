import logging
import json
from ytmusicapi import OAuthCredentials, YTMusic
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("test_force_refresh")

ConfigManager.ensure_dirs()
client_id, client_secret = ConfigManager.get_credentials()
print("Client ID:", client_id)

with open(ConfigManager.OAUTH_FILE, "r") as f:
    token_data = json.load(f)

if client_id and client_secret:
    creds = OAuthCredentials(client_id, client_secret)
    print("Forcing token refresh...")
    try:
        fresh = creds.refresh_token(token_data["refresh_token"])
        print("Refresh successful!")
        
        # Update token_data
        token_data["access_token"] = fresh["access_token"]
        token_data["expires_at"] = int(time_left := fresh["expires_in"]) # Wait, let's calculate expires_at properly
        import time
        token_data["expires_at"] = int(time.time()) + fresh["expires_in"]
        token_data["expires_in"] = fresh["expires_in"]
        
        # Save back to file
        with open(ConfigManager.OAUTH_FILE, "w") as f:
            json.dump(token_data, f, indent=4)
        print("Saved refreshed token to oauth.json")
        
        # Try get_library_playlists
        print("Initializing YTMusic with the fresh token...")
        yt = YTMusic(str(ConfigManager.OAUTH_FILE), oauth_credentials=creds)
        print("Fetching library playlists...")
        playlists = yt.get_library_playlists(limit=5)
        print("SUCCESS! Fetched playlists:", len(playlists))
        
    except Exception as e:
        log.exception("Error during force refresh or API call")
else:
    print("No credentials to test force refresh")
