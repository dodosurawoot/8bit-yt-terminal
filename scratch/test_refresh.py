import time
import json
import logging
from pathlib import Path
from ytmusicapi import OAuthCredentials, YTMusic
from ytmusicapi.auth.oauth import RefreshingToken
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("test_refresh")

ConfigManager.ensure_dirs()
client_id, client_secret = ConfigManager.get_credentials()
print("Client ID:", client_id)
print("Client Secret exists:", bool(client_secret))

# Load current oauth.json
with open(ConfigManager.OAUTH_FILE, "r") as f:
    token_data = json.load(f)

print("Current token_data:")
for k, v in token_data.items():
    if k in ["access_token", "refresh_token"]:
        print(f"  {k}: {v[:10]}...{v[-10:] if len(v) > 10 else ''}")
    else:
        print(f"  {k}: {v}")

print("Current time:", int(time.time()))
expires_at = token_data.get("expires_at", 0)
time_left = expires_at - int(time.time())
print(f"Time left until expiration: {time_left} seconds")

# Test refreshing manually
if client_id and client_secret:
    creds = OAuthCredentials(client_id, client_secret)
    print("Refreshing token via credentials.refresh_token...")
    try:
        fresh = creds.refresh_token(token_data["refresh_token"])
        print("Refresh successful! New data keys:", list(fresh.keys()))
        print("New expires_in:", fresh.get("expires_in"))
    except Exception as e:
        log.exception("Error during credentials.refresh_token")
else:
    print("No credentials to test refresh")
