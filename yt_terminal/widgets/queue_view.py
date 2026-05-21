

# Right-Bottom Pane: Up Next Queue View

from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from yt_terminal.music_service import Track

import logging
import hashlib
log = logging.getLogger("yt-terminal")

class TrackListItem(ListItem):
    """Structured subclass representing a track item in a list."""
    def __init__(self, child: Widget, track: Track, track_index: int, **kwargs):
        super().__init__(child, **kwargs)
        self.track = track
        self.track_index = track_index

class QueueItemWidget(Widget):
    """Renders a single song card in the playlist queue."""
    def __init__(self, track_info: Track, **kwargs):
        super().__init__(**kwargs)
        self.track = track_info

    def compose(self):
        # Generate stable dynamic pastel color from track metadata
        track_str = f"{self.track.title or ''}-{self.track.artist or ''}"
        h = hashlib.md5(track_str.encode("utf-8")).hexdigest()
        # Generate premium warm colors (100-227 range)
        r = int(h[0:2], 16) % 128 + 100
        g = int(h[2:4], 16) % 128 + 100
        b = int(h[4:6], 16) % 128 + 100
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        
        with Horizontal(classes="queue-item"):
            # Col 1: Solid block color thumbnail indicator
            thumb_label = Label(f"[{hex_color}]███[/]", classes="queue-thumb")
            yield thumb_label
            
            # Col 2: Text details
            with Vertical(classes="queue-details"):
                yield Label(self.track.title or "Unknown Track", classes="queue-title")
                yield Label(self.track.artist or "Unknown Artist", classes="queue-artist")


class QueueView(Widget):
    """Displays the upcoming tracks queue list."""
    queue_data = reactive(list)  # List of Track objects
    current_index = reactive(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_items = []
        self._last_active_idx = -1

    def compose(self):
        self.border_title = "Up Next / AutoPlay"
        
        with Horizontal(id="queue-header"):
            yield Label("∞ AutoPlay ON", id="autoplay-lbl")
            
        yield ListView(id="queue-list")
        self.list_items = []

    def on_mount(self) -> None:
        """Called when the widget is mounted. Populates the queue if data is already loaded."""
        self.run_worker(self.watch_queue_data(self.queue_data))

    async def watch_queue_data(self, new_val):
        """Reactively updates the visual list when queue changes."""
        log.info(f"[QueueView] watch_queue_data triggered with {len(new_val) if new_val else 0} items")
        try:
            lv = self.query_one("#queue-list", ListView)
        except Exception as e:
            log.warning(f"[QueueView] failed to find #queue-list: {e}")
            return

        # Clear existing items safely
        try:
            lv.clear()
            log.info("[QueueView] Cleared #queue-list successfully using lv.clear()")
        except Exception as e:
            log.warning(f"[QueueView] lv.clear() failed: {e}")
            # Fallback manual removal
            try:
                for child in list(lv.children):
                    await child.remove()
            except Exception:
                pass

        self.list_items = []
        self._last_active_idx = -1
        
        if not new_val:
            log.info("[QueueView] queue_data is empty, appending empty message")
            lv.append(ListItem(Label("Queue is empty 🎵")))
            return

        log.info(f"[QueueView] Appending {len(new_val)} tracks to ListView")
        for i, track in enumerate(new_val):
            widget = QueueItemWidget(track)
            item = TrackListItem(widget, track=track, track_index=i)
            lv.append(item)
            self.list_items.append(item)

        log.info(f"[QueueView] Successfully populated ListView with {len(self.list_items)} items")
        self.highlight_current_track(self.current_index)

    def watch_current_index(self, new_val):
        self.highlight_current_track(new_val)

    def highlight_current_track(self, index):
        if not hasattr(self, "list_items") or not self.list_items:
            return
            
        if index < 0 or index >= len(self.list_items):
            return

        old_idx = self._last_active_idx
        self._last_active_idx = index

        # Remove active class from previous item
        if old_idx != -1 and old_idx < len(self.list_items):
            try:
                self.list_items[old_idx].remove_class("active-track")
            except Exception:
                pass

        # Add active class to new item and scroll it into view
        try:
            item = self.list_items[index]
            item.add_class("active-track")
            item.scroll_visible(animate=True)
        except Exception:
            pass
