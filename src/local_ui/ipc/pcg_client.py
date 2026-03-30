import socket
import json

PCG_SOCKET_PATH = "/tmp/pcg.sock"


class PcgClient:
    """IPC client communicating with PCG via Unix Domain Socket."""

    def send_control(self, command: str, value: float) -> dict:
        payload = json.dumps({"command": command, "value": value}).encode()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(3.0)
                sock.connect(PCG_SOCKET_PATH)
                sock.sendall(payload)
                response = sock.recv(1024)
                return json.loads(response)
        except (ConnectionRefusedError, FileNotFoundError, TimeoutError) as e:
            return {"status": "error", "detail": str(e)}
