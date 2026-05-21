# ColorThief dynamic palette extractor and TCSS variable generator

import os
import logging
from PIL import Image
from colorthief import ColorThief

# Fallback premium dark theme palette
DEFAULT_THEME = {
    "primary_bg": "#0a0b10",      # Deep obsidian
    "panel_bg": "#131520",        # Translucent glass panel
    "player_bg": "#121422",       # Tinted player panel
    "eq_bg": "#151320",           # Tinted EQ panel
    "right_bg": "#161622",        # Tinted right panels
    "accent": "#00f3ff",          # Cyber cyan
    "text_primary": "#f5f6fa",    # Ice white
    "text_muted": "#686d80",      # Translucent slate-gray
    "border": "#262938"           # Sleek rounded border tint
}

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def darken_color(rgb, factor=0.4):
    return tuple(max(0, int(c * factor)) for c in rgb)

def lighten_color(rgb, factor=1.3):
    return tuple(min(255, int(c * factor)) for c in rgb)

def extract_palette(image_path=None):
    """
    Extracts dominant colors from the image at image_path using ColorThief.
    If image_path is None or doesn't exist, returns the default theme.
    """
    if not image_path or not os.path.exists(image_path):
        return DEFAULT_THEME.copy()
    
    try:
        color_thief = ColorThief(image_path)
        dominant = color_thief.get_color(quality=1)
        palette = color_thief.get_palette(color_count=5, quality=1)
        
        # Ensure we have at least 3 distinct dominant colors from palette
        c1 = palette[0] if len(palette) > 0 else dominant
        c2 = palette[1] if len(palette) > 1 else darken_color(c1, 0.8)
        c3 = palette[2] if len(palette) > 2 else lighten_color(c1, 1.2)
        
        # Darken the colors appropriately for premium near-black panels
        player_rgb = darken_color(c1, 0.12)
        eq_rgb = darken_color(c2, 0.12)
        right_rgb = darken_color(c3, 0.12)
        bg_rgb = darken_color(dominant, 0.08)
        panel_rgb = darken_color(dominant, 0.15)
        
        # Pick best accent from palette
        accent_rgb = dominant
        for col in palette:
            # Simple luminance check
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            if 100 < lum < 220:
                accent_rgb = col
                break
                
        # If accent is too close to bg, lighten it
        if sum(abs(a - b) for a, b in zip(accent_rgb, bg_rgb)) < 100:
            accent_rgb = lighten_color(dominant, 1.5)
            
        text_rgb = lighten_color(accent_rgb, 1.6)
        # Ensure text is bright enough
        if sum(text_rgb) / 3 < 180:
            text_rgb = (255, 240, 240)
            
        muted_rgb = darken_color(text_rgb, 0.6)
        border_rgb = lighten_color(bg_rgb, 1.3)
        
        return {
            "primary_bg": rgb_to_hex(bg_rgb),
            "panel_bg": rgb_to_hex(panel_rgb),
            "player_bg": rgb_to_hex(player_rgb),
            "eq_bg": rgb_to_hex(eq_rgb),
            "right_bg": rgb_to_hex(right_rgb),
            "accent": rgb_to_hex(accent_rgb),
            "text_primary": rgb_to_hex(text_rgb),
            "text_muted": rgb_to_hex(muted_rgb),
            "border": rgb_to_hex(border_rgb)
        }
    except Exception as e:
        logging.error(f"Failed to extract palette from image: {e}")
        return DEFAULT_THEME.copy()

def download_and_extract(thumbnail_url: str) -> dict:
    """
    Downloads a thumbnail image, caches it, and extracts the theme palette.
    Falls back to the default theme on any network or filesystem failures.
    """
    if not thumbnail_url:
        return DEFAULT_THEME.copy()
        
    import hashlib
    import requests
    from yt_terminal.config_manager import ConfigManager
    
    ConfigManager.ensure_dirs()
    url_hash = hashlib.md5(thumbnail_url.encode("utf-8")).hexdigest()
    cache_path = ConfigManager.CACHE_DIR / f"{url_hash}.jpg"
    
    if not cache_path.exists():
        try:
            r = requests.get(thumbnail_url, timeout=5)
            if r.status_code == 200:
                with open(cache_path, "wb") as f:
                    f.write(r.content)
                # Optimize image size for ColorThief palette extraction
                try:
                    with Image.open(cache_path) as img:
                        img.thumbnail((64, 64))
                        img.save(cache_path, "JPEG")
                except Exception as e:
                    logging.warning(f"Failed to downscale cached thumbnail: {e}")
            else:
                return DEFAULT_THEME.copy()
        except Exception as e:
            logging.error(f"Failed to download thumbnail: {e}")
            return DEFAULT_THEME.copy()
            
    return extract_palette(str(cache_path))

def generate_tcss(theme_dict):
    """
    Generates the Textual CSS theme overrides based on the theme dictionary.
    """
    return f"""
/* Generated TUI Theme Stylesheet */
$primary-bg: {theme_dict.get('primary_bg', '#0a0b10')};
$player-bg: {theme_dict.get('player_bg', '#121422')};
$eq-bg: {theme_dict.get('eq_bg', '#151320')};
$right-bg: {theme_dict.get('right_bg', '#161622')};
$accent: {theme_dict['accent']};
$text-primary: {theme_dict['text_primary']};
$text-muted: {theme_dict['text_muted']};
$border: {theme_dict['border']};

Screen {{
    background: $primary-bg;
    color: $text-primary;
}}

#main-layout {{
    background: $primary-bg;
}}

#player-pane {{
    background: $player-bg 85%;
    border: round $border;
    color: $text-primary;
}}

#eq-pane {{
    background: $eq-bg 80%;
    border: round $border;
    color: $text-primary;
}}

#lyrics-view {{
    background: $right-bg 75%;
    border: round $border;
    color: $text-primary;
}}

#queue-view {{
    background: $right-bg 75%;
    border: round $border;
    color: $text-primary;
}}
"""
