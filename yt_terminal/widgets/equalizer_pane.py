# Center Pane Widget: Equalizer & Spectrum Visualizer

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
        self.num_bars = 28
        self.bar_heights = [0 for _ in range(self.num_bars)]
        self.set_interval(0.08, self.animate_spectrum)

    def animate_spectrum(self) -> None:
        if not self.anim_active:
            # Graceful decay when paused
            for i in range(self.num_bars):
                self.bar_heights[i] = max(0, self.bar_heights[i] - 1)
            self.refresh()
            return
            
        # Extract dynamic RMS amplitude level from the active mpv player
        amp = 0.0
        if hasattr(self, "app") and self.app and hasattr(self.app, "player") and self.app.player:
            try:
                amp = self.app.player.get_audio_level()
            except Exception:
                pass

        if amp <= 0.0:
            # Silent parts decay columns gracefully
            for i in range(self.num_bars):
                self.bar_heights[i] = max(0, self.bar_heights[i] - 1)
            self.refresh()
            return
            
        # Distribute RMS power across 28 bands with dynamic peak weighting
        for i in range(self.num_bars):
            if i < 6:
                weight = 1.4  # Sub-Bass/Bass
            elif i < 12:
                weight = 1.1  # Mid-Bass
            elif i < 20:
                weight = 0.8  # Vocals/Mids
            else:
                weight = 0.5  # Presence/Highs
                
            # Add dynamic, smooth organic noise to simulate authentic multi-band movement
            fluctuation = random.uniform(-0.1, 0.1)
            target = int((amp * weight + fluctuation) * 10)
            target = max(0, min(8, target))
            
            current = self.bar_heights[i]
            if current < target:
                self.bar_heights[i] = min(8, current + 2) # fast rise
            else:
                self.bar_heights[i] = max(0, current - 1) # smooth analog decay
                
        self.refresh()

    def render(self) -> Text:
        max_height = 8  # 8 vertical steps for high-res spectrum mapping
        rows = []
        
        for h in range(max_height - 1, -1, -1):
            # Dynamic Winamp classic green-yellow-orange-red color spectrum gradient
            if h >= 6:
                color = "rgb(240,80,80)"  # Red peaks (Rows 6-7)
            elif h >= 4:
                color = "rgb(248,140,50)" # Orange mids (Rows 4-5)
            elif h >= 2:
                color = "rgb(250,210,50)" # Yellow low-mids (Rows 2-3)
            else:
                color = "rgb(50,220,100)"  # Green bass base (Rows 0-1)
                
            row_chars = []
            for i in range(self.num_bars):
                val = self.bar_heights[i]
                # Scale value to match current slice height
                val_at_slice = val - h
                if val_at_slice >= 1.0:
                    row_chars.append(f"[{color}]█[/]")
                elif val_at_slice >= 0.5:
                    row_chars.append(f"[{color}]▄[/]")
                else:
                    row_chars.append(" ")
            rows.append("".join(row_chars))
            
        return Text.from_markup("\n".join(rows))

class EqualizerPane(Widget):
    """The complete Center Pane wrapping EQ sliders, spectrum, and tabs."""
    
    def compose(self):
        self.border_title = "Equalizer & Visualizer"
        
        # Upper EQ panel
        self.eq_widget = EqualizerWidget()
        yield self.eq_widget
        
        # Lower Spectrum Panel
        with Vertical(id="vis-container"):
            self.visualizer = SpectrumVisualizer()
            yield self.visualizer
            
        # Navigation toggle tab row
        with Horizontal(id="eq-vis-toggle"):
            self.eq_tab = Label("🎛 EQUALIZER", classes="toggle-btn active")
            self.vis_tab = Label("⚡ VISUALIZER", classes="toggle-btn active")
            yield self.eq_tab
            yield self.vis_tab
