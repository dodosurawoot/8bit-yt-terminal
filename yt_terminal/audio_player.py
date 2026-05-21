import os
import subprocess
import socket
import json
import time
import tempfile
import shutil

class AudioPlayer:
    """Controls a background mpv process via a Unix domain socket using JSON-IPC."""
    
    def __init__(self):
        self.process = None
        self._socket_dir = tempfile.mkdtemp(prefix="yt-terminal-mpv-")
        os.chmod(self._socket_dir, 0o700)
        self.SOCKET_PATH = os.path.join(self._socket_dir, "mpv.sock")
        self._socket = None
        self._start_mpv()

    def _start_mpv(self):
        """Launches the background mpv process in idle mode."""
        if os.path.exists(self.SOCKET_PATH):
            try:
                os.remove(self.SOCKET_PATH)
            except Exception as e:
                log.debug(f"Failed to remove pre-existing socket {self.SOCKET_PATH}: {e}")
                
        cmd = [
            "mpv",
            "--no-video",
            "--idle",
            f"--input-ipc-server={self.SOCKET_PATH}",
            "--af=lavfi=[astats=metadata=1]",
            "--volume=80"
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Poll for socket creation (up to 3 seconds, 0.05s intervals)
            start_time = time.time()
            while time.time() - start_time < 3.0:
                if os.path.exists(self.SOCKET_PATH):
                    break
                time.sleep(0.05)
        except FileNotFoundError:
            self.process = None

    def _close_socket(self):
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                log.debug(f"Failed to close socket gracefully: {e}")
            self._socket = None

    def _ensure_connection(self) -> bool:
        """Ensures a long-lived socket connection to mpv."""
        if self._socket is not None:
            return True
            
        if not self.process or self.process.poll() is not None:
            self._close_socket()
            self._start_mpv()
            if not self.process:
                return False

        if not os.path.exists(self.SOCKET_PATH):
            return False

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.1)  # Low timeout for persistent IPC
            s.connect(self.SOCKET_PATH)
            self._socket = s
            return True
        except Exception:
            self._close_socket()
            return False

    def _send_command(self, cmd_args: list) -> dict:
        """Sends a JSON-IPC command to mpv over the persistent Unix socket."""
        if not self._ensure_connection():
            return {"error": "mpv process is not running or socket is unavailable"}

        try:
            payload = json.dumps({"command": cmd_args}) + "\n"
            self._socket.sendall(payload.encode("utf-8"))
            
            # Read first line of response
            data = b""
            while b"\n" not in data:
                chunk = self._socket.recv(4096)
                if not chunk:
                    # Connection closed by peer
                    self._close_socket()
                    return {"error": "connection closed by mpv"}
                data += chunk
            
            if data:
                line = data.decode("utf-8").split("\n")[0]
                return json.loads(line)
        except (socket.timeout, socket.error):
            # Socket timed out or errored: close it so we reconnect next time
            self._close_socket()
            # Retry once
            if self._ensure_connection():
                try:
                    payload = json.dumps({"command": cmd_args}) + "\n"
                    self._socket.sendall(payload.encode("utf-8"))
                    data = b""
                    while b"\n" not in data:
                        chunk = self._socket.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                    if data:
                        line = data.decode("utf-8").split("\n")[0]
                        return json.loads(line)
                except Exception:
                    self._close_socket()
        except Exception as e:
            self._close_socket()
            return {"error": str(e)}
            
        return {"error": "no response from mpv"}

    def play_url(self, url: str):
        """Loads a YouTube URL and starts playing it."""
        self._send_command(["loadfile", url, "replace"])
        # Ensure we unpause if it was paused
        self.set_pause(False)

    def set_pause(self, paused: bool):
        """Pauses or resumes playback."""
        self._send_command(["set_property", "pause", paused])

    def is_paused(self) -> bool:
        """Checks if the player is currently paused."""
        res = self._send_command(["get_property", "pause"])
        return res.get("data") is True if "data" in res else False

    def seek(self, position_seconds: float):
        """Seeks to a specific timestamp in seconds (absolute)."""
        self._send_command(["seek", position_seconds, "absolute"])

    def get_position(self) -> float:
        """Gets current playback position in seconds."""
        res = self._send_command(["get_property", "time-pos"])
        if "data" in res and res["data"] is not None:
            return float(res["data"])
        return 0.0

    def get_duration(self) -> float:
        """Gets total track duration in seconds."""
        res = self._send_command(["get_property", "duration"])
        if "data" in res and res["data"] is not None:
            return float(res["data"])
        return 0.0

    def get_volume(self) -> int:
        """Gets player volume (0-100)."""
        res = self._send_command(["get_property", "volume"])
        if "data" in res and res["data"] is not None:
            return int(res["data"])
        return 80

    def set_volume(self, volume: int):
        """Sets player volume (0-100)."""
        self._send_command(["set_property", "volume", max(0, min(100, volume))])

    def stop(self):
        """Stops playback."""
        self._send_command(["stop"])

    def quit(self):
        """Terminates the background mpv process and cleans up the socket."""
        self._close_socket()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception as e:
                log.debug(f"Failed to terminate mpv process: {e}")
                try:
                    self.process.kill()
                except Exception as ex:
                    log.debug(f"Failed to kill mpv process: {ex}")
            self.process = None
            
        if hasattr(self, "_socket_dir") and os.path.exists(self._socket_dir):
            shutil.rmtree(self._socket_dir, ignore_errors=True)

    def get_audio_level(self) -> float:
        """Queries mpv for current overall RMS level in dB and returns normalized linear amplitude (0.0 - 1.0)."""
        res = self._send_command(["get_property", "af-metadata"])
        try:
            if "data" in res and res["data"]:
                data = res["data"]
                rms_val = None
                
                def recurse(d):
                    nonlocal rms_val
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if "RMS_level" in k:
                                rms_val = v
                                return
                            recurse(v)
                    elif isinstance(d, list):
                        for item in d:
                            recurse(item)
                            
                recurse(data)
                if rms_val is not None:
                    db = float(rms_val)
                    # Convert dB to linear amplitude (-60dB to 0dB scale)
                    amp = max(0.0, min(1.0, (db + 60.0) / 60.0))
                    return amp
        except Exception:
            pass
        return 0.0
