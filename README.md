# 📻 YT-Terminal v3.0
> A premium, highly-polished terminal YouTube Music player inspired by Apple Music UI, featuring 8-bit retro album art, scrolling timed spotlight lyrics, and a classic Winamp-style spectrum visualizer.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-E8959A?style=for-the-badge&logo=python" alt="Python Version"/>
  <img src="https://img.shields.io/badge/Textual-TUI-2A1A22?style=for-the-badge&logo=terminal" alt="Textual TUI"/>
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-E8959A?style=for-the-badge" alt="Platform Supported"/>
</p>

---

## ✨ Features

- **🎨 Apple Music-Style Dark Aesthetics**: Translucent layouts styled with high-fidelity slate-rose accent systems (`#1c1216` deep rose background, `#2a1a22` panels, and `#e8959a` dusty accents). All layouts feature responsive rounded borders.
- **🌆 Real-time Adaptive Theme Wash**: A background theme engine Powered by `ColorThief` that dynamically extracts dominant palette swatches from the current song's album art, instantly bathing the TUI in a customized 25-35% darkened gradient wash.
- **🎤 timed spotlight Lyrics**: Scrolling lyrics sync perfectly to play status and apply a premium 3-tier proximity fading focus:
  - **Active Line**: Vibrant pink-white text, bold, underlined, and auto-centered.
  - **Adjacent Lines (±1)**: Mid-level muted mauve.
  - **Distant Lines (±2+)**: Deeply faded dark-rose slate.
- **🎛 Winamp-style 8-Band Equalizer**: Custom vertical level indicators with standard profiles including `YT-DeepRose`, `Bass Boost`, `Vocal`, `Acoustic`, and `Flat`.
- **⚡ 28-Column Spectrum Visualizer**: Animated classic spectrum bars responding dynamically to the background `mpv` player's real-time audio amplitude (RMS dB metadata).
- **🎶 Color-Hashed Queue Miniatures**: Every song in the queue features a color-coded pastel mini cover block hashed from track metadata. Active track shows a thick vertical accent bar highlighting the current title.
- **🔍 Underlined Tab Search**: Interactive filter categories (Songs, Albums, Playlists) styled with bottom solid highlight lines instead of clunky console blocks. Includes real-time autocomplete suggestions.
- **📱 Fully Responsive Layout**: Responsive breakpoints adapt instantly if the console is resized, collapsing gracefully to hide panels on compact screens.

---

## ⌨️ Keyboard Shortcuts

Quickly control your YT-Terminal player using built-in global bindings:

| Hotkey | Action |
|--------|--------|
| <kbd>Space</kbd> | Toggle Play / Pause |
| <kbd>n</kbd> | Next Track |
| <kbd>p</kbd> | Previous Track |
| <kbd>l</kbd> | Toggle Immersive Full-Screen Lyrics Mode |
| <kbd>/</kbd> | Open Search Overlay |
| <kbd>q</kbd> | Safe Quit (cleanly terminates background `mpv` socket) |

---

## 🚀 Installation & Running

### Prerequisites
Make sure you have **`mpv`** installed on your system (which is used as the high-performance background audio backend):
- **macOS**: `brew install mpv`
- **Linux**: `sudo apt install mpv` / `sudo dnf install mpv`

### Running from Source
1. **Clone the repository**:
   ```bash
   git clone https://github.com/dodosurawoot/8bit-yt-terminal.git
   cd 8bit-yt-terminal
   ```
2. **Setup virtual environment & install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Run the developer server**:
   ```bash
   make dev
   ```

### First-Time Google Login
On your first run, a secure terminal authentication dialog will display a Google authorization link and a short device pairing code. Visit the link, enter the code, and confirm access. The app will securely cache your token and initialize your Liked Songs library!

---

## 📦 Building a Desktop Release
To build a standalone desktop executable target using PyInstaller:
```bash
make build
```
This generates a single-file executable at `dist/YT-Terminal` containing all assets and visual styles.

---

## 📝 Disclaimer
This application is unofficial and not affiliated with YouTube or Google Inc. All "YouTube", "YouTube Music", and brand assets are properties of their respective owners.
