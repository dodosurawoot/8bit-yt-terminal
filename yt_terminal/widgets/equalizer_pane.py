# Center Pane Widget: Equalizer & Spectrum Visualizer

from textual.containers import Center
import random
import time
import math
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
    current_style = reactive(0) # 0: Chunky LED Grid, 1: HUD Mirrored, 2: Analog Wave, 3: Digital Solid

    def on_mount(self) -> None:
        self.num_bars = 24
        self.bar_heights = [0.0 for _ in range(self.num_bars)]
        self.bar_velocities = [0.0 for _ in range(self.num_bars)]
        self.peak_heights = [0.0 for _ in range(self.num_bars)]
        self.peak_delays = [0 for _ in range(self.num_bars)]
        # Boost frame rate to 25 FPS (0.04s interval) for liquid-smooth physics-based animation
        self.set_interval(0.04, self.animate_spectrum)
        self.update_border_title()

    def watch_current_style(self, new_style: int) -> None:
        """Observe style reactive change to update border title automatically."""
        self.update_border_title()

    def update_border_title(self) -> None:
        style_names = {
            0: "Chunky LED Grid",
            1: "HUD Mirrored",
            2: "Analog Wave",
            3: "Digital Solid"
        }
        self.border_title = f"{style_names.get(self.current_style, 'Chunky LED Grid')}"

    def on_click(self, event=None) -> None:
        """Cycle visualizer style on mouse click."""
        self.current_style = (self.current_style + 1) % 4

    def animate_spectrum(self) -> None:
        max_height = 6.0
        
        # Graceful decay when paused or inactive
        if not self.anim_active:
            for i in range(self.num_bars):
                self.bar_heights[i] = max(0.0, self.bar_heights[i] - 0.15)
                self.peak_heights[i] = max(0.0, self.peak_heights[i] - 0.1)
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
                # Procedural synthwave organic wave simulation with physics!
                t = time.time()
                for i in range(self.num_bars):
                    # Combine multiple harmonic waves for dynamic flowing movement
                    val = 2.5 + 2.0 * math.sin(t * 2.5 + i * 0.4)
                    val += 1.0 * math.sin(t * 5.0 - i * 0.8)
                    
                    # Section-specific frequency accentuations
                    if i < 4:
                        val += 1.0 * (1.0 + math.sin(t * 4.0)) # Bass roll
                    elif i > self.num_bars - 4:
                        val += 0.5 * random.random() # Treble shimmer
                        
                    target = max(0.0, min(max_height, val))
                    
                    y = self.bar_heights[i]
                    v = self.bar_velocities[i]
                    # Springy rise, slower drag decay
                    accel = (target - y) * 0.4 if target > y else (target - y) * 0.18 - 0.03
                    v = v * 0.72 + accel
                    y = max(0.0, min(max_height, y + v))
                    if y <= 0.0:
                        v = 0.0
                    self.bar_heights[i] = y
                    self.bar_velocities[i] = v
                
                # Update visualizer peak heights
                for i in range(self.num_bars):
                    cur = self.bar_heights[i]
                    pk = self.peak_heights[i]
                    if cur > pk:
                        self.peak_heights[i] = cur
                        self.peak_delays[i] = 5
                    else:
                        if self.peak_delays[i] > 0:
                            self.peak_delays[i] -= 1
                        else:
                            self.peak_heights[i] = max(0.0, pk - 0.15)
                            
                self.refresh()
                return
            else:
                # Decays slowly on stop
                for i in range(self.num_bars):
                    self.bar_heights[i] = max(0.0, self.bar_heights[i] - 0.2)
                    self.peak_heights[i] = max(0.0, self.peak_heights[i] - 0.1)
                self.refresh()
                return

        # Real audio stream dynamic analysis: apply organic fluid physics
        for i in range(self.num_bars):
            if i < 3:
                weight = 1.3  # Bass
            elif i < 8:
                weight = 0.8  # Mids
            else:
                weight = 0.4  # Highs
                
            fluctuation = random.uniform(-0.15, 0.15)
            target = (amp * weight + fluctuation) * 6.0
            target = max(0.0, min(max_height, target))
            
            y = self.bar_heights[i]
            v = self.bar_velocities[i]
            
            # Spring-mass physics calculation for liquid organic bounce
            if target > y:
                accel = (target - y) * 0.48 # Fast snappy upward acceleration
            else:
                accel = (target - y) * 0.22 - 0.05 # Organic gravity fall with speed decay
                
            v = v * 0.7 + accel
            y = max(0.0, min(max_height, y + v))
            if y <= 0.0:
                v = 0.0
                
            self.bar_heights[i] = y
            self.bar_velocities[i] = v
                
        # Classic floating peak decays
        for i in range(self.num_bars):
            cur = self.bar_heights[i]
            pk = self.peak_heights[i]
            if cur > pk:
                self.peak_heights[i] = cur
                self.peak_delays[i] = 5
            else:
                if self.peak_delays[i] > 0:
                    self.peak_delays[i] -= 1
                else:
                    self.peak_heights[i] = max(0.0, pk - 0.12)
                    
        self.refresh()

    def render(self) -> Text:
        max_height = 6
        rows = []
        
        # Gradient colors from deep blue at the bottom to vibrant cyber cyan at the top
        colors = ["#0033aa", "#0055dd", "#0077ff", "#00aaff", "#00d4ff", "#00f3ff"]
        
        # Style 0: Chunky LED Grid with smooth deep blue to cyan gradient and sub-cell precision
        if self.current_style == 0:
            for h in range(max_height - 1, -1, -1):
                color = colors[h]
                row_chars = []
                for i in range(self.num_bars):
                    val = self.bar_heights[i]
                    peak = self.peak_heights[i]
                    
                    if val >= h + 1:
                        # Fully active block
                        row_chars.append(f"[{color}]█[/]")
                    elif val <= h:
                        # Inactive cell: check if peak sits exactly here
                        if int(peak) == h and peak > 0:
                            row_chars.append("[#ffaec9]▀[/]") # Soft glowing pink peak
                        else:
                            row_chars.append("[#262938]░[/]") # Obsidian translucent background cell
                    else:
                        # Partially active cell (fractional height sub-block rendering)
                        fraction = val - h
                        if fraction < 0.125:
                            row_chars.append("[#262938]░[/]")
                        elif fraction < 0.25:
                            row_chars.append(f"[{color}] [/]")
                        elif fraction < 0.375:
                            row_chars.append(f"[{color}]▂[/]")
                        elif fraction < 0.5:
                            row_chars.append(f"[{color}]▃[/]")
                        elif fraction < 0.625:
                            row_chars.append(f"[{color}]▄[/]")
                        elif fraction < 0.75:
                            row_chars.append(f"[{color}]▅[/]")
                        elif fraction < 0.875:
                            row_chars.append(f"[{color}]▆[/]")
                        else:
                            row_chars.append(f"[{color}]▇[/]")
                            
                rows.append(" ".join(row_chars))
                
        # Style 1: HUD Mirrored (Symmetric up & down from center baseline with sub-block resolution)
        elif self.current_style == 1:
            for h in range(max_height - 1, -1, -1):
                row_chars = []
                for i in range(self.num_bars):
                    v = self.bar_heights[i]
                    active_height = v / 2.0 # Maps 0..6 to 0..3 active blocks float
                    
                    # Colors for high-tech HUD mirrored styling
                    if h == 5 or h == 0:
                        color = "#00f3ff"  # Electric Cyan (Outer bands)
                    elif h == 4 or h == 1:
                        color = "#00a8ff"  # Neon Blue (Mid bands)
                    else:
                        color = "#0055ff"  # Deep HUD Blue (Inner bands)
                        
                    if h >= 3:
                        idx = h - 3
                        if active_height >= idx + 1:
                            row_chars.append(f"[{color}]█[/]")
                        elif active_height <= idx:
                            row_chars.append("[#15223c]·[/]")
                        else:
                            # Sub-block precision upwards
                            fraction = active_height - idx
                            sub_chars = [" ", "▂", "▃", "▄", "▅", "▆", "▇"]
                            char_idx = min(6, int(fraction * 8))
                            row_chars.append(f"[{color}]{sub_chars[char_idx]}[/]")
                    else:
                        idx = 2 - h
                        if active_height >= idx + 1:
                            row_chars.append(f"[{color}]█[/]")
                        elif active_height <= idx:
                            row_chars.append("[#15223c]·[/]")
                        else:
                            # Downward fraction rendering representation
                            row_chars.append(f"[{color}]▀[/]")
                            
                rows.append(" ".join(row_chars))

        # Style 2: Continuous Analog Oscilloscope (CRT radar scrolling wave)
        elif self.current_style == 2:
            num_cols = self.num_bars * 2 - 1
            interp_heights = [0.0] * num_cols
            for x in range(num_cols):
                if x % 2 == 0:
                    interp_heights[x] = float(self.bar_heights[x // 2])
                else:
                    left = float(self.bar_heights[x // 2])
                    right = float(self.bar_heights[x // 2 + 1]) if (x // 2 + 1) < self.num_bars else left
                    interp_heights[x] = (left + right) / 2.0
                    
            for h in range(max_height - 1, -1, -1):
                row_chars = []
                for x in range(num_cols):
                    wave_h = int(interp_heights[x])
                    if wave_h == h:
                        row_chars.append("[#00ff66]█[/]")
                    else:
                        row_chars.append("[#10301a]·[/]")
                rows.append("".join(row_chars))

        # Style 3: Digital Solid (Golden amber block columns)
        elif self.current_style == 3:
            for h in range(max_height - 1, -1, -1):
                if h >= 4:
                    color = "#ff9100"  # Amber Orange (Rows 4-5)
                elif h >= 2:
                    color = "#ffc400"  # Warm Yellow (Rows 2-3)
                else:
                    color = "#ffea00"  # Neon Yellow (Rows 0-1)
                    
                row_chars = []
                for i in range(self.num_bars):
                    val = self.bar_heights[i]
                    if val > h:
                        row_chars.append(f"[{color}]█[/]")
                    else:
                        row_chars.append("[#221a0f]·[/]")
                        
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
