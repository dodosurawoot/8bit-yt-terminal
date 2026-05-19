# Main Application Orchestrator for LANY Music CLI

import os
import sys
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, ListView
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.binding import Binding

from lany_music_cli.widgets.player_pane import PlayerPane
from lany_music_cli.widgets.equalizer_pane import EqualizerPane
from lany_music_cli.widgets.lyrics_view import LyricsView
from lany_music_cli.widgets.queue_view import QueueView
from lany_music_cli.widgets.login_screen import LoginScreen
from lany_music_cli.widgets.search_overlay import SearchOverlay

from lany_music_cli.music_service import MusicService, Track
from lany_music_cli.audio_player import AudioPlayer
from lany_music_cli.theme_engine import download_and_extract, generate_tcss

# Determine standard base asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ART_PATH = os.path.join(BASE_DIR, "assets", "album_art.png")

class LanyMusicApp(App):
    """An Apple Music / Winamp inspired Terminal Media Player."""
    
    CSS_PATH = "style.tcss"
    
    # Global hotkeys including '/' search
    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", show=True),
        Binding("n", "next_track", "Next Track", show=True),
        Binding("p", "prev_track", "Prev Track", show=True),
        Binding("slash", "search_overlay", "Search", show=True),
        Binding("q", "quit", "Quit Player", show=True),
    ]
    
    # Playback Reactives
    active_track_index = reactive(0)
    is_playing = reactive(False)
    current_time = reactive(0.0)
    track_duration = reactive(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ms = MusicService()
        self.player: AudioPlayer | None = None  # Lazy init after login
        self.queue: list[Track] = []
        self._current_track: Track | None = None
        self._asset_task = None
        self._lyrics_task = None
        self._queue_task = None
        self._skip_autoplay_update = False  # Prevent double queue race

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal(id="main-layout"):
            # Col 1: Player Pane (Left)
            self.player_pane = PlayerPane(id="player-pane")
            yield self.player_pane
            
            # Col 2: Equalizer & Visualizer Pane (Center)
            self.eq_pane = EqualizerPane(id="eq-pane")
            yield self.eq_pane
            
            # Col 3: Lyrics & Queue (Right Stacked)
            with Vertical(id="right-pane"):
                self.lyrics_view = LyricsView(id="lyrics-view")
                self.queue_view = QueueView(id="queue-view")
                yield self.lyrics_view
                yield self.queue_view
                
        yield Footer()

    def on_mount(self) -> None:
        """Runs initialization check when TUI loads."""
        if not self.ms.is_authenticated():
            # Trigger first-time Google Device Code Login wizard
            self.push_screen(LoginScreen(self.ms), callback=self.on_login_completed)
        else:
            # Load library automatically
            self.run_worker(self.initialize_library())

    async def on_login_completed(self, success_event=None) -> None:
        """Triggered once LoginScreen authenticates Google account."""
        self.run_worker(self.initialize_library())

    async def initialize_library(self):
        """Fetches initial library tracks (Liked Songs) to populate queue."""
        # Lazy-init AudioPlayer here (after login, not on import)
        if self.player is None:
            self.player = AudioPlayer()

        self.title = "LANY Music CLI > Loading Liked Songs... 🎵"
        
        # Load up to 40 tracks from user Liked library
        liked_tracks = await self.ms.get_liked_songs(limit=40)
        
        if not liked_tracks:
            # Search fallback if Liked list is completely empty
            liked_tracks = await self.ms.search("LANY Malibu Nights")
            
        if liked_tracks:
            self.queue = liked_tracks
            self.queue_view.queue_data = self.queue
            # Skip autoplay queue update on first load to prevent double update race
            self._skip_autoplay_update = True
            self.load_track(0)
        else:
            self.title = "LANY Music CLI > Ready (Press / to search)"

        # Start background polling timer for mpv timeline position
        self.set_interval(0.5, self.update_playback_timeline)

    def load_track(self, index: int):
        """Loads and starts audio streaming for a selected queue track."""
        if not self.queue or not (0 <= index < len(self.queue)):
            return
            
        self.active_track_index = index
        track = self.queue[index]
        self._current_track = track
        
        # Start background asset, lyrics & queue updates in thread pools
        self._cancel_background_tasks()
        self._asset_task = self.run_worker(self.update_track_theme_and_artwork(track))
        self._lyrics_task = self.run_worker(self.update_track_lyrics(track))
        # Only update autoplay queue if not skipped (avoids double-update DuplicateIds)
        if self._skip_autoplay_update:
            self._skip_autoplay_update = False
        else:
            self._queue_task = self.run_worker(self.update_autoplay_queue(track))
        
        # Update left Player widget info
        self.player_pane.track_title = track.title
        self.player_pane.track_artist = track.artist
        self.player_pane.track_album = track.album
        self.player_pane.track_duration = track.duration_seconds
        self.player_pane.track_current_time = 0
        self.player_pane.is_playing = True
        self.player_pane.artwork_path = DEFAULT_ART_PATH
        
        # Stream URL via background mpv process
        if self.player:
            self.player.play_url(f"https://www.youtube.com/watch?v={track.video_id}")
        
        # Sync widget reactives
        self.current_time = 0.0
        self.track_duration = track.duration_seconds
        self.is_playing = True
        self.queue_view.current_index = index
        self.eq_pane.visualizer.anim_active = True
        
        self.title = f"lany-music-cli > now streaming: {track.title} 🎵"

    def _cancel_background_tasks(self):
        """Cancels stale asynchronous requests to avoid thread collisions."""
        if self._asset_task and not self._asset_task.done():
            self._asset_task.cancel()
        if self._lyrics_task and not self._lyrics_task.done():
            self._lyrics_task.cancel()
        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()

    async def update_track_theme_and_artwork(self, track: Track):
        """Downloads thumbnail and generates the extracted album color theme in parallel."""
        if not track.thumbnail_url:
            return
            
        # Download, cache and extract dominant color scheme
        theme_vars = await asyncio.to_thread(download_and_extract, track.thumbnail_url)
        tcss_str = generate_tcss(theme_vars)
        self.stylesheet.add_source(tcss_str)
        
        # Locate path of cached thumbnail using config hash
        import hashlib
        from lany_music_cli.config_manager import ConfigManager
        url_hash = hashlib.md5(track.thumbnail_url.encode("utf-8")).hexdigest()
        cache_path = ConfigManager.CACHE_DIR / f"{url_hash}.jpg"
        
        if cache_path.exists():
            self.player_pane.artwork_path = str(cache_path)

    async def update_track_lyrics(self, track: Track):
        """Loads lyrics from YouTube Music API asynchronously."""
        lyrics = await self.ms.get_lyrics(track.video_id)
        self.lyrics_view.lyrics_data = lyrics

    async def update_autoplay_queue(self, track: Track):
        """Pulls Autoplay/Up Next queue list from active track."""
        next_tracks = await self.ms.get_up_next_queue(track.video_id)
        if next_tracks:
            # Splice in active track at start followed by autoplay suggestions
            self.queue = [track] + next_tracks
            self.queue_view.queue_data = self.queue
            self.active_track_index = 0
            self.queue_view.current_index = 0

    def update_playback_timeline(self):
        """Queries background mpv process for position and checks song ends."""
        if not self.is_playing or not self._current_track:
            return
            
        if not self.player:
            return
        pos = self.player.get_position()
        dur = self.player.get_duration() or self._current_track.duration_seconds
        
        self.current_time = pos
        self.player_pane.track_current_time = int(pos)
        self.lyrics_view.current_time = pos
        
        # Auto-advance to next song if active song finishes
        if dur > 0 and pos >= (dur - 1.0):
            self.action_next_track()

    # --- Hotkey Actions ---

    def action_toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.player:
            self.player.set_pause(not self.is_playing)
        self.player_pane.is_playing = self.is_playing
        self.eq_pane.visualizer.anim_active = self.is_playing

    def action_next_track(self) -> None:
        if self.queue and len(self.queue) > 1:
            next_idx = (self.active_track_index + 1) % len(self.queue)
            self.load_track(next_idx)

    def action_prev_track(self) -> None:
        if self.queue and len(self.queue) > 1:
            prev_idx = (self.active_track_index - 1) % len(self.queue)
            self.load_track(prev_idx)

    def action_search_overlay(self) -> None:
        """Opens search modal overlay."""
        self.push_screen(SearchOverlay(self.ms))

    def action_quit(self) -> None:
        """Terminates background play processes safely before exiting."""
        if self.player:
            self.player.quit()
        self.exit()

    # --- Widget Event Listeners ---

    def on_player_pane_play_toggle(self, message: PlayerPane.PlayToggle) -> None:
        self.action_toggle_play()

    def on_player_pane_next_track(self, message: PlayerPane.NextTrack) -> None:
        self.action_next_track()

    def on_player_pane_prev_track(self, message: PlayerPane.PrevTrack) -> None:
        self.action_prev_track()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Triggers playlist/queue track jumps on song card click."""
        item = event.item
        if hasattr(item, "track") and hasattr(item, "track_index"):
            self.load_track(item.track_index)

    def on_search_overlay_song_selected(self, message: SearchOverlay.SongSelected) -> None:
        """Plays search selection immediately and seeds dynamic queue."""
        self.queue = [message.track]
        self.queue_view.queue_data = self.queue
        self.load_track(0)

def main():
    app = LanyMusicApp()
    app.run()

if __name__ == "__main__":
    main()
