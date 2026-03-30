from fastapi import APIRouter, HTTPException
import socket
import json

router = APIRouter(prefix="/api/control", tags=["control"])

PCG_SOCKET_PATH = "/tmp/pcg.sock"


def _send_to_pcg(command: str, value: float) -> dict:
    payload = json.dumps({"command": command, "value": value}).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3.0)
            sock.connect(PCG_SOCKET_PATH)
            sock.sendall(payload)
            return json.loads(sock.recv(1024))
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError) as e:
        raise HTTPException(status_code=503, detail=f"PCG connection failed: {e}")


@router.post("/pump_duty")
def set_pump_duty(duty: float) -> dict:
    if not 0 <= duty <= 100:
        raise HTTPException(status_code=400, detail="duty must be between 0 and 100")
    return _send_to_pcg("set_pump_duty", duty)


@router.post("/fan_voltage")
def set_fan_voltage(voltage: float) -> dict:
    if not 0 <= voltage <= 12:
        raise HTTPException(status_code=400, detail="voltage must be between 0 and 12")
    return _send_to_pcg("set_fan_voltage", voltage)
