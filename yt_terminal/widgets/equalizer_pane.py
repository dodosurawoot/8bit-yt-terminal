# Center Pane Widget: Equalizer & Spectrum Visualizer

from textual.containers import Center
import random
from textual.widget import Widget
from textual.widgets import Label, Select
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from yt_terminal.mock_data import EQ_PRESETS

class EqualizerWidget(Widget):
    """Renders the 8-band Equalizer visualizer with dB vertical bars."""
    preset_name = reactive("YT-DeepRose")

    def compose(self):
        yield Label("Equalizer", classes="eq-title")
        
        # Preset selection container
        with Horizontal(id="eq-preset-container"):
            # Select dropdown for presets
            self.select_preset = Select(
                [(name, name) for name in EQ_PRESETS.keys()],
                value=self.preset_name,
                allow_blank=False,
            )
            yield self.select_preset
            yield Label("•••", id="eq-menu")

        # Equalizer Sliders Container
        with Horizontal(id="eq-sliders"):
            self.sliders = []
            bands = ["16", "12", "24", "58", "10k", "260", "...", "8k"]
            for i, band in enumerate(bands):
                # Slide indicator label (vertical bar representation)
                bar = Label("", classes="eq-bar")
                lbl = Label(band, classes="eq-label")
                self.sliders.append(bar)
                yield Vertical(bar, lbl, classes="eq-col")
                
    def on_mount(self):
        self.update_sliders()

    def watch_preset_name(self, new_val):
        self.update_sliders()

    def update_sliders(self):
        if not hasattr(self, "sliders") or not self.sliders:
            return
            
        levels = EQ_PRESETS.get(self.preset_name, [5] * 8)
        max_height = 5
        
        for i, level in enumerate(levels):
            # Scale level (0-10) to max_height (5)
            scaled_level = int(level / 2)
            bar_chars = []
            # We want to render a vertical block bar
            for h in range(max_height):
                if h < scaled_level:
                    bar_chars.append("█")
                else:
                    bar_chars.append("░")
            # Reverse because vertical drawing draws top-to-bottom
            bar_chars.reverse()
            self.sliders[i].update("\n".join(bar_chars))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select == self.select_preset:
            self.preset_name = str(event.value)

from rich.text import Text

