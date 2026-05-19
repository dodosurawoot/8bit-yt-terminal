import asyncio
from textual.screen import Screen
from textual.widgets import Label, Input, Button, Static
from textual.containers import Vertical, Horizontal, Grid
from textual.reactive import reactive
from textual.message import Message
from lany_music_cli.music_service import MusicService
from lany_music_cli.config_manager import ConfigManager

class LoginScreen(Screen):
    """Screen for handling YouTube Music OAuth device registration flow."""
    
    DEFAULT_CSS = """
    LoginScreen {
        align: center middle;
        background: #432832 50%;
    }

    #login-box {
        width: 60;
        height: auto;
        border: thick #7a5260;
        background: #4f313c;
        padding: 2;
        border-title-color: #d38e91;
    }

    .login-title {
        text-align: center;
        color: #d38e91;
        text-style: bold;
        margin-bottom: 1;
    }

    .login-desc {
        text-align: center;
        margin-bottom: 2;
        color: #a68894;
    }

    .login-field-lbl {
        margin-top: 1;
        color: #fbe5e6;
    }

    .login-field {
        margin-bottom: 1;
        border: tall #7a5260;
    }

    #btn-container {
        align: center middle;
        margin-top: 2;
    }

    .action-btn {
        width: 100%;
        background: #d38e91;
        color: #fbe5e6;
    }

    #oauth-details-box {
        border: dashed #7a5260;
        padding: 1 2;
        margin-top: 1;
        margin-bottom: 1;
        background: #432832;
        align: center middle;
    }

    .oauth-url {
        text-style: underline;
        color: #d38e91;
        text-align: center;
    }

    .oauth-code {
        text-align: center;
        text-style: bold;
        color: #fbe5e6;
        background: #432832;
        padding: 1 3;
        margin: 1 0;
    }

    .status-msg {
        text-align: center;
        color: #d38e91;
        margin-top: 1;
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
            yield Label("🎵  LANY Music CLI Player", classes="login-title")
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

            with Vertical(id="oauth-details-container", visible=False) as details:
                yield Label("1. Go to the verification URL in your browser:", classes="login-desc")
                yield Label("", id="verification-url-lbl", classes="oauth-url")
                yield Label("2. Enter this device authorization code:", classes="login-desc")
                yield Label("XXXX-XXXX", id="user-code-lbl", classes="oauth-code")
                yield Label("Waiting for you to authorize standard Google access...", id="polling-status-lbl", classes="status-msg")

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
                code_data = await self.ms.get_oauth_code(client_id, client_secret)
                
                # Show OAuth directions panel
                self.query_one("#oauth-details-container").visible = True
                self.query_one("#verification-url-lbl", Label).update(code_data["verification_url"])
                self.query_one("#user-code-lbl", Label).update(f"  {code_data['user_code']}  ")
                self.query_one("#polling-status-lbl", Label).update("Waiting for your authorization... ⏳")
                
                # Hide input fields to clean up display
                self.query_one("#client-id-input").visible = False
                self.query_one("#client-secret-input").visible = False
                self.query_one(".login-field-lbl").visible = False
                
                # Start background polling task
                self.device_code = code_data["device_code"]
                self.poll_task = asyncio.create_task(
                    self.poll_for_auth(client_id, client_secret, code_data["device_code"], code_data.get("interval", 5))
                )
            except Exception as e:
                event.button.disabled = False
                self.query_one("#polling-status-lbl", Label).update(f"⚠️ Error: {str(e)}")

    async def poll_for_auth(self, client_id: str, client_secret: str, device_code: str, interval: int):
        """Polls Google OAuth servers until token is issued or expires."""
        while True:
            await asyncio.sleep(interval)
            try:
                token_data = await self.ms.poll_oauth_token(client_id, client_secret, device_code)
                if token_data and "access_token" in token_data:
                    # Success! Save credentials and dismiss
                    await self.ms.save_oauth_session(client_id, client_secret, token_data)
                    self.query_one("#polling-status-lbl", Label).update("✅ Connected successfully! Redirecting...")
                    await asyncio.sleep(1.5)
                    self.post_message(self.LoginSuccess())
                    break
            except Exception as e:
                # Expecting 'authorization_pending' standard error; keep polling
                err_msg = str(e).lower()
                if "pending" not in err_msg and "slow_down" not in err_msg:
                    self.query_one("#polling-status-lbl", Label).update(f"⚠️ Auth error: {str(e)}")
                    self.query_one("#connect-btn", Button).disabled = False
                    break

    def on_unmount(self):
        """Ensure background polling task is canceled when leaving screen."""
        if self.poll_task and not self.poll_task.done():
            self.poll_task.cancel()
