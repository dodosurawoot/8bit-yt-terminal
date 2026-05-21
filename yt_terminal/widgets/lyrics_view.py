# Right-Top Pane: Synced Lyrics View

import bisect
from textual.widget import Widget
from textual.widgets import Label
from textual.containers import VerticalScroll
from textual.reactive import reactive

class LyricsView(Widget):
    """Displays scrollable lyrics that sync and highlight based on current playback time."""
    current_time = reactive(0.0)
    lyrics_data = reactive(list)  # List of {"start": float, "text": str}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lyric_labels = []
        self._lyric_times = []
        self._last_active_idx = -1

    def compose(self):
        self.border_title = "Lyrics"
        with VerticalScroll(id="lyrics-scroll-container"):
            self.lyric_labels = []
            lbl = Label("No song playing 🎵", classes="lyric-line inactive")
            yield lbl
            self.lyric_labels.append(lbl)

    async def watch_lyrics_data(self, new_val):
        """Reactively updates the lyrics screen when the track data updates."""
        if not self.lyric_labels:
            # Still empty/initializing
            pass

        try:
            container = self.query_one("#lyrics-scroll-container")
        except Exception as e:
            log.warning(f"Could not locate lyrics container: {e}")
            return

        # Safely remove existing lyrics labels
        try:
            for lbl in list(self.lyric_labels):
                await lbl.remove()
        except Exception as e:
            log.debug(f"Failed to remove stale lyrics: {e}")

        self.lyric_labels = []
        self._lyric_times = [item.get("start", 0.0) for item in new_val] if new_val else []
        self._last_active_idx = -1
        
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

    def _update_label_class(self, idx, active_idx):
        if idx < 0 or idx >= len(self.lyric_labels):
            return
        lbl = self.lyric_labels[idx]
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

    def sync_lyrics(self, current_time_seconds):
        if not self.lyric_labels or not self.lyrics_data:
            return
            
        # Find active lyric index using binary search (O(log n))
        active_idx = bisect.bisect_right(self._lyric_times, current_time_seconds) - 1
        
        # Only update DOM if the active lyric index has changed
        if active_idx == self._last_active_idx:
            return
            
        old_idx = self._last_active_idx
        self._last_active_idx = active_idx
        
        # Determine the set of indices that need their class updated
        indices_to_update = set()
        if old_idx != -1:
            indices_to_update.update({old_idx - 1, old_idx, old_idx + 1})
        if active_idx != -1:
            indices_to_update.update({active_idx - 1, active_idx, active_idx + 1})
            
        for idx in indices_to_update:
            self._update_label_class(idx, active_idx)

