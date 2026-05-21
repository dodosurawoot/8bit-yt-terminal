# Main Application Orchestrator for YT-Terminal

import os
import tempfile
import asyncio
import logging
import time
from yt_terminal.config_manager import ConfigManager

logging.basicConfig(
    filename=os.path.join(tempfile.gettempdir(), "yt-terminal.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("yt-terminal")
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.binding import Binding

from yt_terminal.widgets.player_pane import PlayerPane
from yt_terminal.widgets.equalizer_pane import EqualizerPane
from yt_terminal.widgets.lyrics_view import LyricsView
from yt_terminal.widgets.queue_view import QueueView
from yt_terminal.widgets.login_screen import LoginScreen
from yt_terminal.widgets.search_overlay import SearchOverlay
from yt_terminal.widgets.app_footer import AppFooter

from yt_terminal.music_service import MusicService, Track
from yt_terminal.audio_player import AudioPlayer
from yt_terminal.theme_engine import download_and_extract, generate_tcss
from yt_terminal.presets import DEFAULT_FALLBACK_TRACKS

# Determine standard base asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ART_PATH = os.path.join(BASE_DIR, "assets", "album_art.png")

class YTTerminalApp(App):
    """A modern YouTube Music terminal player with 8-bit art and Winamp spectrum."""
    
    CSS_PATH = "style.tcss"
    
    # Global hotkeys including '/' search
    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", show=False),
        Binding("n", "next_track", "Next Track", show=False),
        Binding("p", "prev_track", "Prev Track", show=False),
        Binding("l", "toggle_lyrics_fullscreen", "Full Lyrics", show=False),
        Binding("w", "toggle_art_lyrics", "Lyrics + Art", show=False),
        Binding("slash", "search_overlay", "Search", show=False),
        Binding("a", "sync_account", "Sync Account", show=False),
        Binding("plus", "volume_up", "Vol +", show=False),
        Binding("minus", "volume_down", "Vol -", show=False),
        Binding("q,ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+p", "command_palette", "palette", show=False),
    ]
    
    # Playback Reactives
    active_track_index = reactive(0)
    is_playing = reactive(False)
    current_time = reactive(0.0)
    track_duration = reactive(0.0)
    shuffle_mode = reactive(False)
    repeat_mode = reactive("off")
    volume_level = reactive(80)

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
        self._last_track_load_time = 0.0

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
                
        yield AppFooter()

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
        except Exception as e:
            log.debug(f"Error in on_resize: {e}")

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
            
        if not liked_tracks:
            log.info("Search fallback returned 0 tracks — seeding curated default tracks")
            liked_tracks = DEFAULT_FALLBACK_TRACKS

        if liked_tracks:
            # Sync initial volumes and states to pane and player
            if hasattr(self, "player_pane") and self.player_pane:
                self.player_pane.shuffle_mode = self.shuffle_mode
                self.player_pane.repeat_mode = self.repeat_mode
                self.player_pane.volume_level = self.volume_level
            if self.player:
                self.player.set_volume(self.volume_level)

            self.queue = liked_tracks
            self.queue_view.queue_data = self.queue
            self._skip_autoplay_update = True
            self.load_track(0)
        else:
            log.warning("No tracks found at all")
            self.title = "YT-Terminal > Ready (Press / to search)"

        # Start background polling timer for mpv timeline position
        self.set_interval(0.5, self.update_playback_timeline)
        # Start background visualizer feeding at 25 FPS
        self.set_interval(0.04, self.feed_visualizer)

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
        
        art_path = theme_vars.get("artwork_path", "")
        if art_path and os.path.exists(art_path):
            self.player_pane.artwork_path = art_path

    async def update_track_lyrics(self, track: Track):
        """Loads lyrics from YouTube Music API asynchronously."""
        lyrics = await self.ms.get_lyrics(track.video_id)
        self.lyrics_view.lyrics_data = lyrics

    async def update_autoplay_queue(self, track: Track):
        """Pulls Autoplay/Up Next queue list from active track without discarding current queue."""
        # Only fetch/update autoplay if:
        # 1. The queue has only 1 track (single song selection) OR
        # 2. We are playing the last song of the current queue (to append next recommendations)
        if len(self.queue) > 1 and self.active_track_index < len(self.queue) - 1:
            log.info("[Autoplay] Playing middle of queue. Autoplay fetch skipped to preserve queue.")
            return

        log.info(f"[Autoplay] Fetching suggestions for: {track.title}")
        next_tracks = await self.ms.get_up_next_queue(track.video_id)
        if not next_tracks:
            return

        if len(self.queue) <= 1:
            # Single song playing: replace queue with [active track] + suggestions
            self.queue = [track] + next_tracks
            self.queue_view.queue_data = self.queue
            self.queue_view.current_index = 0
            log.info(f"[Autoplay] Single track queue populated with {len(self.queue)} tracks.")
        else:
            # Multi-song queue, and we are playing the last song: append suggestions (filtering out duplicates)
            existing_ids = {t.video_id for t in self.queue}
            appended_count = 0
            new_tracks = []
            for t in next_tracks:
                if t.video_id not in existing_ids:
                    new_tracks.append(t)
                    existing_ids.add(t.video_id)
                    appended_count += 1
            
            if new_tracks:
                self.queue = self.queue + new_tracks
                self.queue_view.queue_data = self.queue
                # Keep current index correct
                self.queue_view.current_index = self.active_track_index
                log.info(f"[Autoplay] Appended {appended_count} recommendations to the end of the queue.")

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
            if not ((now - self._last_track_load_time) < 8.0):
                pos = self.current_time

        # Only update live duration if we are out of the 8-second initial loading period
        now = time.time()
        is_loading = (now - self._last_track_load_time) < 8.0

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
            self.action_next_track(is_auto_advance=True)

    def watch_shuffle_mode(self, val: bool) -> None:
        if hasattr(self, "player_pane") and self.player_pane:
            self.player_pane.shuffle_mode = val

    def watch_repeat_mode(self, val: str) -> None:
        if hasattr(self, "player_pane") and self.player_pane:
            self.player_pane.repeat_mode = val

    def watch_volume_level(self, val: int) -> None:
        if hasattr(self, "player_pane") and self.player_pane:
            self.player_pane.volume_level = val

    def feed_visualizer(self) -> None:
        """Feeds the live mpv audio levels to the spectrum visualizer at a fast interval."""
        if not self.is_playing or not self.player:
            if hasattr(self, "eq_pane") and self.eq_pane and hasattr(self.eq_pane, "visualizer") and self.eq_pane.visualizer:
                self.eq_pane.visualizer.audio_level = 0.0
                self.eq_pane.visualizer.is_playing = False
            return

        amp = self.player.get_audio_level()
        if hasattr(self, "eq_pane") and self.eq_pane and hasattr(self.eq_pane, "visualizer") and self.eq_pane.visualizer:
            self.eq_pane.visualizer.audio_level = amp
            self.eq_pane.visualizer.is_playing = True

    # --- Hotkey Actions ---

    def action_toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.player:
            self.player.set_pause(not self.is_playing)
        self.player_pane.is_playing = self.is_playing
        self.eq_pane.visualizer.anim_active = self.is_playing

    def action_next_track(self, is_auto_advance: bool = False) -> None:
        if not self.queue:
            return

        if is_auto_advance and self.repeat_mode == "one":
            log.info("Auto-advance: repeat_mode is 'one', replaying current track")
            self.load_track(self.active_track_index)
            return

        if self.shuffle_mode and len(self.queue) > 1:
            import random
            choices = [i for i in range(len(self.queue)) if i != self.active_track_index]
            next_idx = random.choice(choices)
            log.info(f"Shuffle mode active: selected random track index {next_idx}")
            self.load_track(next_idx)
        else:
            next_idx = self.active_track_index + 1
            if next_idx >= len(self.queue):
                if self.repeat_mode == "all":
                    log.info("Queue wrapped around (repeat_mode='all')")
                    self.load_track(0)
                else:
                    # repeat_mode == "off"
                    if is_auto_advance:
                        log.info("Queue finished (repeat_mode='off') — pausing playback gracefully")
                        self.is_playing = False
                        if self.player:
                            self.player.set_pause(True)
                        self.player_pane.is_playing = False
                        self.eq_pane.visualizer.anim_active = False
                    else:
                        log.info("Manual next at end of queue — wrap around to index 0")
                        self.load_track(0)
            else:
                self.load_track(next_idx)

    def action_prev_track(self) -> None:
        if not self.queue:
            return

        if self.shuffle_mode and len(self.queue) > 1:
            import random
            choices = [i for i in range(len(self.queue)) if i != self.active_track_index]
            prev_idx = random.choice(choices)
            log.info(f"Shuffle mode active: selected random track index {prev_idx} for prev track")
            self.load_track(prev_idx)
        else:
            prev_idx = self.active_track_index - 1
            if prev_idx < 0:
                prev_idx = len(self.queue) - 1
                log.info("Manual prev at start of queue — wrap around to end")
            self.load_track(prev_idx)

    def action_volume_up(self) -> None:
        if self.player:
            new_vol = min(100, self.volume_level + 5)
            self.player.set_volume(new_vol)
            self.volume_level = new_vol
            log.info(f"Volume increased to {new_vol}%")

    def action_volume_down(self) -> None:
        if self.player:
            new_vol = max(0, self.volume_level - 5)
            self.player.set_volume(new_vol)
            self.volume_level = new_vol
            log.info(f"Volume decreased to {new_vol}%")

    def action_search_overlay(self) -> None:
        """Opens search modal overlay."""
        self.push_screen(SearchOverlay(self.ms))

    def action_toggle_lyrics_fullscreen(self) -> None:
        """Toggles immersive full-screen lyrics mode."""
        try:
            layout = self.query_one("#main-layout")
            layout.remove_class("expanded-art-lyrics-active")
            layout.toggle_class("fullscreen-lyrics-active")
        except Exception as e:
            log.debug(f"Failed to toggle fullscreen lyrics: {e}")

    def action_toggle_art_lyrics(self) -> None:
        """Toggles Apple Music style expanded album art with lyrics mode."""
        try:
            layout = self.query_one("#main-layout")
            layout.remove_class("fullscreen-lyrics-active")
            layout.toggle_class("expanded-art-lyrics-active")
        except Exception as e:
            log.debug(f"Failed to toggle art lyrics: {e}")

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
            except Exception as e:
                log.debug(f"Failed to pause player before sync: {e}")
        
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

    def on_player_pane_shuffle_toggle(self, message: PlayerPane.ShuffleToggle) -> None:
        self.shuffle_mode = not self.shuffle_mode
        log.info(f"Shuffle mode toggled: {self.shuffle_mode}")

    def on_player_pane_repeat_toggle(self, message: PlayerPane.RepeatToggle) -> None:
        if self.repeat_mode == "off":
            self.repeat_mode = "all"
        elif self.repeat_mode == "all":
            self.repeat_mode = "one"
        else:
            self.repeat_mode = "off"
        log.info(f"Repeat mode toggled: {self.repeat_mode}")

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
