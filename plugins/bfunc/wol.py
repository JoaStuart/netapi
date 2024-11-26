import socket
import config
from device.api import APIFunct


class Wol(APIFunct):

    def _send_wol(self, mac: str) -> None:
        # Format MAC and add FFh bytes
        mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        # Send wake message
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ("<broadcast>", 9))

    def api(self) -> dict | tuple[bytes, str]:
        if len(self.args) < 1:
            return {"wol": "You need to provide the config name of the device to wake."}

        try:
            mac = config.load_var(f"wol.{self.args[0]}")
        except:
            return {"wol": "This device is not registered in the config!"}

        self._send_wol(str(mac))

        return {"wol": "Sent wake up call."}
