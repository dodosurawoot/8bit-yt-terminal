import asyncio
from textual.screen import Screen
from textual.widgets import Label, Input, Button, Static
from textual.containers import Vertical, Horizontal, Grid
from textual.reactive import reactive
from textual.message import Message
from yt_terminal.music_service import MusicService
from yt_terminal.config_manager import ConfigManager

class ClickableCodeLabel(Label):
    """A label that displays the OAuth code and copies it to the clipboard when clicked."""
    code_text = ""

    def on_click(self) -> None:
        if self.code_text:
            try:
                import subprocess
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, close_fds=True)
                process.communicate(input=self.code_text.encode('utf-8'))
                self.app.notify("Authorization code copied to clipboard!", title="Clipboard")
            except Exception:
                pass

class LoginScreen(Screen):
    """Screen for handling YouTube Music OAuth device registration flow."""
    
    DEFAULT_CSS = """
    LoginScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #login-box {
        width: 60;
        height: auto;
        border: round #3c2633;
        background: #1c1216;
        padding: 2 4;
        border-title-color: #e8959a;
    }

    .login-title {
        text-align: center;
        color: #e8959a;
        text-style: bold;
        margin-bottom: 1;
    }

    .login-desc {
        text-align: center;
        margin-bottom: 1;
        color: #7a5a68;
        text-wrap: wrap; /* Ensure long descriptions wrap cleanly without clipping */
    }

    .login-field-lbl {
        margin-top: 1;
        color: #fff0f0;
        text-wrap: wrap;
    }

    .login-field {
        margin-bottom: 1;
        border: round #3c2633;
        background: #2a1a22;
    }

    #btn-container {
        align: center middle;
        margin-top: 2;
    }

    .action-btn {
        width: 100%;
        background: #e8959a;
        color: #1c1216;
        text-style: bold;
    }

    #oauth-details-container {
        display: none;
        margin-top: 1;
        margin-bottom: 1;
        padding: 1 2;
        border: dashed #3c2633;
        background: #23161c;
    }

    .oauth-step-title {
        color: #fff0f0;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
        text-wrap: wrap;
    }

    .oauth-url {
        text-style: underline bold;
        color: #50dc64; /* Neon green for high contrast visibility */
        text-align: center;
        margin-top: 1;
        margin-bottom: 2;
        text-wrap: wrap;
    }

    .oauth-code {
        text-align: center;
        text-style: bold;
        color: #fedb72; /* Glowing golden-yellow pairing code */
        background: #1c1216;
        border: round #3c2633;
        padding: 1 3;
        margin: 1 0;
    }

    .oauth-code:hover {
        background: #3c2633;
        color: #fff0f0;
        border: round #e8959a;
    }

    .status-msg {
        text-align: center;
        color: #e8959a;
        margin-top: 2;
        text-wrap: wrap;
    }
    """

    class LoginSuccess(Message):
        """Posted when OAuth registration completes successfully."""
        pass

    def __init__(self, music_service: MusicService):
        super().__init__()
        self.ms = music_service
        self.device_code = None
        self.poll_task = None

    def compose(self):
        with Vertical(id="login-box") as v:
            v.border_title = " YOUTUBE MUSIC LOGIN "
            yield Label("🎵  YT-Terminal", classes="login-title")
            yield Label(
                "Integrate your real YouTube Music account! Please supply your "
                "Google Cloud Client Credentials (configured as 'TVs & Input Devices').",
                classes="login-desc"
            )

            # Saved credentials check
            saved_id, saved_secret = ConfigManager.get_credentials()
            
            yield Label("Client ID", classes="login-field-lbl")
            yield Input(
                value=saved_id or "", 
                placeholder="Paste your OAuth Client ID here...", 
                id="client-id-input", 
                classes="login-field"
            )

            yield Label("Client Secret", classes="login-field-lbl")
            yield Input(
                value=saved_secret or "", 
                placeholder="Paste your OAuth Client Secret here...", 
                password=True, 
                id="client-secret-input", 
                classes="login-field"
            )

            with Vertical(id="oauth-details-container") as details:
                yield Label("⚡ STEP 1: Go to the verification URL in your browser:", classes="oauth-step-title")
                yield Label("", id="verification-url-lbl", classes="oauth-url")
                yield Label("🔑 STEP 2: Enter this device authorization code:", classes="oauth-step-title")
                yield ClickableCodeLabel("XXXX-XXXX", id="user-code-lbl", classes="oauth-code")
                yield Label("Waiting for your authorization... ⏳", id="polling-status-lbl", classes="status-msg")

            with Horizontal(id="btn-container"):
                yield Button("Connect Account", id="connect-btn", classes="action-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-btn":
            client_id = self.query_one("#client-id-input", Input).value.strip()
            client_secret = self.query_one("#client-secret-input", Input).value.strip()

            if not client_id or not client_secret:
                self.query_one("#polling-status-lbl", Label).text = "⚠️ Please fill in both Client ID and Client Secret"
                return

            event.button.disabled = True
            self.query_one("#polling-status-lbl", Label).text = "Generating device code..."
            
            try:
                # Fetch Device Code Flow URL and User Code
                code_data = await self.ms.get_oauth_device_code(client_id, client_secret)
                
                # Show OAuth directions panel
                self.query_one("#oauth-details-container").display = True
                self.query_one("#verification-url-lbl", Label).update(code_data["verification_url"])
                
                user_code = code_data["user_code"]
                user_code_lbl = self.query_one("#user-code-lbl", ClickableCodeLabel)
                user_code_lbl.code_text = user_code
                user_code_lbl.update(f"  {user_code}  ")
                
                # Automatically copy to macOS clipboard
                copied_successful = False
                try:
                    import subprocess
                    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, close_fds=True)
                    process.communicate(input=user_code.encode('utf-8'))
                    copied_successful = True
                except Exception:
                    pass
                
                status_msg = "Waiting for your authorization... ⏳"
                if copied_successful:
                    status_msg += " (Copied code to clipboard!)"
                    self.app.notify("Device code copied to clipboard automatically!", title="Clipboard")
                self.query_one("#polling-status-lbl", Label).update(status_msg)

                # Automatically open default system web browser to verification URL
                try:
                    import webbrowser
                    webbrowser.open(code_data["verification_url"])
                except Exception:
                    pass
                
                # Hide input fields to clean up display
                self.query_one("#client-id-input").display = False
                self.query_one("#client-secret-input").display = False
                for lbl in self.query(".login-field-lbl"):
                    lbl.display = False
                
                # Start background polling task using Textual run_worker
                self.device_code = code_data["device_code"]
                self.poll_task = self.run_worker(
                    self.poll_for_auth(client_id, client_secret, code_data["device_code"], code_data.get("interval", 5))
                )
            except Exception as e:
                event.button.disabled = False
                self.query_one("#polling-status-lbl", Label).update(f"⚠️ Error: {str(e)}")

    async def poll_for_auth(self, client_id: str, client_secret: str, device_code: str, interval: int):
        """Polls Google OAuth servers until token is issued, expires, or times out (30 mins)."""
        max_attempts = 360  # 30 minutes / 5-second interval
        attempts = 0
        while attempts < max_attempts:
            await asyncio.sleep(interval)
            attempts += 1
            try:
                token_data = await self.ms.poll_oauth_token(client_id, client_secret, device_code)
                if token_data and "access_token" in token_data:
                    # Success! Save credentials and dismiss
                    await self.ms.save_oauth_session(client_id, client_secret, token_data)
                    self.query_one("#polling-status-lbl", Label).update("✅ Connected successfully! Redirecting...")
                    await asyncio.sleep(1.5)
                    self.post_message(self.LoginSuccess())
                    self.dismiss(True)
                    break
            except Exception as e:
                # Expecting 'authorization_pending' standard error; keep polling
                err_msg = str(e).lower()
                if "pending" not in err_msg and "slow_down" not in err_msg:
                    self.query_one("#polling-status-lbl", Label).update(f"⚠️ Auth error: {str(e)}")
                    self.query_one("#connect-btn", Button).disabled = False
                    break
        else:
            self.query_one("#polling-status-lbl", Label).update("⚠️ Verification timed out. Please try again.")
            self.query_one("#connect-btn", Button).disabled = False

    def on_unmount(self):
        """Ensure background polling task is canceled when leaving screen."""
        if self.poll_task:
            try:
                self.poll_task.cancel()
            except Exception:
                pass
