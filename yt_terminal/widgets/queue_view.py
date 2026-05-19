# Right-Bottom Pane: Up Next Queue View

from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from yt_terminal.music_service import Track

class QueueItemWidget(Widget):
    """Renders a single song card in the playlist queue."""
    def __init__(self, track_info: Track, **kwargs):
        super().__init__(**kwargs)
        self.track = track_info

    def compose(self):
        # Generate stable dynamic pastel color from track metadata
        import hashlib
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
    queue_data = reactive([])  # List of Track objects
    current_index = reactive(0)
    _update_counter = 0  # Unique ID counter to avoid DuplicateIds

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
        try:
            lv = self.query_one("#queue-list", ListView)
        except Exception:
            # Widget not fully composed yet
            return

        # Remove all existing children explicitly and await each removal
        # to ensure DOM is fully clean before inserting new items.
        # lv.clear() alone is NOT synchronous — old nodes linger and cause DuplicateIds.
        try:
            for child in list(lv.children):
                await child.remove()
        except Exception:
            pass

        self.list_items = []
        
        if not new_val:
            lv.append(ListItem(Label("Queue is empty 🎵")))
            return

        for i, track in enumerate(new_val):
            widget = QueueItemWidget(track)
            # No static ID — let Textual auto-generate unique IDs to avoid all collisions
            item = ListItem(widget)
            item.track = track
            item.track_index = i
            lv.append(item)
            self.list_items.append(item)

        self.highlight_current_track(self.current_index)

    def watch_current_index(self, new_val):
        self.highlight_current_track(new_val)

    def highlight_current_track(self, index):
        if not hasattr(self, "list_items") or not self.list_items:
            return
            
        for i, item in enumerate(self.list_items):
            if i == index:
                item.add_class("active-track")
                item.scroll_visible(animate=True)
            else:
                item.remove_class("active-track")
