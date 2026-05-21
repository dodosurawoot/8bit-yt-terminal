import os
import json
import shutil
import logging
from pathlib import Path

log = logging.getLogger("yt-terminal")

class ConfigManager:
    """Manages persistent configuration and paths for YT-Terminal."""
    
    CONFIG_DIR = Path.home() / ".config" / "yt-terminal"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    OAUTH_FILE = CONFIG_DIR / "oauth.json"
    CACHE_DIR = CONFIG_DIR / "cache"

    @classmethod
    def ensure_dirs(cls):
        """Ensures that the config and cache directories exist and handles migration."""
        old_dir = Path.home() / ".config" / "lany-music-cli"
        # Perform silent one-time migration if old config exists but new doesn't
        if old_dir.exists() and not cls.CONFIG_DIR.exists():
            try:
                shutil.copytree(old_dir, cls.CONFIG_DIR)
            except Exception as e:
                log.warning(f"Failed to migrate configuration from {old_dir}: {e}")

        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(cls.CONFIG_DIR, 0o700)
        except Exception as e:
            log.debug(f"Failed to set permissions on config directory: {e}")

        # Periodically clean thumbnail cache files older than 30 days
        try:
            cls.clean_cache(max_age_days=30)
        except Exception as e:
            log.warning(f"Automatic cache cleanup failed: {e}")

    @classmethod
    def get_cache_size(cls) -> tuple[int, int]:
        """Returns a tuple containing the (file_count, total_bytes) of the thumbnail cache."""
        cls.ensure_dirs()
        num_files = 0
        total_bytes = 0
        try:
            for item in cls.CACHE_DIR.iterdir():
                if item.is_file():
                    num_files += 1
                    total_bytes += item.stat().st_size
        except Exception as e:
            log.warning(f"Failed to calculate cache size: {e}")
        return num_files, total_bytes

    @classmethod
    def clean_cache(cls, max_age_days: int = 30):
        """Prunes thumbnail cache files older than max_age_days."""
        if not cls.CACHE_DIR.exists():
            return
        import time
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        pruned_count = 0
        pruned_bytes = 0
        try:
            for item in cls.CACHE_DIR.iterdir():
                if item.is_file():
                    mtime = item.stat().st_mtime
                    if now - mtime > max_age_seconds:
                        size = item.stat().st_size
                        item.unlink()
                        pruned_count += 1
                        pruned_bytes += size
            if pruned_count > 0:
                log.info(f"Cache cleanup complete. Pruned {pruned_count} files ({pruned_bytes / 1024:.1f} KB)")
        except Exception as e:
            log.warning(f"Failed to clean cache: {e}")

    @classmethod
    def load_config(cls) -> dict:
        """Loads config, returns empty dict if file does not exist."""
        cls.ensure_dirs()
        if not cls.CONFIG_FILE.exists():
            return {}
        try:
            with open(cls.CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Failed to load config file: {e}")
            return {}

    @classmethod
    def save_config(cls, data: dict):
        """Saves config data securely (owner-only access)."""
        cls.ensure_dirs()
        try:
            with open(cls.CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            try:
                os.chmod(cls.CONFIG_FILE, 0o600)
            except Exception as e:
                log.debug(f"Failed to set permissions on config file: {e}")
        except Exception as e:
            log.error(f"Error saving config: {e}")

    @classmethod
    def is_authenticated(cls) -> bool:
        """Checks if OAuth file exists and is non-empty."""
        cls.ensure_dirs()
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
