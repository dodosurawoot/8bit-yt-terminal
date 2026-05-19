# Right-Bottom Pane: Up Next Queue View

from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from lany_music_cli.mock_data import MOCK_QUEUE

class QueueItemWidget(Widget):
    """Renders a single song card in the playlist queue."""
    def __init__(self, track_info, **kwargs):
        super().__init__(**kwargs)
        self.track = track_info

    def compose(self):
        with Horizontal(classes="queue-item"):
            # Col 1: Small solid color square acting as album art thumbnail
            color = self.track.get("color", "#d38e91")
            thumb_label = Label(f"[{color}]███[/]", classes="queue-thumb")
            yield thumb_label
            
            # Col 2: Text detail info
            with Vertical(classes="queue-details"):
                yield Label(self.track["title"], classes="queue-title")
                yield Label(self.track["artist"], classes="queue-artist")

class QueueView(Widget):
    """Displays the upcoming tracks queue list and handle track change messages."""
    
    current_index = reactive(0)

    def compose(self):
        self.border_title = "Up Next / AutoPlay"
        
        # autoplay header layout
        with Horizontal(id="queue-header"):
            yield Label("∞ AutoPlay ON", id="autoplay-lbl")
            
        with ListView(id="queue-list"):
            self.list_items = []
            for i, track in enumerate(MOCK_QUEUE):
                item = ListItem(QueueItemWidget(track), id=f"queue-track-{i}")
                yield item
                self.list_items.append(item)

    def watch_current_index(self, new_val):
        self.highlight_current_track(new_val)

    def highlight_current_track(self, index):
        if not hasattr(self, "list_items") or not self.list_items:
            return
            
        for i, item in enumerate(self.list_items):
            if i == index:
                item.add_class("active-track")
                # Scroll highlighted item visible
                item.scroll_visible(animate=True)
            else:
                item.remove_class("active-track")
