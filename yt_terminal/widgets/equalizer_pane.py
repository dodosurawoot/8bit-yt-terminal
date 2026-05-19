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
        max_height = 10
        
        for i, level in enumerate(levels):
            # level is from 0 to 10
            bar_chars = []
            # We want to render a vertical block bar
            # e.g., filled blocks from bottom to level height
            for h in range(max_height):
                if h < level:
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
        # 30 frequency bands for the spectrum
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
            
        # Distribute RMS power across bands with simulated weight curve (heavy bass, lighter highs)
        for i in range(self.num_bars):
            if i < 8:
                weight = 1.3  # Bass
            elif i < 18:
                weight = 1.0  # Mids
            else:
                weight = 0.7  # Highs
                
            # Add micro-fluctuation to columns for an alive, premium look
            fluctuation = random.uniform(-0.12, 0.12)
            target = int((amp * weight + fluctuation) * 8)
            target = max(0, min(8, target))
            
            current = self.bar_heights[i]
            if current < target:
                self.bar_heights[i] = min(8, current + 2)
            else:
                self.bar_heights[i] = max(0, current - 1)
                
        self.refresh()

    def render(self) -> Text:
        max_height = 6
        rows = []
        
        for h in range(max_height - 1, -1, -1):
            # Dynamic Winamp classic green-yellow-red color spectrum gradient
            if h >= 4:
                color = "rgb(240,80,80)"  # Red peaks
            elif h >= 2:
                color = "rgb(250,200,50)"  # Yellow mids
            else:
                color = "rgb(50,220,100)"  # Green bass/low mids
                
            row_chars = []
            for i in range(self.num_bars):
                val = self.bar_heights[i]
                val_at_slice = val - (h * 1.5)
                if val_at_slice >= 1.5:
                    row_chars.append(f"[{color}]█[/]")
                elif val_at_slice >= 0.5:
                    row_chars.append(f"[{color}]▄[/]")
                else:
                    row_chars.append(" ")
            rows.append("   " + "".join(row_chars))
            
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
