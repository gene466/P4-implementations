"""Install client and server IP whitelist entries after cookie validation."""

import ipaddress
import struct

import nnpy
from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI


class DigestController:
    def __init__(self, sw_name="s1"):
        topo = load_topo("topology.json")
        self.controller = SimpleSwitchThriftAPI(topo.get_thrift_port(sw_name))
        self.installed = set()

    def recv_msg_digest(self, msg):
        if len(msg) < 32:
            raise ValueError("short BMv2 digest header")
        _, _, ctx_id, list_id, buffer_id, count = struct.unpack("<iQiiQi", msg[:32])
        payload = msg[32:]
        if len(payload) < 9 * count:
            raise ValueError("short BMv2 digest payload")

        for offset in range(0, 9 * count, 9):
            _, src, dst = struct.unpack("!BII", payload[offset:offset + 9])
            # The table matches source IP for traffic in both directions.
            for raw_address in (src, dst):
                address = str(ipaddress.IPv4Address(raw_address))
                if address not in self.installed:
                    self.controller.table_add("whitelist", "NoAction", [address])
                    self.installed.add(address)
                    print("Whitelisted:", address, flush=True)

        self.controller.client.bm_learning_ack_buffer(ctx_id, list_id, buffer_id)

    def run_digest_loop(self):
        sub = nnpy.Socket(nnpy.AF_SP, nnpy.SUB)
        socket_path = self.controller.client.bm_mgmt_get_info().notifications_socket
        print("Connecting to notification sub:", socket_path, flush=True)
        sub.connect(socket_path)
        sub.setsockopt(nnpy.SUB, nnpy.SUB_SUBSCRIBE, b"")
        try:
            while True:
                self.recv_msg_digest(sub.recv())
        except KeyboardInterrupt:
            print("Controller stopped.")
        finally:
            sub.close()


if __name__ == "__main__":
    DigestController().run_digest_loop()
