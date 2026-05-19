import os
import subprocess
import socket
import json
import time
from pathlib import Path

class AudioPlayer:
    """Controls a background mpv process via a Unix domain socket using JSON-IPC."""
    
    SOCKET_PATH = "/tmp/yt-terminal-mpv.sock"
    
    def __init__(self):
        self.process = None
        self._start_mpv()

    def _start_mpv(self):
        """Launches the background mpv process in idle mode."""
        # Clean up stale socket file if it exists
        if os.path.exists(self.SOCKET_PATH):
            try:
                os.remove(self.SOCKET_PATH)
            except Exception:
                pass
                
        cmd = [
            "mpv",
            "--no-video",
            "--idle",
            f"--input-ipc-server={self.SOCKET_PATH}",
            "--af=lavfi=[astats=metadata=1]",
            "--volume=80"
        ]
        
        try:
            # Direct stderr/stdout to DEVNULL to avoid cluttering TUI
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Give mpv a moment to create the socket
            time.sleep(0.5)
        except FileNotFoundError:
            # mpv is not installed or not in PATH
            self.process = None

    def _send_command(self, cmd_args: list) -> dict:
        """Sends a JSON-IPC command to mpv over the Unix socket."""
        if not self.process or self.process.poll() is not None:
            # Process died or didn't start; try restarting it
            self._start_mpv()
            if not self.process:
                return {"error": "mpv process is not running"}

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(self.SOCKET_PATH)
            
            payload = json.dumps({"command": cmd_args}) + "\n"
            s.sendall(payload.encode("utf-8"))
            
            # Read first line of response
            data = b""
            while b"\n" not in data:
                chunk = s.recv(1024)
                if not chunk:
                    break
                data += chunk
            
            s.close()
            
            if data:
                line = data.decode("utf-8").split("\n")[0]
                return json.loads(line)
        except Exception as e:
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
        if self.process:
            try:
                self._send_command(["quit"])
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            
        if os.path.exists(self.SOCKET_PATH):
            try:
                os.remove(self.SOCKET_PATH)
            except Exception:
                pass

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

    def __del__(self):
        self.quit()
