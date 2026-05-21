# Main Application Orchestrator for YT-Terminal

import os
import sys
import asyncio
import logging
import time
import hashlib
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(
    filename="/tmp/yt-terminal.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("yt-terminal")
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, ListView
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.binding import Binding

from yt_terminal.widgets.player_pane import PlayerPane
from yt_terminal.widgets.equalizer_pane import EqualizerPane
from yt_terminal.widgets.lyrics_view import LyricsView
from yt_terminal.widgets.queue_view import QueueView
from yt_terminal.widgets.login_screen import LoginScreen
from yt_terminal.widgets.search_overlay import SearchOverlay

from yt_terminal.music_service import MusicService, Track
from yt_terminal.audio_player import AudioPlayer
from yt_terminal.theme_engine import download_and_extract, generate_tcss

# Determine standard base asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ART_PATH = os.path.join(BASE_DIR, "assets", "album_art.png")

class YTTerminalApp(App):
    """A modern YouTube Music terminal player with 8-bit art and Winamp spectrum."""
    
    CSS_PATH = "style.tcss"
    
    # Global hotkeys including '/' search
    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", show=True),
        Binding("n", "next_track", "Next Track", show=True),
        Binding("p", "prev_track", "Prev Track", show=True),
        Binding("l", "toggle_lyrics_fullscreen", "Full Lyrics", show=True),
        Binding("w", "toggle_art_lyrics", "Lyrics + Art", show=True),
        Binding("slash", "search_overlay", "Search", show=True),
        Binding("a", "sync_account", "Sync Account", show=True),
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

    def on_resize(self, event) -> None:
        """Dynamically adjusts layout when the terminal is resized."""
        try:
            width = event.size.width
            if width < 80:
                self.player_pane.display = True
                self.eq_pane.display = False
                self.query_one("#right-pane").display = False
            elif width < 120:
                self.player_pane.display = True
                self.eq_pane.display = False
                self.query_one("#right-pane").display = True
            else:
                self.player_pane.display = True
                self.eq_pane.display = True
                self.query_one("#right-pane").display = True
        except Exception:
            pass

    def on_mount(self) -> None:
        """Runs initialization check when TUI loads."""
        log.info("App mounted. Checking authentication...")
        if not self.ms.is_authenticated():
            log.info("Not authenticated — showing login screen")
            self.push_screen(LoginScreen(self.ms), callback=self.on_login_completed)
        else:
            log.info("Authenticated — loading library")
            self.run_worker(self.initialize_library())

    async def on_login_completed(self, success_event=None) -> None:
        """Triggered once LoginScreen authenticates Google account."""
        log.info("Login completed successfully")
        self.run_worker(self.initialize_library())

    async def initialize_library(self):
        """Fetches initial library tracks (Liked Songs) to populate queue."""
        # Lazy-init AudioPlayer here (after login, not on import)
        if self.player is None:
            self.player = AudioPlayer()

        self.title = "YT-Terminal > Loading Liked Songs... 🎵"
        
        # Load up to 40 tracks from user Liked library
        liked_tracks = await self.ms.get_liked_songs(limit=40)
        log.info(f"Liked songs loaded: {len(liked_tracks)} tracks")
        
        if not liked_tracks:
            log.info("No liked songs — falling back to search")
            liked_tracks = await self.ms.search("LANY Malibu Nights")
            
        if liked_tracks:
            self.queue = liked_tracks
            self.queue_view.queue_data = self.queue
            self._skip_autoplay_update = True
            self.load_track(0)
        else:
            log.warning("No tracks found at all")
            self.title = "YT-Terminal > Ready (Press / to search)"

        # Start background polling timer for mpv timeline position
        self.set_interval(0.5, self.update_playback_timeline)

    def load_track(self, index: int):
        """Loads and starts audio streaming for a selected queue track."""
        if not self.queue or not (0 <= index < len(self.queue)):
            log.warning(f"load_track({index}) — out of range or empty queue")
            return
            
        self.active_track_index = index
        track = self.queue[index]
        self._current_track = track
        self._last_track_load_time = time.time()
        log.info(f"▶ Playing [{index}]: {track.title} — {track.artist} (id={track.video_id})")
        
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
        
        self.title = f"YT-Terminal > Now Streaming: {track.title} 🎵"

    def _cancel_background_tasks(self):
        """Cancels stale asynchronous requests to avoid thread collisions."""
        if self._asset_task and not self._asset_task.is_finished:
            self._asset_task.cancel()
        if self._lyrics_task and not self._lyrics_task.is_finished:
            self._lyrics_task.cancel()
        if self._queue_task and not self._queue_task.is_finished:
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
            # DON'T reset active_track_index here — it causes cascade re-plays
            self.queue_view.current_index = 0

    def update_playback_timeline(self):
        """Queries background mpv process for position and checks song ends."""
        if not self.is_playing or not self._current_track:
            return
            
        if not self.player:
            return

        pos = self.player.get_position()
        dur = self.player.get_duration() or self._current_track.duration_seconds

        # Avoid temporary 0.0 read glitches from mpv during stream buffering
        if pos == 0.0 and self.current_time > 2.0:
            now = time.time()
            if not (hasattr(self, '_last_track_load_time') and (now - self._last_track_load_time) < 8.0):
                pos = self.current_time

        # Only update live duration if we are out of the 8-second initial loading period
        now = time.time()
        is_loading = hasattr(self, '_last_track_load_time') and (now - self._last_track_load_time) < 8.0

        if not is_loading and dur and dur > 0:
            self.track_duration = dur
            self.player_pane.track_duration = dur

        # Buffer & Cooldown Protection Guard
        # During the first 8 seconds after loading, we filter out stale positions
        # and ignore auto-advance checks while mpv buffers the network stream.
        if is_loading:
            if pos > 5.0:
                # Stale position from previous track while mpv buffers the new stream
                pos = 0.0
            
            # Sync timeline using buffered position
            self.current_time = pos
            self.player_pane.track_current_time = int(pos)
            self.lyrics_view.current_time = pos
            return

        self.current_time = pos
        self.player_pane.track_current_time = int(pos)
        self.lyrics_view.current_time = pos
        
        # Auto-advance to next song if active song finishes
        # Require dur > 10 to avoid false positives from mpv returning 0
        if dur > 10 and pos >= (dur - 1.0):
            log.info(f"Track finished (pos={pos:.1f}, dur={dur:.1f}) — advancing to next track")
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

    def action_toggle_lyrics_fullscreen(self) -> None:
        """Toggles immersive full-screen lyrics mode."""
        try:
            layout = self.query_one("#main-layout")
            layout.remove_class("expanded-art-lyrics-active")
            layout.toggle_class("fullscreen-lyrics-active")
        except Exception:
            pass

    def action_toggle_art_lyrics(self) -> None:
        """Toggles Apple Music style expanded album art with lyrics mode."""
        try:
            layout = self.query_one("#main-layout")
            layout.remove_class("fullscreen-lyrics-active")
            layout.toggle_class("expanded-art-lyrics-active")
        except Exception:
            pass

    def action_sync_account(self) -> None:
        """Triggers manual YouTube Music authentication / Re-sync screen."""
        log.info("User triggered manual sync / login screen")
        # Pause active player first if playing to release audio device resources
        if self.player:
            try:
                self.player.set_pause(True)
                self.is_playing = False
                self.player_pane.is_playing = False
                self.eq_pane.visualizer.anim_active = False
            except Exception:
                pass
        
        self.push_screen(LoginScreen(self.ms), callback=self.on_login_completed)

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

    def on_search_overlay_playlist_selected(self, message: SearchOverlay.PlaylistSelected) -> None:
        """Loads and plays all album or playlist tracks."""
        if message.tracks:
            self.queue = message.tracks
            self.queue_view.queue_data = self.queue
            self.load_track(0)

def main():
    app = YTTerminalApp()
    app.run()

if __name__ == "__main__":
    main()
