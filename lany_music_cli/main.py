# Main Application Orchestrator for LANY Music CLI

import os
import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.binding import Binding

from lany_music_cli.widgets.player_pane import PlayerPane
from lany_music_cli.widgets.equalizer_pane import EqualizerPane
from lany_music_cli.widgets.lyrics_view import LyricsView
from lany_music_cli.widgets.queue_view import QueueView

from lany_music_cli.mock_data import MOCK_QUEUE
from lany_music_cli.theme_engine import extract_palette, generate_tcss

# Determine standard base asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ART_PATH = os.path.join(BASE_DIR, "assets", "album_art.png")

class LanyMusicApp(App):
    """An Apple Music / Winamp inspired Terminal Media Player."""
    
    # Custom stylesheet
    CSS_PATH = "style.tcss"
    
    # Global hotkeys
    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", show=True),
        Binding("n", "next_track", "Next Track", show=True),
        Binding("p", "prev_track", "Prev Track", show=True),
        Binding("q", "quit", "Quit Player", show=True),
    ]
    
    # Playback Reactives
    active_track_index = reactive(0)
    is_playing = reactive(True)
    current_time = reactive(0)

    def compose(self) -> ComposeResult:
        # Top titlebar (includes custom clock option)
        yield Header(show_clock=True)
        
        # Grid Main Layout
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
                
        # Statusbar
        yield Footer()

    def on_mount(self) -> None:
        """Run on initial widget mounting."""
        # 1. Apply Dynamic Artwork Theme
        theme_vars = extract_palette(ART_PATH)
        tcss_str = generate_tcss(theme_vars)
        self.stylesheet.add_source(tcss_str)
        
        # 2. Configure default first track state
        self.load_track(0)
        
        # 3. Start simulated audio playback loop (1 second interval)
        self.set_interval(1.0, self.update_playback_time)

    def load_track(self, index):
        """Loads track info into active state and updates widgets."""
        if not (0 <= index < len(MOCK_QUEUE)):
            return
            
        self.active_track_index = index
        track = MOCK_QUEUE[index]
        
        # Populate left player pane
        self.player_pane.track_title = track["title"]
        self.player_pane.track_artist = track["artist"]
        self.player_pane.track_album = track["album"]
        self.player_pane.track_duration = track["duration"]
        self.player_pane.track_current_time = track["current_time"]
        self.player_pane.bitrate = track["bitrate"]
        self.player_pane.artwork_path = ART_PATH
        
        # Sync reactive timer
        self.current_time = track["current_time"]
        
        # Update queue highlight selection
        self.queue_view.current_index = index
        
        # Update bottom footer status message
        title_str = track["title"]
        self.title = f"lany-music-cli v1.2.0 > now playing: {title_str}"

    def update_playback_time(self):
        """Simulate audio time progress."""
        if not self.is_playing:
            return
            
        track = MOCK_QUEUE[self.active_track_index]
        duration = track["duration"]
        
        if self.current_time < duration:
            self.current_time += 1
            self.player_pane.track_current_time = self.current_time
            self.lyrics_view.current_time = self.current_time
        else:
            # Song finished -> auto-play next track in loop
            self.action_next_track()

    # Hotkey Action Handlers
    def action_toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        self.player_pane.is_playing = self.is_playing
        # Pause/resume visualizer animations
        self.eq_pane.visualizer.anim_active = self.is_playing

    def action_next_track(self) -> None:
        next_idx = (self.active_track_index + 1) % len(MOCK_QUEUE)
        # Reset track time on change
        MOCK_QUEUE[next_idx]["current_time"] = 0
        self.load_track(next_idx)

    def action_prev_track(self) -> None:
        prev_idx = (self.active_track_index - 1) % len(MOCK_QUEUE)
        MOCK_QUEUE[prev_idx]["current_time"] = 0
        self.load_track(prev_idx)

    # Left Player Pane Event Message Handlers
    def on_player_pane_play_toggle(self, message: PlayerPane.PlayToggle) -> None:
        self.action_toggle_play()

    def on_player_pane_next_track(self, message: PlayerPane.NextTrack) -> None:
        self.action_next_track()

    def on_player_pane_prev_track(self, message: PlayerPane.PrevTrack) -> None:
        self.action_prev_track()

def main():
    app = LanyMusicApp()
    app.run()

if __name__ == "__main__":
    main()
