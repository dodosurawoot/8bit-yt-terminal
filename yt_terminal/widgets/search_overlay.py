import asyncio
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Label, Input, ListItem, ListView, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.message import Message
from yt_terminal.music_service import MusicService, Track
from yt_terminal.config_manager import ConfigManager

class SuggestionListItem(ListItem):
    """Subclass representing a search history or live suggestion item."""
    def __init__(self, child: Widget, query_val: str, **kwargs):
        super().__init__(child, **kwargs)
        self.query_val = query_val

class SearchResultListItem(ListItem):
    """Subclass representing a track search result item."""
    def __init__(self, child: Widget, track_index: int, **kwargs):
        super().__init__(child, **kwargs)
        self.track_index = track_index

class SearchOverlay(Screen):
    """Modal overlay screen for searching and playing songs, albums, playlists, and artists."""

    DEFAULT_CSS = """
    SearchOverlay {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #search-box {
        width: 80;
        height: 28;
        border: round #7a5260;
        background: #1c1216;
        padding: 2 4;
        border-title-color: #d38e91;
        overflow: hidden;
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
        height: 3;
        margin-bottom: 1;
        background: #22151b;
    }

    .filter-btn {
        min-width: 16;
        height: 3;
        background: transparent;
        border: none;
        color: #a68894;
        content-align: center middle;
        text-style: bold;
    }

    .filter-btn:hover {
        background: #2d1c25;
        color: #fbe5e6;
        border: none;
    }

    .filter-btn:focus {
        border: none;
    }

    .filter-btn.active {
        background: #d38e91;
        color: #1c1216;
        text-style: bold;
        border: none;
    }

    .filter-btn.active:hover {
        background: #d38e91;
        color: #1c1216;
    }

    .filter-btn.active:focus {
        background: #d38e91;
        color: #1c1216;
        border: none;
    }

    #search-results-list {
        height: 14;
        background: #150d10;
        border: solid #7a5260;
        scrollbar-size: 1 1;
        overflow-x: hidden;
    }

    .search-item-row {
        layout: horizontal;
        padding: 0 1;
        height: 1;
    }

    .search-item-icon {
        width: 3;
        color: #d38e91;
    }

    .search-item-title {
        width: 50%;
        color: #fbe5e6;
        text-overflow: ellipsis;
    }

    .search-item-separator {
        width: 3;
        color: #a68894;
        text-align: center;
    }

    .search-item-artist {
        width: 40%;
        color: #a68894;
        text-overflow: ellipsis;
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
        self._debounce_timer = None

    def compose(self):
        # Load search history
        config = ConfigManager.load_config()
        self.recent_searches = config.get("search_history", [])

        with Vertical(id="search-box") as v:
            v.border_title = " SEARCH YT-TERMINAL "
            
            yield Input(
                placeholder="Find Songs, Albums & Playlists...",
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

    def on_unmount(self) -> None:
        """Saves search history to disk on overlay dismissal."""
        if self._debounce_timer:
            self._debounce_timer.stop()
            self._debounce_timer = None
        try:
            config = ConfigManager.load_config()
            config["search_history"] = self.recent_searches
            ConfigManager.save_config(config)
        except Exception as e:
            log.warning(f"Failed to save search history: {e}")

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
            item = SuggestionListItem(Label(f"  🕒  {query}"), query_val=query)
            lv.append(item)

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Loads live search suggestions as the user types with a 300ms debounce."""
        query = event.value.strip()
        if not query:
            if self._debounce_timer:
                self._debounce_timer.stop()
                self._debounce_timer = None
            self.show_recent_searches()
            return

        # Cancel any pending search suggestion request timer
        if self._debounce_timer:
            self._debounce_timer.stop()
            self._debounce_timer = None

        # Schedule suggestion fetch
        async def do_fetch():
            try:
                self.results_type = "suggestions"
                suggestions = await self.ms.get_search_suggestions(query)
                # Ensure the user hasn't cleared or changed input during network call
                if self.results_type == "suggestions" and self.query_one("#search-input", Input).value.strip() == query:
                    self.suggestions_list = suggestions
                    lv = self.query_one("#search-results-list", ListView)
                    lv.clear()
                    
                    if suggestions:
                        for sugg in suggestions[:8]:
                            item = SuggestionListItem(Label(f"  💡  {sugg}"), query_val=sugg)
                            lv.append(item)
                    else:
                        lv.append(ListItem(Label("Press Enter to search...")))
            except Exception as e:
                log.debug(f"Failed to fetch search suggestions: {e}")

        self._debounce_timer = self.set_timer(0.3, lambda: self.run_worker(do_fetch()))

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
        # Cancel any pending suggestion timers
        if self._debounce_timer:
            self._debounce_timer.stop()
            self._debounce_timer = None

        # Save to history list (write to disk is deferred to on_unmount)
        if query in self.recent_searches:
            self.recent_searches.remove(query)
        self.recent_searches.insert(0, query)
        self.recent_searches = self.recent_searches[:10]  # Cap at 10

        self.results_type = "results"
        self.query_one("#search-input", Input).value = query
        lv = self.query_one("#search-results-list", ListView)
        lv.clear()
        
        self.query_one("#search-input", Input).disabled = True
        lv.append(ListItem(Label(f"Searching for {self.current_filter}... Please wait 🔍")))

        try:
            # Map user category filter to standard API filter
            api_filter = self.current_filter if self.current_filter in ("artists", "playlists", "albums") else "songs"

            tracks = await self.ms.search(query, filter_type=api_filter)
            self.results_tracks = tracks
            lv.clear()

            if not tracks:
                lv.append(ListItem(Label("❌ No results found. Try a different category or search term!")))
            else:
                for i, track in enumerate(tracks):
                    icon_char = "♪"
                    if self.current_filter == "albums":
                        icon_char = "💿"
                    elif self.current_filter == "playlists":
                        icon_char = "🎶"
                    elif self.current_filter == "artists":
                        icon_char = "👤"

                    artist_name = track.artist if track.artist else "Unknown Artist"
                    if self.current_filter == "playlists" and not track.artist:
                        artist_name = "Playlist"
                    elif self.current_filter == "artists":
                        artist_name = "Artist"

                    row = Horizontal(
                        Label(icon_char, classes="search-item-icon"),
                        Label(track.title, classes="search-item-title"),
                        Label(" - ", classes="search-item-separator"),
                        Label(artist_name, classes="search-item-artist"),
                        classes="search-item-row"
                    )
                    
                    item = SearchResultListItem(row, track_index=i)
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
        
        if isinstance(item, SuggestionListItem):
            await self.perform_search(item.query_val)
            return

        if isinstance(item, SearchResultListItem) and 0 <= item.track_index < len(self.results_tracks):
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
                except Exception as e:
                    log.warning(f"Failed to fetch album tracks: {e}")
                self.dismiss()
            elif self.current_filter == "playlists":
                lv = self.query_one("#search-results-list", ListView)
                lv.clear()
                lv.append(ListItem(Label("Loading all Playlist tracks... 🎶")))
                try:
                    tracks = await self.ms.get_playlist_tracks(selected.video_id)
                    if tracks:
                        self.post_message(self.PlaylistSelected(tracks))
                except Exception as e:
                    log.warning(f"Failed to fetch playlist tracks: {e}")
                self.dismiss()

    def on_key(self, event) -> None:
        """Escapes the search overlay via Escape."""
        if event.key == "escape":
            self.dismiss()
