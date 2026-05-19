# ColorThief dynamic palette extractor and TCSS variable generator

import os
import logging
from colorthief import ColorThief

# Fallback LANY-DeepRose warm mauve theme palette
DEFAULT_THEME = {
    "primary_bg": "#432832",      # Deep dark rose
    "panel_bg": "#4f313c",        # Slightly lighter rose panel
    "accent": "#d38e91",          # Dusty pink/accent
    "text_primary": "#fbe5e6",    # Warm white/light pink
    "text_muted": "#a68894",      # Muted mauve text
    "border": "#7a5260"           # Rose border
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
    If image_path is None or doesn't exist, returns the default LANY-DeepRose theme.
    """
    if not image_path or not os.path.exists(image_path):
        return DEFAULT_THEME.copy()
    
    try:
        color_thief = ColorThief(image_path)
        dominant = color_thief.get_color(quality=1)
        palette = color_thief.get_palette(color_count=5, quality=1)
        
        # Determine background (darkened dominant color)
        bg_rgb = darken_color(dominant, 0.45)
        panel_rgb = darken_color(dominant, 0.6)
        
        # Pick best accent from palette
        # We look for a bright light color in the palette
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
            text_rgb = (250, 235, 235)
            
        muted_rgb = darken_color(text_rgb, 0.7)
        border_rgb = lighten_color(bg_rgb, 1.4)
        
        return {
            "primary_bg": rgb_to_hex(bg_rgb),
            "panel_bg": rgb_to_hex(panel_rgb),
            "accent": rgb_to_hex(accent_rgb),
            "text_primary": rgb_to_hex(text_rgb),
            "text_muted": rgb_to_hex(muted_rgb),
            "border": rgb_to_hex(border_rgb)
        }
    except Exception as e:
        logging.error(f"Failed to extract palette from image: {e}")
        return DEFAULT_THEME.copy()

def generate_tcss(theme_dict):
    """
    Generates the Textual CSS theme overrides based on the theme dictionary.
    """
    return f"""
/* Generated TUI Theme Stylesheet */
$primary-bg: {theme_dict['primary_bg']};
$panel-bg: {theme_dict['panel_bg']};
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

#player-pane, #eq-pane, #lyrics-view, #queue-view {{
    background: $panel-bg;
    border: tall $border;
    color: $text-primary;
}}
"""
