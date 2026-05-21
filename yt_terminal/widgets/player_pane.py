# Left Pane Widget: Artwork, Track Info, Progress & Controls

import os
import time
import math
from PIL import Image
from textual.widget import Widget
from textual.widgets import Label, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.message import Message

from rich.text import Text

def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"

class AlbumArt(Widget):
    """Renders the album art image as retro 8-bit colored pixel art."""
    image_path = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_size = (0, 0)
        self._last_path = None
        self._cached_rendered_art = None

    def render(self) -> Text:
        w = self.content_size.width
        h = self.content_size.height
        
        # Fallback if dimensions are 0 (e.g. before mount/layout)
        if w <= 0 or h <= 0:
            w, h = 32, 12
            
        path = self.image_path
        
        # If cache is valid, return cached Text object
        if (w, h) == self._last_size and path == self._last_path and self._cached_rendered_art is not None:
            return self._cached_rendered_art
            
        self._last_size = (w, h)
        self._last_path = path
        
        if not path or not os.path.exists(path):
            fallback_text = (
                "\n"
                "   .------.  \n"
                "  /   YT   \\ \n"
                " |  (O)(O)  |\n"
                " |    ||    |\n"
                "  \\  '--'  / \n"
                "   '------'  \n"
                "  [NO COVER] "
            )
            self._cached_rendered_art = Text(fallback_text)
            return self._cached_rendered_art
            
        try:
            img = Image.open(path)
            # Standard square album art aspect ratio fits in character cells
            # height is in rows, which is half-blocks, so 1 row = 2 pixels high.
            pixel_w = w
            pixel_h = h * 2
            
            # Find largest square that fits within the available width and height
            side = min(pixel_w, pixel_h)
            if side < 4:
                side = 4
                
            img = img.resize((side, side), Image.Resampling.NEAREST)
            # Quantize color palette to 16 colors for dithered/retro console look
            img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16).convert("RGB")
            
            lines = []
            pixels = img.load()
            for y in range(side // 2):
                line_markup = []
                for x in range(side):
                    top_rgb = pixels[x, 2 * y]
                    bottom_rgb = pixels[x, 2 * y + 1]
                    line_markup.append(
                        f"[rgb({top_rgb[0]},{top_rgb[1]},{top_rgb[2]}) on rgb({bottom_rgb[0]},{bottom_rgb[1]},{bottom_rgb[2]})]▀[/]"
                    )
                lines.append("".join(line_markup))
            self._cached_rendered_art = Text.from_markup("\n".join(lines))
        except Exception as e:
            self._cached_rendered_art = Text(f"\n\n Error loading art:\n {str(e)}")
            
        return self._cached_rendered_art

class PlayerPane(Widget):
    """The Left Pane showing active song info, artwork, and control bindings."""
    
    # Define custom messages to communicate playback status to main app
    class PlayToggle(Message):
        pass
    class NextTrack(Message):
        pass
    class PrevTrack(Message):
        pass
    class ShuffleToggle(Message):
        pass
    class RepeatToggle(Message):
        pass

    track_title = reactive("No Track")
    track_artist = reactive("—")
    track_album = reactive("—")
    track_duration = reactive(0)
    track_current_time = reactive(0)
    bitrate = reactive("Hi-Res Lossless")
    artwork_path = reactive("")
    is_playing = reactive(True)
    shuffle_mode = reactive(False)
    repeat_mode = reactive("off")  # "off", "one", "all"
    volume_level = reactive(80)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.album_art = None
        self.title_lbl = None
        self.artist_lbl = None
        self.volume_lbl = None
        self.play_time_lbl = None
        self.progress_track = None
        self.rem_time_lbl = None
        self.bitrate_lbl = None
        self.play_btn = None

    def compose(self):
        self.border_title = "Now Playing"
        
        # Album Art
        self.album_art = AlbumArt()
        yield self.album_art
        
        # Track details
        self.title_lbl = Label(self.track_title, classes="track-title")
        self.artist_lbl = Label(f"{self.track_artist} — {self.track_album}", classes="track-artist")
        yield self.title_lbl
        yield self.artist_lbl
        
        # Favorite button, Volume indicator & Options menu row
        with Horizontal(id="favorite-and-menu"):
            yield Label("★", id="favorite-btn")
            self.volume_lbl = Label("🔊 80%", id="volume-lbl")
            yield self.volume_lbl
            yield Label("•••", id="menu-btn")
            
        # Progress Bar / Time Indicators
        with Horizontal(id="progress-container"):
            self.play_time_lbl = Label("2:32", id="play-time")
            self.progress_track = Label("━━━━━━━●━━━━", id="progress-track")
            self.rem_time_lbl = Label("-0:49", id="remaining-time")
            yield self.play_time_lbl
            yield self.progress_track
            yield self.rem_time_lbl
            
        # Bitrate Quality Badge
        with Horizontal(id="bitrate-container"):
            self.bitrate_lbl = Label(self.bitrate, id="bitrate-badge")
            yield self.bitrate_lbl
            
        # Unicode Media controls row
        with Horizontal(id="media-controls"):
            yield Button("SHF", id="shuffle-btn")
            yield Button("⏮", id="prev-btn")
            self.play_btn = Button("⏸" if self.is_playing else "▶", id="play-btn")
            yield self.play_btn
            yield Button("⏭", id="next-btn")
            yield Button("RPT", id="repeat-btn")

    def watch_track_title(self, new_val):
        if self.title_lbl is not None:
            self.title_lbl.update(new_val)

    def watch_track_artist(self, new_val):
        if self.artist_lbl is not None:
            self.artist_lbl.update(f"{new_val} — {self.track_album}")

    def watch_track_album(self, new_val):
        if self.artist_lbl is not None:
            self.artist_lbl.update(f"{self.track_artist} — {new_val}")

    def watch_bitrate(self, new_val):
        if self.bitrate_lbl is not None:
            self.bitrate_lbl.update(new_val)

    def watch_artwork_path(self, new_val):
        if self.album_art is not None:
            self.album_art.image_path = new_val

    def watch_is_playing(self, new_val):
        if self.play_btn is not None:
            self.play_btn.label = "⏸" if new_val else "▶"

    def watch_shuffle_mode(self, new_val: bool):
        try:
            btn = self.query_one("#shuffle-btn", Button)
            if new_val:
                btn.add_class("active")
            else:
                btn.remove_class("active")
        except Exception as e:
            log.debug(f"Failed to update shuffle button styles: {e}")

    def watch_repeat_mode(self, new_val: str):
        try:
            btn = self.query_one("#repeat-btn", Button)
            btn.remove_class("active-all", "active-one")
            if new_val == "all":
                btn.add_class("active-all")
                btn.label = "RPT"
            elif new_val == "one":
                btn.add_class("active-one")
                btn.label = "RP1"
            else:
                btn.label = "RPT"
        except Exception as e:
            log.debug(f"Failed to update repeat button styles: {e}")

    def watch_volume_level(self, new_val: int):
        if self.volume_lbl is not None:
            icon = "🔊"
            if new_val == 0:
                icon = "🔇"
            elif new_val < 30:
                icon = "🔈"
            elif new_val < 70:
                icon = "🔉"
            self.volume_lbl.update(f"{icon} {new_val}%")

    def watch_track_current_time(self, new_val):
        self.update_progress_ui()

    def watch_track_duration(self, new_val):
        self.update_progress_ui()

    def update_progress_ui(self):
        if self.play_time_lbl is None:
            return
        curr_str = _format_time(self.track_current_time)
        rem_seconds = max(0, self.track_duration - self.track_current_time)
        rem_str = f"-{_format_time(rem_seconds)}"
        
        self.play_time_lbl.update(curr_str)
        self.rem_time_lbl.update(rem_str)
        
        # Calculate dynamic track characters with higher resolution (22 chars)
        total_chars = 22
        percent = min(1.0, max(0.0, self.track_current_time / self.track_duration)) if self.track_duration > 0 else 0
        dot_pos = int(percent * (total_chars - 1))
        
        # Calculate dynamic glowing head color that 'breathes' based on time
        t = time.time()
        pulse = 0.5 + 0.5 * math.sin(t * 4.0) # Breathes 4 times a second
        if pulse > 0.75:
            head_color = "#ffffff" # Bright hot-spot glow
        elif pulse > 0.35:
            head_color = "#00f3ff" # Cyber Cyan
        else:
            head_color = "#0088cc" # Deep ocean pulse
            
        parts = []
        for x in range(total_chars):
            if x < dot_pos:
                # Fading gradient track: interpolates from deep ocean blue to neon cyan trail
                ratio = x / dot_pos if dot_pos > 0 else 0
                if ratio < 0.25:
                    col = "#002277" # Deep blue base
                elif ratio < 0.5:
                    col = "#0044bb"
                elif ratio < 0.75:
                    col = "#0077ff"
                else:
                    col = "#00d4ff" # Cyan light trail
                parts.append(f"[{col}]━[/]")
            elif x == dot_pos:
                parts.append(f"[bold {head_color}]●[/]")
            else:
                # Unplayed section: dim translucent dark gray
                parts.append("[#262938]━[/]")
                
        track_markup = "".join(parts)
        self.progress_track.update(Text.from_markup(track_markup))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "play-btn":
            self.post_message(self.PlayToggle())
        elif button_id == "next-btn":
            self.post_message(self.NextTrack())
        elif button_id == "prev-btn":
            self.post_message(self.PrevTrack())
        elif button_id == "shuffle-btn":
            self.post_message(self.ShuffleToggle())
        elif button_id == "repeat-btn":
            self.post_message(self.RepeatToggle())
