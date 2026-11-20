# P4/BMv2 SYN proxy examples

This directory contains four experimental TCP SYN proxy examples. Their READMEs explain how to run each one on the modern BMv2 VM. The distinction below matters when interpreting the `test_incomplete_syn.py` result: **blocking one SYN does not imply that a second SYN from the same source will be blocked**.

| Example | When the server first sees a client SYN | State used afterward |
| --- | --- | --- |
| [SYN-authentication with reset and digest](syn-auth-reset-digest/README.md) | After the first SYN causes a digest and the controller installs a whitelist entry | Source IP in a control-plane table |
| [SYN-authentication with reset and Bloom filter](syn-auth-reset-bloomfilter/README.md) | On the second SYN for the same source IP, destination IP, destination port, and protocol | Two bits in a data-plane Bloom filter; source port is excluded |
| [SYN-authentication with cookie](syn-auth-cookie/README.md) | After a valid cookie ACK is received and the controller installs a whitelist entry; the client must reconnect after the reset | Source IP in a control-plane table |
| [SYN Cookie proxy](syn-cookie/README.md) | Only after a valid cookie ACK starts the server-side handshake | Per-connection state; the source-IP whitelist code is disabled |

## Why two reset methods admit a second SYN

Both reset methods respond to an unknown source's first SYN with RST+ACK. They also set whitelist state **because the SYN arrived**, without checking whether the sender received the reset or completed a handshake:

- **Reset with digest:** The first SYN sends a digest. Once `controller_py3.py` adds the source IP to `MyIngress.whitelist`, another SYN from that IP is forwarded, even to a different destination or port covered by the forwarding table. The second packet may arrive before the controller has installed the entry; in that case it is reset again.
- **Reset with Bloom filter:** The first SYN sets two filter bits immediately. Another SYN with the same source IP, destination IP, destination port, and protocol is forwarded, even if its TCP source port changes. Different tuples can also be admitted by Bloom filter false positives.

For example, running the single-SYN Scapy script twice from `h2` to `h3:8080` can show a first SYN stopped at `s1` and a second SYN on `s1-eth3`. A server SYN-ACK in response to the second packet confirms that the SYN reached `h3`. Scapy has no matching TCP socket, so the `h2` kernel may then send a RST. That RST does not mean the server never received the SYN; it also does not show that a full TCP connection was established.

The single-SYN tests in the individual READMEs demonstrate **first-attempt isolation only**. A repeated or spoofed source can pass these reset mechanisms once its whitelist state is set. The digest variant grants access by source IP; the Bloom filter variant uses the tuple described above. Neither state expires while the switch runs, and neither test establishes resistance to a sustained SYN flood.

The cookie-based examples require an ACK that matches the SYN-ACK cookie before their respective server-side or whitelist steps. Sending two SYNs alone does not satisfy that check. These are still research prototypes: their cookie computation uses fixed parameters and an unkeyed CRC, and `syn-auth-cookie` later trusts a source-IP whitelist. A successful functional test is not a security evaluation.
