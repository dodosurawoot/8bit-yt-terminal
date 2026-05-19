import asyncio
import os
import json
import requests
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from ytmusicapi import YTMusic, OAuthCredentials
from yt_terminal.config_manager import ConfigManager

log = logging.getLogger("yt-terminal")

class Track:
    """Unified Track representation for TUI player."""
    def __init__(
        self,
        video_id: str,
        title: str,
        artist: str,
        album: str,
        duration_seconds: int,
        thumbnail_url: str = "",
        lyrics_id: Optional[str] = None
    ):
        self.video_id = video_id
        self.title = title
        self.artist = artist
        self.album = album
        self.duration_seconds = duration_seconds
        self.thumbnail_url = thumbnail_url
        self.lyrics_id = lyrics_id

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url
        }


class MusicService:
    """Headless API Service wrapping ytmusicapi securely using async thread pools."""
    
    def __init__(self):
        self.yt: Optional[YTMusic] = None
        self.yt_public = YTMusic()  # Clean unauthenticated public fallback
        self._init_client()

    def _init_client(self):
        """Initializes the YTMusic client if credentials exist."""
        ConfigManager.ensure_dirs()
        if ConfigManager.is_authenticated():
            # Self-healing OAUTH_FILE parse to strip unsupported 'refresh_token_expires_in' key
            if ConfigManager.OAUTH_FILE.exists():
                try:
                    import json
                    with open(ConfigManager.OAUTH_FILE, "r") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "refresh_token_expires_in" in data:
                        del data["refresh_token_expires_in"]
                        with open(ConfigManager.OAUTH_FILE, "w") as f:
                            json.dump(data, f, indent=4)
                except Exception:
                    pass

            client_id, client_secret = ConfigManager.get_credentials()
            try:
                if client_id and client_secret:
                    # Initialize authenticated client with OAuthCredentials
                    self.yt = YTMusic(
                        str(ConfigManager.OAUTH_FILE),
                        oauth_credentials=OAuthCredentials(client_id, client_secret)
                    )
                else:
                    self.yt = YTMusic(str(ConfigManager.OAUTH_FILE))
            except Exception:
                # If loading authenticated client fails, fall back to unauthenticated
                self.yt = YTMusic()
        else:
            self.yt = YTMusic()

    def is_authenticated(self) -> bool:
        """Returns True if the client is authenticated."""
        return ConfigManager.is_authenticated()

    # --- Authentication (OAuth Flow) ---

    async def get_oauth_code(self, client_id: str, client_secret: str) -> dict:
        """Starts device code authorization flow."""
        def _get_code():
            creds = OAuthCredentials(client_id, client_secret)
            return creds.get_code()
        
        return await asyncio.to_thread(_get_code)

    async def poll_oauth_token(self, client_id: str, client_secret: str, device_code: str) -> dict:
        """Polls for OAuth token, returns token dict or raises exception if pending."""
        def _poll():
            creds = OAuthCredentials(client_id, client_secret)
            return creds.token_from_code(device_code)
            
        return await asyncio.to_thread(_poll)

    async def save_oauth_session(self, client_id: str, client_secret: str, token_data: dict):
        """Saves client credentials and OAuth token to disk."""
        ConfigManager.ensure_dirs()
        ConfigManager.save_credentials(client_id, client_secret)
        
        def _save():
            # Write token_data out directly as oauth.json
            with open(ConfigManager.OAUTH_FILE, "w") as f:
                json.dump(token_data, f, indent=4)
                
        await asyncio.to_thread(_save)
        self._init_client()

    # --- API Endpoints ---

    async def get_library_playlists(self) -> List[Dict[str, Any]]:
        """Gets user's library playlists."""
        if not self.is_authenticated() or not self.yt:
            return []
        try:
            return await asyncio.to_thread(self.yt.get_library_playlists, limit=25)
        except Exception:
            return []

    async def get_liked_songs(self, limit: int = 30) -> List[Track]:
        """Gets user's Liked Songs library playlist."""
        if not self.is_authenticated() or not self.yt:
            return []
        try:
            raw_liked = await asyncio.to_thread(self.yt.get_liked_songs, limit=limit)
            return self._parse_tracks(raw_liked.get("tracks", []))
        except Exception:
            return []

    async def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> List[Track]:
        """Gets tracks from a playlist with robust public fallback."""
        if self.yt:
            try:
                playlist = await asyncio.to_thread(self.yt.get_playlist, playlist_id, limit=limit)
                return self._parse_tracks(playlist.get("tracks", []))
            except Exception as e:
                log.warning(f"Authenticated get_playlist failed ({e}) — falling back to public client")

        try:
            playlist = await asyncio.to_thread(self.yt_public.get_playlist, playlist_id, limit=limit)
            return self._parse_tracks(playlist.get("tracks", []))
        except Exception:
            return []

    async def search(self, query: str, filter_type: str = "songs") -> List[Track]:
        """Searches YouTube Music for tracks with robust public fallback."""
        if self.yt:
            try:
                results = await asyncio.to_thread(self.yt.search, query, filter=filter_type, limit=20)
                return self._parse_tracks(results)
            except Exception as e:
                log.warning(f"Authenticated search failed ({e}) — falling back to public client")

        try:
            results = await asyncio.to_thread(self.yt_public.search, query, filter=filter_type, limit=20)
            return self._parse_tracks(results)
        except Exception:
            return []

    async def get_search_suggestions(self, query: str) -> List[str]:
        """Gets autocomplete search recommendations with robust public fallback."""
        if not query.strip():
            return []
        if self.yt:
            try:
                return await asyncio.to_thread(self.yt.get_search_suggestions, query)
            except Exception as e:
                log.warning(f"Authenticated suggestions failed ({e}) — falling back to public client")
        
        try:
            return await asyncio.to_thread(self.yt_public.get_search_suggestions, query)
        except Exception:
            return []

    async def get_album_tracks(self, album_id: str) -> List[Track]:
        """Gets individual tracks listed within a YouTube Music album with robust public fallback."""
        if self.yt:
            try:
                album = await asyncio.to_thread(self.yt.get_album, album_id)
                return self._parse_tracks(album.get("tracks", []))
            except Exception as e:
                log.warning(f"Authenticated get_album failed ({e}) — falling back to public client")

        try:
            album = await asyncio.to_thread(self.yt_public.get_album, album_id)
            return self._parse_tracks(album.get("tracks", []))
        except Exception:
            return []

    async def get_up_next_queue(self, video_id: str) -> List[Track]:
        """Gets the autoplay/related songs queue from watch playlist with robust public fallback."""
        if self.yt:
            try:
                watch_data = await asyncio.to_thread(self.yt.get_watch_playlist, videoId=video_id, limit=15)
                return self._parse_tracks(watch_data.get("tracks", []))
            except Exception as e:
                log.warning(f"Authenticated get_watch_playlist failed ({e}) — falling back to public client")

        try:
            watch_data = await asyncio.to_thread(self.yt_public.get_watch_playlist, videoId=video_id, limit=15)
            return self._parse_tracks(watch_data.get("tracks", []))
        except Exception:
            return []

    async def get_lyrics(self, video_id: str) -> List[Dict[str, Any]]:
        """Gets synced or static lyrics with robust public fallback."""
        watch_data = None
        if self.yt:
            try:
                watch_data = await asyncio.to_thread(self.yt.get_watch_playlist, videoId=video_id)
            except Exception as e:
                log.warning(f"Authenticated get_watch_playlist for lyrics failed ({e}) — falling back to public client")

        if not watch_data:
            try:
                watch_data = await asyncio.to_thread(self.yt_public.get_watch_playlist, videoId=video_id)
            except Exception:
                return []

        lyrics_id = watch_data.get("lyrics")
        if not lyrics_id:
            return []

        raw_lyrics = None
        if self.yt:
            try:
                raw_lyrics = await asyncio.to_thread(self.yt.get_lyrics, lyrics_id)
            except Exception as e:
                log.warning(f"Authenticated get_lyrics failed ({e}) — falling back to public client")

        if not raw_lyrics:
            try:
                raw_lyrics = await asyncio.to_thread(self.yt_public.get_lyrics, lyrics_id)
            except Exception:
                return []

        try:
            text = raw_lyrics.get("lyrics", "")
            return self._parse_lyrics_from_watch_and_text(watch_data, text)
        except Exception:
            return []

    def _parse_lyrics_from_watch_and_text(self, watch_data: dict, text: str) -> List[Dict[str, Any]]:
        """Utility helper to estimate line timings cleanly with LRC parser support."""
        if not text:
            return []
            
        import re
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # Check if lyrics contain LRC-style timestamps [mm:ss.xx] or [mm:ss]
        lrc_pattern = re.compile(r"^\[(\d+):(\d+)(?:\.(\d+))?\](.*)$")
        has_lrc = False
        parsed_lines = []
        
        for line in lines:
            match = lrc_pattern.match(line)
            if match:
                has_lrc = True
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                ms = int(match.group(3)) if match.group(3) else 0
                start_time = minutes * 60 + seconds + (ms / 100.0 if ms < 100 else ms / 1000.0)
                content = match.group(4).strip()
                parsed_lines.append({
                    "start": start_time,
                    "text": content
                })
                
        if has_lrc and parsed_lines:
            parsed_lines.sort(key=lambda x: x["start"])
            return parsed_lines
            
        # Fallback to smart estimated timeline with opening instrumental delay
        parsed_lines = []
        duration = watch_data.get("tracks", [{}])[0].get("duration_seconds", 180)
        if not duration or duration <= 0:
            duration = 180
            
        # Apply a natural opening instrumental buffer (e.g., 8 seconds or 8% of song)
        intro_delay = min(10.0, duration * 0.08)
        usable_duration = max(30.0, duration - intro_delay)
        time_per_line = max(1.5, min(6.0, usable_duration / max(1, len(lines))))
        
        for i, line in enumerate(lines):
            start = intro_delay + (i * time_per_line)
            parsed_lines.append({
                "start": start,
                "text": line
            })
        return parsed_lines

    # --- Utility Parsing Helpers ---

    def _parse_tracks(self, raw_tracks: List[Dict[str, Any]]) -> List[Track]:
        """Maps raw API responses into high-quality unified Track models."""
        parsed = []
        for track in raw_tracks:
            video_id = track.get("videoId")
            if not video_id:
                # Fallback for album/playlist browse IDs in search results
                video_id = track.get("browseId") or track.get("playlistId")
                
            if not video_id:
                continue
                
            title = track.get("title", "Unknown Track")
            
            # Parse artist name
            artists = track.get("artists", [])
            if isinstance(artists, list) and artists:
                artist = ", ".join([a.get("name", "Unknown") for a in artists if a.get("name")])
            elif isinstance(artists, str):
                artist = artists
            else:
                artist = "Unknown Artist"
                
            # Parse album name
            album_data = track.get("album")
            if isinstance(album_data, dict):
                album = album_data.get("name", "Unknown Album")
            elif isinstance(album_data, str):
                album = album_data
            else:
                album = "Single"

            # Parse duration
            duration_sec = track.get("duration_seconds", 0)
            if not duration_sec and "duration" in track:
                parts = str(track["duration"]).split(":")
                try:
                    if len(parts) == 2:
                        duration_sec = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except ValueError:
                    duration_sec = 0

            # Get largest thumbnail URL
            thumbnails = track.get("thumbnails", [])
            thumb_url = ""
            if thumbnails:
                # Use largest resolution available
                sorted_thumbs = sorted(thumbnails, key=lambda x: x.get("width", 0), reverse=True)
                thumb_url = sorted_thumbs[0].get("url", "")

            parsed.append(Track(
                video_id=video_id,
                title=title,
                artist=artist,
                album=album,
                duration_seconds=duration_sec or 180,
                thumbnail_url=thumb_url
            ))
        return parsed
