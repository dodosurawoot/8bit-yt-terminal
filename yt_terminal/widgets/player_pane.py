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

class AlbumArt(Widget):
    """Renders the album art image as retro 8-bit colored pixel art."""
    image_path = reactive(None)
    rendered_art = reactive(None)

    def watch_image_path(self, new_path: str | None) -> None:
        """Reactively pre-renders the artwork when the path changes."""
        self.rendered_art = self._pre_render(new_path)

    def _pre_render(self, path: str | None) -> Text:
        if not path or not os.path.exists(path):
            fallback_text = (
                "\n\n"
                "   .------.  \n"
                "  /   YT   \\ \n"
                " |  (O)(O)  |\n"
                " |    ||    |\n"
                "  \\  '--'  / \n"
                "   '------'  \n"
                "  [NO COVER] "
            )
            return Text(fallback_text)
        
        try:
            # Open image, downscale and quantize colors for 8-bit styling
            img = Image.open(path)
            w, h = 32, 24
            img = img.resize((w, h), Image.Resampling.NEAREST)
            # Quantize color palette to 16 colors for dithered/retro console look
            img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16).convert("RGB")
            
            lines = []
            for y in range(12):  # 12 character lines, representing 24 pixel vertical lines
                line_markup = []
                for x in range(w):
                    top_rgb = img.getpixel((x, 2 * y))
                    bottom_rgb = img.getpixel((x, 2 * y + 1))
                    line_markup.append(
                        f"[rgb({top_rgb[0]},{top_rgb[1]},{top_rgb[2]}) on rgb({bottom_rgb[0]},{bottom_rgb[1]},{bottom_rgb[2]})]▀[/]"
                    )
                lines.append("  " + "".join(line_markup))
            return Text.from_markup("\n".join(lines))
        except Exception as e:
            return Text(f"\n\n Error loading art:\n {str(e)}")

    def render(self) -> Text:
        if self.rendered_art is None:
            self.rendered_art = self._pre_render(self.image_path)
        return self.rendered_art

class PlayerPane(Widget):
    """The Left Pane showing active song info, artwork, and control bindings."""
    
    # Define custom messages to communicate playback status to main app
    class PlayToggle(Message):
        pass
    class NextTrack(Message):
        pass
    class PrevTrack(Message):
        pass

    track_title = reactive("No Track")
    track_artist = reactive("—")
    track_album = reactive("—")
    track_duration = reactive(201)
    track_current_time = reactive(152)
    bitrate = reactive("Hi-Res Lossless")
    artwork_path = reactive("")
    is_playing = reactive(True)

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
        
        # Favorite button & Options menu row
        with Horizontal(id="favorite-and-menu"):
            yield Label("★", id="favorite-btn")
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
        if hasattr(self, "title_lbl"):
            self.title_lbl.update(new_val)

    def watch_track_artist(self, new_val):
        if hasattr(self, "artist_lbl"):
            self.artist_lbl.update(f"{new_val} — {self.track_album}")

    def watch_track_album(self, new_val):
        if hasattr(self, "artist_lbl"):
            self.artist_lbl.update(f"{self.track_artist} — {new_val}")

    def watch_bitrate(self, new_val):
        if hasattr(self, "bitrate_lbl"):
            self.bitrate_lbl.update(new_val)

    def watch_artwork_path(self, new_val):
        if hasattr(self, "album_art"):
            self.album_art.image_path = new_val

    def watch_is_playing(self, new_val):
        if hasattr(self, "play_btn"):
            self.play_btn.label = "⏸" if new_val else "▶"

    def watch_track_current_time(self, new_val):
        self.update_progress_ui()

    def watch_track_duration(self, new_val):
        self.update_progress_ui()

    def update_progress_ui(self):
        if not hasattr(self, "play_time_lbl"):
            return
            
        # Convert seconds to M:SS
        def format_time(seconds):
            m, s = divmod(int(seconds), 60)
            return f"{m}:{s:02d}"
            
        curr_str = format_time(self.track_current_time)
        rem_seconds = max(0, self.track_duration - self.track_current_time)
        rem_str = f"-{format_time(rem_seconds)}"
        
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
