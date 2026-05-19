from textual.screen import Screen
from textual.widgets import Label, Input, ListItem, ListView
from textual.containers import Vertical, Horizontal
from textual.message import Message
from lany_music_cli.music_service import MusicService, Track

class SearchOverlay(Screen):
    """Modal overlay screen for searching and playing songs from YouTube Music."""

    DEFAULT_CSS = """
    SearchOverlay {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #search-box {
        width: 70;
        height: 25;
        border: thick #7a5260;
        background: #4f313c;
        padding: 1 2;
    }

    .search-title {
        text-align: center;
        color: #d38e91;
        text-style: bold;
        margin-bottom: 1;
    }

    #search-input {
        margin-bottom: 1;
        border: tall #7a5260;
        color: #fbe5e6;
    }

    #search-results-list {
        height: 14;
        background: #432832;
        border: solid #7a5260;
        scrollbar-size: 1;
    }

    .search-item-row {
        layout: horizontal;
        padding: 0 1;
        height: 1;
    }

    .search-item-title {
        width: 40%;
        color: #fbe5e6;
        text-overflow: ellipsis;
    }

    .search-item-artist {
        width: 35%;
        color: #a68894;
        text-overflow: ellipsis;
    }

    .search-item-album {
        width: 25%;
        color: #a68894;
        text-overflow: ellipsis;
        text-align: right;
    }
    """

    class SongSelected(Message):
        """Posted when a song is selected from search results."""
        def __init__(self, track: Track):
            super().__init__()
            self.track = track

    def __init__(self, music_service: MusicService):
        super().__init__()
        self.ms = music_service
        self.results_tracks = []

    def compose(self):
        with Vertical(id="search-box") as v:
            v.border_title = " SEARCH YOUTUBE MUSIC "
            yield Label("🔍  Find Songs & Playlists", classes="search-title")
            yield Input(
                placeholder="Type song name and press Enter to search...",
                id="search-input"
            )
            
            # Start with an empty list and a help prompt
            with ListView(id="search-results-list") as lv:
                yield ListItem(Label("No search results yet. Type above and press Enter!"))

    def on_mount(self):
        # Auto-focus the search bar immediately
        self.query_one("#search-input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Trigger search query when Enter is pressed in input field."""
        query = event.value.strip()
        if not query:
            return

        lv = self.query_one("#search-results-list", ListView)
        lv.clear()
        
        # Display search progress
        self.query_one("#search-input", Input).disabled = True
        lv.append(ListItem(Label("Searching YouTube Music... Please wait 🔍")))

        try:
            tracks = await self.ms.search(query)
            self.results_tracks = tracks
            lv.clear()

            if not tracks:
                lv.append(ListItem(Label("❌ No results found. Try a different search term!")))
            else:
                for i, track in enumerate(tracks):
                    # Make a beautiful single line row matching visual columns
                    row = Horizontal(
                        Label(track.title, classes="search-item-title"),
                        Label(f" - {track.artist}", classes="search-item-artist"),
                        Label(track.album, classes="search-item-album"),
                        classes="search-item-row"
                    )
                    
                    item = ListItem(row)
                    # Bind index to list item
                    item.track_index = i
                    lv.append(item)
        except Exception as e:
            lv.clear()
            lv.append(ListItem(Label(f"⚠️ Search error: {str(e)}")))
        finally:
            inp = self.query_one("#search-input", Input)
            inp.disabled = False
            inp.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Select a song item to play."""
        item = event.item
        if hasattr(item, "track_index") and 0 <= item.track_index < len(self.results_tracks):
            selected_track = self.results_tracks[item.track_index]
            self.post_message(self.SongSelected(selected_track))
            self.dismiss()

    def on_key(self, event) -> None:
        """Allow escaping the search overlay with Escape."""
        if event.key == "escape":
            self.dismiss()
