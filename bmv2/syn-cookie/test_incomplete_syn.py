
from scapy.all import Ether, IP, TCP, sendp, get_if_hwaddr

iface = "h2-eth0"

pkt = (
    Ether(
        src=get_if_hwaddr(iface),
        dst="00:00:0a:00:00:03"
    )
    / IP(
        src="10.0.0.2",
        dst="10.0.0.3"
    )
    / TCP(
        sport=40001,
        dport=8080,
        flags="S",
        seq=1000
    )
)

pkt.show2()

# 只送一個 SYN，不主動回覆 ACK
sendp(pkt, iface=iface, count=1, verbose=True)
