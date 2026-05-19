import os
import json
from pathlib import Path

class ConfigManager:
    """Manages persistent configuration and paths for LANY Music CLI."""
    
    CONFIG_DIR = Path.home() / ".config" / "lany-music-cli"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    OAUTH_FILE = CONFIG_DIR / "oauth.json"
    CACHE_DIR = CONFIG_DIR / "cache"

    @classmethod
    def ensure_dirs(cls):
        """Ensures that the config and cache directories exist."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_config(cls) -> dict:
        """Loads config, returns empty dict if file does not exist."""
        cls.ensure_dirs()
        if not cls.CONFIG_FILE.exists():
            return {}
        try:
            with open(cls.CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save_config(cls, data: dict):
        """Saves config data."""
        cls.ensure_dirs()
        try:
            with open(cls.CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    @classmethod
    def is_authenticated(cls) -> bool:
        """Checks if OAuth file exists and is non-empty."""
        return cls.OAUTH_FILE.exists() and cls.OAUTH_FILE.stat().st_size > 0

    @classmethod
    def get_credentials(cls) -> tuple[str | None, str | None]:
        """Returns (client_id, client_secret) from config."""
        config = cls.load_config()
        return config.get("client_id"), config.get("client_secret")

    @classmethod
    def save_credentials(cls, client_id: str, client_secret: str):
        """Saves client_id and client_secret to config."""
        config = cls.load_config()
        config["client_id"] = client_id
        config["client_secret"] = client_secret
        cls.save_config(config)
