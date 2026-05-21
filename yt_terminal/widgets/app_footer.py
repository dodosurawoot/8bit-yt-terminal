# Custom Premium TUI Footer Widget for YT-Terminal

from textual.widget import Widget
from rich.text import Text

class AppFooter(Widget):
    """A customized premium TUI footer displaying exact keybindings with Obsidian Synthwave theme colors."""

    DEFAULT_CSS = """
    AppFooter {
        background: #0a0b10;
        color: #686d80;
        height: 1;
        width: 100%;
        dock: bottom;
        border-top: solid #262938;
        content-align: center middle;
    }
    """

    def render(self) -> Text:
        """Renders the beautifully styled keybindings with golden keys and white labels."""
        return Text.from_markup(
            "[bold #fedb72]^q q[/] [#f5f6fa]Quit[/]   "
            "[bold #fedb72]space[/] [#f5f6fa]Play/Pause[/]   "
            "[bold #fedb72]n[/] [#f5f6fa]Next Track[/]   "
            "[bold #fedb72]p[/] [#f5f6fa]Prev Track[/]   "
            "[bold #fedb72]l[/] [#f5f6fa]Full Lyrics[/]   "
            "[bold #fedb72]w[/] [#f5f6fa]Lyrics + Art[/]   "
            "[bold #fedb72]/[/] [#f5f6fa]Search[/]   "
            "[bold #fedb72]a[/] [#f5f6fa]Sync Account[/]   "
            "[bold #fedb72]+[/] [#f5f6fa]Vol +[/]   "
            "[bold #fedb72]-[/] [#f5f6fa]Vol -[/]   "
            "[bold #fedb72]^p[/] [#f5f6fa]palette[/]"
        )
