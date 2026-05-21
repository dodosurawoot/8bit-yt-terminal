import logging
import json
import time
from ytmusicapi import OAuthCredentials, YTMusic
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(level=logging.DEBUG)

ConfigManager.ensure_dirs()
client_id, client_secret = ConfigManager.get_credentials()

with open(ConfigManager.OAUTH_FILE, "r") as f:
    token_data = json.load(f)

creds = OAuthCredentials(client_id, client_secret)
yt = YTMusic(str(ConfigManager.OAUTH_FILE), oauth_credentials=creds)

print("Auth Type:", yt.auth_type)
print("Base Headers:")
for k, v in yt.base_headers.items():
    print(f"  {k}: {v}")

print("Headers property:")
for k, v in yt.headers.items():
    print(f"  {k}: {v}")

# Let's inspect context
print("Context client:")
print(json.dumps(yt.context.get("context", {}).get("client", {}), indent=2))
