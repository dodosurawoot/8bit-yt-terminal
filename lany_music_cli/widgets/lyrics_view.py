# Right-Top Pane: Synced Lyrics View

from textual.widget import Widget
from textual.widgets import Label
from textual.containers import VerticalScroll
from textual.reactive import reactive
from lany_music_cli.mock_data import MOCK_LYRICS

class LyricsView(Widget):
    """Displays scrollable lyrics that sync and highlight based on current playback time."""
    current_time = reactive(0.0)

    def compose(self):
        self.border_title = "Lyrics"
        
        # Scroll container for lyric lines
        with VerticalScroll(id="lyrics-scroll-container"):
            self.lyric_labels = []
            for i, (t, text) in enumerate(MOCK_LYRICS):
                lbl = Label(text or "♪", classes="lyric-line inactive")
                yield lbl
                self.lyric_labels.append(lbl)

    def watch_current_time(self, new_val):
        self.sync_lyrics(new_val)

    def sync_lyrics(self, current_time_seconds):
        if not hasattr(self, "lyric_labels") or not self.lyric_labels:
            return
            
        # Find active lyric index
        active_idx = -1
        for i, (t, text) in enumerate(MOCK_LYRICS):
            if t <= current_time_seconds:
                active_idx = i
            else:
                break
                
        # Update classes and scroll
        for idx, lbl in enumerate(self.lyric_labels):
            if idx == active_idx:
                lbl.add_class("active")
                lbl.remove_class("inactive")
                # Scroll the active lyric line to center screen smoothly
                lbl.scroll_visible(animate=True, top=False)
            else:
                lbl.add_class("inactive")
                lbl.remove_class("active")
