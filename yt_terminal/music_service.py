import asyncio
import os
import json
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from ytmusicapi import YTMusic, OAuthCredentials
from yt_terminal.config_manager import ConfigManager

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
        self._init_client()

    def _init_client(self):
        """Initializes the YTMusic client if credentials exist."""
        ConfigManager.ensure_dirs()
        if ConfigManager.is_authenticated():
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
        """Gets tracks from a playlist."""
        if not self.yt:
            return []
        try:
            playlist = await asyncio.to_thread(self.yt.get_playlist, playlist_id, limit=limit)
            return self._parse_tracks(playlist.get("tracks", []))
        except Exception:
            return []

    async def search(self, query: str, filter_type: str = "songs") -> List[Track]:
        """Searches YouTube Music for tracks."""
        if not self.yt:
            return []
        try:
            results = await asyncio.to_thread(self.yt.search, query, filter=filter_type, limit=20)
            return self._parse_tracks(results)
        except Exception:
            return []

    async def get_search_suggestions(self, query: str) -> List[str]:
        """Gets autocomplete search recommendations from YouTube Music."""
        if not self.yt or not query.strip():
            return []
        try:
            return await asyncio.to_thread(self.yt.get_search_suggestions, query)
        except Exception:
            return []

    async def get_album_tracks(self, album_id: str) -> List[Track]:
        """Gets individual tracks listed within a YouTube Music album."""
        if not self.yt:
            return []
        try:
            album = await asyncio.to_thread(self.yt.get_album, album_id)
            return self._parse_tracks(album.get("tracks", []))
        except Exception:
            return []

    async def get_up_next_queue(self, video_id: str) -> List[Track]:
        """Gets the autoplay/related songs queue from watch playlist."""
        if not self.yt:
            return []
        try:
            watch_data = await asyncio.to_thread(self.yt.get_watch_playlist, videoId=video_id, limit=15)
            return self._parse_tracks(watch_data.get("tracks", []))
        except Exception:
            return []

    async def get_lyrics(self, video_id: str) -> List[Dict[str, Any]]:
        """Gets synced or static lyrics. Returns timed line dicts if possible."""
        if not self.yt:
            return []
            
        try:
            # First, check if watch playlist has lyrics browseId
            watch_data = await asyncio.to_thread(self.yt.get_watch_playlist, videoId=video_id)
            lyrics_id = watch_data.get("lyrics")
            if not lyrics_id:
                return []
                
            raw_lyrics = await asyncio.to_thread(self.yt.get_lyrics, lyrics_id)
            text = raw_lyrics.get("lyrics", "")
            
            # YouTube Music standard API returns plain static lyrics.
            # We split by line and add mock timestamps that progress roughly with song.
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            parsed_lines = []
            
            # Simple progressive timestamp estimation if they are not pre-timed
            duration = watch_data.get("tracks", [{}])[0].get("duration_seconds", 180)
            if not duration:
                duration = 180
            time_per_line = max(1.5, min(6.0, duration / max(1, len(lines))))
            
            for i, line in enumerate(lines):
                start = i * time_per_line
                parsed_lines.append({
                    "start": start,
                    "text": line
                })
            return parsed_lines
        except Exception:
            return []

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
