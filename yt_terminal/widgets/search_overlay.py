import asyncio
from textual.screen import Screen
from textual.widgets import Label, Input, ListItem, ListView, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.message import Message
from yt_terminal.music_service import MusicService, Track
from yt_terminal.config_manager import ConfigManager

class SearchOverlay(Screen):
    """Modal overlay screen for searching and playing songs, albums, playlists, and artists."""

    DEFAULT_CSS = """
    SearchOverlay {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #search-box {
        width: 80;
        height: 30;
        border: round #7a5260;
        background: #1c1216;
        padding: 1 2;
        border-title-color: #d38e91;
    }

    .search-title {
        text-align: center;
        color: #d38e91;
        text-style: bold;
        margin-bottom: 1;
    }

    #search-input {
        margin-bottom: 1;
        border: round #7a5260;
        color: #fbe5e6;
        background: #2a1a22;
    }

    #filter-container {
        layout: horizontal;
        align: center middle;
        width: 100%;
        height: 2;
        margin-bottom: 1;
    }

    .filter-btn {
        min-width: 12;
        margin: 0 1;
        background: transparent;
        border: none;
        color: #a68894;
        height: 1;
        padding: 0;
    }

    .filter-btn.active {
        background: transparent;
        color: #fbe5e6;
        border-bottom: solid #d38e91;
        text-style: bold;
        height: 1;
        padding: 0;
    }

    #search-results-list {
        height: 14;
        background: #150d10;
        border: solid #7a5260;
        scrollbar-size: 1 1;
    }

    .search-item-row {
        layout: horizontal;
        padding: 0 1;
        height: 1;
    }

    .search-item-title {
        width: 45%;
        color: #fbe5e6;
        text-overflow: ellipsis;
    }

    .search-item-artist {
        width: 30%;
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
        """Posted when a single song is selected from search results."""
        def __init__(self, track: Track):
            super().__init__()
            self.track = track

    class PlaylistSelected(Message):
        """Posted when an entire playlist or album is selected."""
        def __init__(self, tracks: list[Track]):
            super().__init__()
            self.tracks = tracks

    def __init__(self, music_service: MusicService):
        super().__init__()
        self.ms = music_service
        self.results_tracks = []
        self.current_filter = "songs"
        self.results_type = "recent"  # "recent", "suggestions", "results"
        self.suggestions_list = []
        self.recent_searches = []

    def compose(self):
        # Load search history
        config = ConfigManager.load_config()
        self.recent_searches = config.get("search_history", [])

        with Vertical(id="search-box") as v:
            v.border_title = " SEARCH YT-TERMINAL "
            yield Label("🔍  Find Songs, Albums & Playlists", classes="search-title")
            
            yield Input(
                placeholder="Type song name or keywords...",
                id="search-input"
            )

            # Category filter buttons
            with Horizontal(id="filter-container"):
                yield Button("Songs", id="filter-songs", classes="filter-btn active")
                yield Button("Albums", id="filter-albums", classes="filter-btn")
                yield Button("Playlists", id="filter-playlists", classes="filter-btn")
                yield Button("Artists", id="filter-artists", classes="filter-btn")
            
            with ListView(id="search-results-list") as lv:
                yield ListItem(Label("Loading search history..."))

    def on_mount(self):
        self.query_one("#search-input", Input).focus()
        self.show_recent_searches()

    def show_recent_searches(self):
        """Displays user search history when input is empty."""
        self.results_type = "recent"
        lv = self.query_one("#search-results-list", ListView)
        lv.clear()
        
        if not self.recent_searches:
            lv.append(ListItem(Label("Search history is empty! Start typing above 🔍")))
            return
            
        lv.append(ListItem(Label("[#d38e91]Recent Searches (Click to search again):[/]")))
        for query in self.recent_searches:
            item = ListItem(Label(f"  🕒  {query}"))
            item.query_val = query
            lv.append(item)

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Loads live search suggestions as the user types."""
        query = event.value.strip()
        if not query:
            self.show_recent_searches()
            return

        # Fetch suggestions in background thread
        try:
            self.results_type = "suggestions"
            suggestions = await self.ms.get_search_suggestions(query)
            if self.results_type == "suggestions" and self.query_one("#search-input", Input).value.strip() == query:
                self.suggestions_list = suggestions
                lv = self.query_one("#search-results-list", ListView)
                lv.clear()
                
                if suggestions:
                    for sugg in suggestions[:8]:
                        item = ListItem(Label(f"  💡  {sugg}"))
                        item.query_val = sugg
                        lv.append(item)
                else:
                    lv.append(ListItem(Label("Press Enter to search...")))
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Toggles result filter tabs and triggers search instantly if input exists."""
        button_id = event.button.id
        if button_id.startswith("filter-"):
            # Set active class on active filter tab
            for btn in self.query(".filter-btn"):
                btn.remove_class("active")
            event.button.add_class("active")
            
            self.current_filter = button_id.replace("filter-", "")
            
            # Re-trigger search with new filter
            query = self.query_one("#search-input", Input).value.strip()
            if query:
                await self.perform_search(query)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Trigger search query when Enter is pressed in input field."""
        query = event.value.strip()
        if not query:
            return
        await self.perform_search(query)

    async def perform_search(self, query: str):
        """Runs the search query with the selected filter type."""
        # Save to history list
        if query in self.recent_searches:
            self.recent_searches.remove(query)
        self.recent_searches.insert(0, query)
        self.recent_searches = self.recent_searches[:10]  # Cap at 10
        
        config = ConfigManager.load_config()
        config["search_history"] = self.recent_searches
        ConfigManager.save_config(config)

        self.results_type = "results"
        self.query_one("#search-input", Input).value = query
        lv = self.query_one("#search-results-list", ListView)
        lv.clear()
        
        self.query_one("#search-input", Input).disabled = True
        lv.append(ListItem(Label(f"Searching for {self.current_filter}... Please wait 🔍")))

        try:
            # Map user category filter to standard API filter
            api_filter = self.current_filter
            if api_filter == "artists":
                api_filter = "artists"
            elif api_filter == "playlists":
                api_filter = "playlists"
            elif api_filter == "albums":
                api_filter = "albums"
            else:
                api_filter = "songs"

            tracks = await self.ms.search(query, filter_type=api_filter)
            self.results_tracks = tracks
            lv.clear()

            if not tracks:
                lv.append(ListItem(Label("❌ No results found. Try a different category or search term!")))
            else:
                for i, track in enumerate(tracks):
                    if self.current_filter == "songs":
                        row = Horizontal(
                            Label(track.title, classes="search-item-title"),
                            Label(f" - {track.artist}", classes="search-item-artist"),
                            Label(track.album, classes="search-item-album"),
                            classes="search-item-row"
                        )
                    elif self.current_filter == "albums":
                        row = Horizontal(
                            Label(f"💿 {track.title}", classes="search-item-title"),
                            Label(f" - {track.artist}", classes="search-item-artist"),
                            Label("Album", classes="search-item-album"),
                            classes="search-item-row"
                        )
                    elif self.current_filter == "playlists":
                        row = Horizontal(
                            Label(f"🎶 {track.title}", classes="search-item-title"),
                            Label(f" - {track.artist}", classes="search-item-artist"),
                            Label("Playlist", classes="search-item-album"),
                            classes="search-item-row"
                        )
                    else:  # artists
                        row = Horizontal(
                            Label(f"👤 {track.title}", classes="search-item-title"),
                            Label("Artist page", classes="search-item-artist"),
                            Label("", classes="search-item-album"),
                            classes="search-item-row"
                        )
                    
                    item = ListItem(row)
                    item.track_index = i
                    lv.append(item)
        except Exception as e:
            lv.clear()
            lv.append(ListItem(Label(f"⚠️ Search error: {str(e)}")))
        finally:
            inp = self.query_one("#search-input", Input)
            inp.disabled = False
            inp.focus()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle clicks on list items based on suggestion/recent/result type."""
        item = event.item
        
        if self.results_type in ("recent", "suggestions"):
            if hasattr(item, "query_val"):
                await self.perform_search(item.query_val)
            return

        if hasattr(item, "track_index") and 0 <= item.track_index < len(self.results_tracks):
            selected = self.results_tracks[item.track_index]
            
            # If search filter is songs or artists, just play the single track
            if self.current_filter in ("songs", "artists"):
                self.post_message(self.SongSelected(selected))
                self.dismiss()
            # If selecting album or playlist, fetch all tracks and load into queue
            elif self.current_filter == "albums":
                lv = self.query_one("#search-results-list", ListView)
                lv.clear()
                lv.append(ListItem(Label("Loading all Album tracks... 💿")))
                try:
                    tracks = await self.ms.get_album_tracks(selected.video_id)
                    if tracks:
                        self.post_message(self.PlaylistSelected(tracks))
                except Exception:
                    pass
                self.dismiss()
            elif self.current_filter == "playlists":
                lv = self.query_one("#search-results-list", ListView)
                lv.clear()
                lv.append(ListItem(Label("Loading all Playlist tracks... 🎶")))
                try:
                    tracks = await self.ms.get_playlist_tracks(selected.video_id)
                    if tracks:
                        self.post_message(self.PlaylistSelected(tracks))
                except Exception:
                    pass
                self.dismiss()

    def on_key(self, event) -> None:
        """Escapes the search overlay via Escape."""
        if event.key == "escape":
            self.dismiss()
