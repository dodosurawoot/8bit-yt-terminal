# EQ presets and default curated fallback tracks for YT-Terminal
from yt_terminal.music_service import Track

EQ_PRESETS = {
    "YT-DeepRose": [8, 9, 6, 8, 7, 5, 4, 3],
    "Flat": [5, 5, 5, 5, 5, 5, 5, 5],
    "Bass Boost": [9, 8, 7, 5, 4, 4, 5, 5],
    "Vocal": [3, 4, 6, 7, 8, 8, 7, 5],
    "Acoustic": [6, 5, 6, 7, 6, 7, 7, 6],
}

DEFAULT_FALLBACK_TRACKS = [
    Track(
        video_id="WMF4kot2qGA",
        title="Malibu Nights",
        artist="LANY",
        album="Malibu Nights",
        duration_seconds=287,
        thumbnail_url="https://i.ytimg.com/vi/WMF4kot2qGA/maxresdefault.jpg"
    ),
    Track(
        video_id="z-SrH7XY1lc",
        title="ILYSB",
        artist="LANY",
        album="LANY",
        duration_seconds=208,
        thumbnail_url="https://i.ytimg.com/vi/z-SrH7XY1lc/maxresdefault.jpg"
    ),
    Track(
        video_id="Mk-XlXe40FM",
        title="Super Far",
        artist="LANY",
        album="LANY",
        duration_seconds=203,
        thumbnail_url="https://i.ytimg.com/vi/Mk-XlXe40FM/maxresdefault.jpg"
    ),
    Track(
        video_id="N2rkKSxX7FI",
        title="Thru These Tears",
        artist="LANY",
        album="Malibu Nights",
        duration_seconds=202,
        thumbnail_url="https://i.ytimg.com/vi/N2rkKSxX7FI/maxresdefault.jpg"
    ),
    Track(
        video_id="vaSq0xqV0rY",
        title="13",
        artist="LANY",
        album="LANY",
        duration_seconds=279,
        thumbnail_url="https://i.ytimg.com/vi/vaSq0xqV0rY/maxresdefault.jpg"
    ),
    Track(
        video_id="XedT5nYyq54",
        title="Let Me Know",
        artist="LANY",
        album="Malibu Nights",
        duration_seconds=200,
        thumbnail_url="https://i.ytimg.com/vi/XedT5nYyq54/maxresdefault.jpg"
    ),
    Track(
        video_id="V18DUQwrDz0",
        title="Thick And Thin",
        artist="LANY",
        album="Malibu Nights",
        duration_seconds=212,
        thumbnail_url="https://i.ytimg.com/vi/V18DUQwrDz0/maxresdefault.jpg"
    )
]