class SpectrumVisualizer(Widget):
    """An active dynamic spectrum visualizer displaying animated block columns synced to mpv audio."""
    
    # Visualizer state
    anim_active = reactive(True)

    def on_mount(self) -> None:
        self.border_title = "Visualizer"
        self.num_bars = 12
        self.bar_heights = [0 for _ in range(self.num_bars)]
        self.peak_heights = [0 for _ in range(self.num_bars)]
        self.peak_delays = [0 for _ in range(self.num_bars)]
        self.set_interval(0.08, self.animate_spectrum)

    def animate_spectrum(self) -> None:
        max_height = 6
        if not self.anim_active:
            # Graceful decay when paused
            for i in range(self.num_bars):
                self.bar_heights[i] = max(0, self.bar_heights[i] - 1)
                self.peak_heights[i] = max(0, self.peak_heights[i] - 1)
            self.refresh()
            return
            
        # Extract dynamic RMS amplitude level from the active mpv player
        amp = 0.0
        if hasattr(self, "app") and self.app and hasattr(self.app, "player") and self.app.player:
            try:
                amp = self.app.player.get_audio_level()
            except Exception:
                pass

        is_playing = False
        if hasattr(self, "app") and self.app and hasattr(self.app, "is_playing"):
            is_playing = self.app.is_playing

        if amp <= 0.0:
            if is_playing:
                # Organic multi-band procedural simulation fallback!
                import time
                import math
                t = time.time()
                for i in range(self.num_bars):
                    # Rolling wave combined with high-frequency noise
                    val = 2.0 + 1.5 * math.sin(t * 3.5 + i * 0.9)
                    val += 1.0 * math.sin(t * 9.0 - i * 1.4)
                    
                    # Bass emphasis on left 3 columns
                    if i < 3:
                        val += 1.2 * (1.0 + math.sin(t * 6.5))
                    # Midrange emphasis on center 6 columns
                    elif i < 9:
                        val += 0.8 * (1.0 + math.cos(t * 5.0))
                    # Treble hiss on right 3 columns
                    else:
                        val += 0.8 * random.random()
                        
                    target = int(max(0, min(max_height, val)))
                    current = self.bar_heights[i]
                    if current < target:
                        self.bar_heights[i] = min(max_height, current + 2)
                    else:
                        self.bar_heights[i] = max(0, current - 1)
                
                # Update floating peaks
                for i in range(self.num_bars):
                    cur = self.bar_heights[i]
                    pk = self.peak_heights[i]
                    if cur > pk:
                        self.peak_heights[i] = cur
                        self.peak_delays[i] = 4
                    else:
                        if self.peak_delays[i] > 0:
                            self.peak_delays[i] -= 1
                        else:
                            self.peak_heights[i] = max(0, pk - 1)
                            
                self.refresh()
                return
            else:
                # Silent parts decay columns gracefully
                for i in range(self.num_bars):
                    self.bar_heights[i] = max(0, self.bar_heights[i] - 1)
                    self.peak_heights[i] = max(0, self.peak_heights[i] - 1)
                self.refresh()
                return
            
        # Distribute RMS power across 12 bands with dynamic peak weighting
        for i in range(self.num_bars):
            if i < 3:
                weight = 1.3  # Bass
            elif i < 8:
                weight = 0.8  # Mids
            else:
                weight = 0.4  # Highs
                
            # Add dynamic, smooth organic noise to simulate authentic multi-band movement
            fluctuation = random.uniform(-0.1, 0.1)
            target = int((amp * weight + fluctuation) * 10)
            target = max(0, min(max_height, target))
            
            current = self.bar_heights[i]
            if current < target:
                self.bar_heights[i] = min(max_height, current + 2) # fast rise
            else:
                self.bar_heights[i] = max(0, current - 1) # smooth analog decay
                
        # Update classic Winamp-style floating peaks
        for i in range(self.num_bars):
            cur = self.bar_heights[i]
            pk = self.peak_heights[i]
            if cur > pk:
                self.peak_heights[i] = cur
                self.peak_delays[i] = 4
            else:
                if self.peak_delays[i] > 0:
                    self.peak_delays[i] -= 1
                else:
                    self.peak_heights[i] = max(0, pk - 1)
                    
        self.refresh()

    def render(self) -> Text:
        max_height = 6  # 6 vertical steps for high-res spectrum mapping
        rows = []
        
        for h in range(max_height - 1, -1, -1):
            # Dynamic Winamp classic green-yellow-orange-red color spectrum gradient
            if h >= 4:
                color = "rgb(240,80,80)"  # Red peaks (Rows 4-5)
            elif h >= 3:
                color = "rgb(248,140,50)" # Orange mids (Row 3)
            elif h >= 1:
                color = "rgb(250,210,50)" # Yellow low-mids (Rows 1-2)
            else:
                color = "rgb(50,220,100)"  # Green bass base (Row 0)
                
            row_chars = []
            for i in range(self.num_bars):
                val = self.bar_heights[i]
                peak = self.peak_heights[i]
                
                if val > h:
                    # Solid chunky block for active 8-bit LED segments
                    row_chars.append(f"[{color}]█[/]")
                elif peak == h and peak > 0:
                    # Floating top peak dot (Winamp style high-contrast rose pop!)
                    row_chars.append("[#ffa8b0]▀[/]")
                else:
                    # Subtle low-contrast background cell for hardware grid panel
                    row_chars.append("[#3a2230]░[/]")
                    
            rows.append(" ".join(row_chars))
            
        return Text.from_markup("\n".join(rows))

class EqualizerPane(Widget):
    """The complete Center Pane wrapping EQ sliders, spectrum, and tabs."""
    
    def compose(self):
        self.border_title = "Equalizer"
        
        # Upper EQ panel
        self.eq_widget = EqualizerWidget()
        yield self.eq_widget
        
        # Lower Spectrum Panel
        with Center(id="vis-container"):
            self.visualizer = SpectrumVisualizer()
            yield self.visualizer
            
        # Navigation toggle tab row
        with Center(id="eq-vis-toggle"):
            yield Label("Visualizer", classes="toggle-btn active")
