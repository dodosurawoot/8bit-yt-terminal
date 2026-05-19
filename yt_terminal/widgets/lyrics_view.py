# Right-Top Pane: Synced Lyrics View

from textual.widget import Widget
from textual.widgets import Label
from textual.containers import VerticalScroll
from textual.reactive import reactive

class LyricsView(Widget):
    """Displays scrollable lyrics that sync and highlight based on current playback time."""
    current_time = reactive(0.0)
    lyrics_data = reactive([])  # List of {"start": float, "text": str}

    def compose(self):
        self.border_title = "Lyrics"
        with VerticalScroll(id="lyrics-scroll-container"):
            self.lyric_labels = []
            lbl = Label("No song playing 🎵", classes="lyric-line inactive")
            yield lbl
            self.lyric_labels.append(lbl)

    async def watch_lyrics_data(self, new_val):
        """Reactively updates the lyrics screen when the track data updates."""
        if not hasattr(self, "lyric_labels"):
            return

        try:
            container = self.query_one("#lyrics-scroll-container")
        except Exception:
            return

        # Safely remove existing lyrics labels
        try:
            for lbl in list(self.lyric_labels):
                await lbl.remove()
        except Exception:
            pass

        self.lyric_labels = []
        
        if not new_val:
            lbl = Label("Instrumental or no lyrics available 🎵", classes="lyric-line inactive")
            await container.mount(lbl)
            self.lyric_labels.append(lbl)
            return

        for item in new_val:
            text = item.get("text", "")
            lbl = Label(text or "♪", classes="lyric-line inactive")
            await container.mount(lbl)
            self.lyric_labels.append(lbl)

    def watch_current_time(self, new_val):
        self.sync_lyrics(new_val)

    def sync_lyrics(self, current_time_seconds):
        if not hasattr(self, "lyric_labels") or not self.lyric_labels or not self.lyrics_data:
            return
            
        # Find active lyric index
        active_idx = -1
        for i, item in enumerate(self.lyrics_data):
            t = item.get("start", 0.0)
            if t <= current_time_seconds:
                active_idx = i
            else:
                break
                
        # Update classes and scroll with three-tier proximity gradient
        for idx, lbl in enumerate(self.lyric_labels):
            d = abs(idx - active_idx)
            
            if d == 0:
                # Target active line
                lbl.remove_class("near-active", "inactive")
                lbl.add_class("active")
                # Scroll active lyric line to center screen smoothly
                lbl.scroll_visible(animate=True, top=False)
            elif d == 1:
                # Proximity 1: near-active
                lbl.remove_class("active", "inactive")
                lbl.add_class("near-active")
            else:
                # Proximity 2+: inactive
                lbl.remove_class("active", "near-active")
                lbl.add_class("inactive")
