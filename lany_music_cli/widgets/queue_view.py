# Right-Bottom Pane: Up Next Queue View

from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from lany_music_cli.music_service import Track

class QueueItemWidget(Widget):
    """Renders a single song card in the playlist queue."""
    def __init__(self, track_info: Track, **kwargs):
        super().__init__(**kwargs)
        self.track = track_info

    def compose(self):
        with Horizontal(classes="queue-item"):
            # Col 1: Solid block thumbnail indicator
            thumb_label = Label("[#d38e91]███[/]", classes="queue-thumb")
            yield thumb_label
            
            # Col 2: Text details
            with Vertical(classes="queue-details"):
                yield Label(self.track.title, classes="queue-title")
                yield Label(self.track.artist, classes="queue-artist")


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

    async def watch_queue_data(self, new_val):
        """Reactively updates the visual list when queue changes."""
        try:
            lv = self.query_one("#queue-list", ListView)
        except Exception:
            # Widget not fully composed yet
            return

        # Increment counter to generate unique IDs across updates
        QueueView._update_counter += 1
        batch = QueueView._update_counter

        lv.clear()
        self.list_items = []
        
        if not new_val:
            lv.append(ListItem(Label("Queue is empty 🎵")))
            return

        for i, track in enumerate(new_val):
            widget = QueueItemWidget(track)
            # Use batch counter in ID to guarantee uniqueness
            item = ListItem(widget, id=f"qt-{batch}-{i}")
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
