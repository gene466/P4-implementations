# controller_py3.py

import nnpy
import struct
import ipaddress

from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI


class DigestController:

    def __init__(self, sw_name):
        self.sw_name = sw_name
        self.topo = load_topo("topology.json")
        self.thrift_port = self.topo.get_thrift_port(sw_name)
        self.controller = SimpleSwitchThriftAPI(self.thrift_port)

    def recv_msg_digest(self, msg):
        topic, device_id, ctx_id, list_id, buffer_id, num = (
            struct.unpack("<iQiiQi", msg[:32])
        )

        offset = 17
        msg = msg[32:]

        for _ in range(num):
            msg_type, arg1, arg2, arg3, arg4 = (
                struct.unpack("!BIIII", msg[:offset])
            )

            if msg_type == 0:
                print("----------------------------------------")
                print("Debug: action executed successfully!")
                print("Message:", msg_type, "data:", arg1,
                      "extra:", arg2)
                print("----------------------------------------")

            elif msg_type == 1:
                src = str(ipaddress.IPv4Address(arg1))
                dst = str(ipaddress.IPv4Address(arg2))

                print("message type:", msg_type,
                      "src ip:", src, "dst ip:", dst)

                self.controller.table_add(
                    "whitelist", "NoAction", [src]
                )

            elif msg_type == 2:
                for hash_value, diff in (
                    (arg1, arg2),
                    (arg3, arg4)
                ):
                    print("connection added with Hash:",
                          hash_value, "diff:", diff)

                    self.controller.table_add(
                        "connections",
                        "saveDifferenceValue",
                        [str(hash_value)],
                        [str(diff)]
                    )

            else:
                print("Unknown message type:", msg_type)

            msg = msg[offset:]

        self.controller.client.bm_learning_ack_buffer(
            ctx_id, list_id, buffer_id
        )

    def run_digest_loop(self):
        sub = nnpy.Socket(nnpy.AF_SP, nnpy.SUB)

        notifications_socket = (
            self.controller.client
            .bm_mgmt_get_info()
            .notifications_socket
        )

        print("Connecting to notification sub:",
              notifications_socket)

        sub.connect(notifications_socket)

        sub.setsockopt(
            nnpy.SUB,
            nnpy.SUB_SUBSCRIBE,
            b""
        )

        try:
            while True:
                msg = sub.recv()
                self.recv_msg_digest(msg)
        except KeyboardInterrupt:
            print("\nController stopped.")
        finally:
            sub.close()


def main():
    DigestController("s1").run_digest_loop()


if __name__ == "__main__":
    main()
