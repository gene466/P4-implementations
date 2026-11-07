# SYN Cookie Proxy (P4 / BMv2)

> **Modernization note:** This directory is based on the original [SYN Cookie implementation](https://github.com/syn-proxy/P4-implementations/tree/master/bmv2/syn-cookie). The SYN Cookie design, P4 data-plane algorithm, and original control-plane implementation belong to the upstream authors. The `modern-bmv2-port` branch focuses on compatibility with a modern P4 VM, Python 3, and reproducible functional tests.

## Overview

This example implements an experimental TCP SYN proxy in a P4-programmable BMv2 switch. For an unrecognized TCP client, the proxy generates a SYN-ACK containing a cookie; the client must acknowledge the cookie before the proxy initiates the server-side handshake. After validation, the control plane receives BMv2 digest notifications and installs state used to translate TCP sequence/acknowledgment numbers between the two connections.

This is a **teaching/research prototype**, not a production security appliance. The implementation has known limitations, including incomplete TCP option handling and static cookie-related parameters; the functional tests below do not constitute a security or performance evaluation.

## Topology

```text
h1 (10.0.0.1) --\
                  s1 (BMv2 SYN Cookie Proxy) ---- h3 (10.0.0.3, HTTP :8080)
h2 (10.0.0.2) --/
      ^
      Scapy incomplete-SYN test
```

| Node | Role | Switch port |
| --- | --- | --- |
| `h1` | Legitimate HTTP client | `s1-eth1` / port 1 |
| `h2` | Client sending a SYN without completing the handshake | `s1-eth2` / port 2 |
| `h3` | HTTP server | `s1-eth3` / port 3 |
| `s1` | BMv2 `simple_switch`, Thrift TCP port 9090 | — |

## Quick start

See **[Complete tutorial: setup, execution, validation, troubleshooting](docs/RUN_MODERN_BMV2.md)** for prerequisite installation, the required Python environment, and details of the IPC socket fix.

The commands below assume the documented VM, dependencies already installed, and a checkout of `modern-bmv2-port`.

**Terminal 1 — BMv2 + Mininet:**

```bash
cd ~/P4-implementations/bmv2/syn-cookie
sudo /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/src/p4dev-python-venv/bin/p4run \
  --config p4app-modern.json
```

Keep the `mininet>` prompt open. **Terminal 2 — controller**, after the BMv2 socket exists:

```bash
cd ~/P4-implementations/bmv2/syn-cookie
sudo chgrp p4 /tmp/bmv2-1-notifications.ipc
sudo chmod 770 /tmp/bmv2-1-notifications.ipc
/home/p4/src/p4dev-python-venv/bin/python -u controller_py3.py
```

> The socket is recreated on BMv2 restart; repeat the permission adjustment each time. Running the controller before this fix can silently leave the connection table empty.

**Back in Mininet — normal connection:**

```text
mininet> h1 ping -c 3 10.0.0.3
mininet> h3 python3 -m http.server 8080 &
mininet> h1 curl -v --max-time 10 http://10.0.0.3:8080/
```

The expected application-level result is `HTTP/1.0 200 OK`. A successful HTTP request, together with new `connections` entries, shows that the normal proxy flow is operational in this environment.

**Incomplete handshake — one SYN from h2:**

```text
mininet> h2 /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/P4-implementations/bmv2/syn-cookie/test_incomplete_syn.py
```

Observe traffic at the switch interfaces as shown in the detailed tutorial. Expect a SYN on `s1-eth2`, a SYN-ACK sent back to h2, and **no matching h2:40001 → h3:8080 SYN on `s1-eth3`**. The local Linux kernel may return a RST because Scapy has not opened a TCP socket. The absence of a matching server-side SYN—not the debug message alone—is the relevant evidence.

## Files in this port

| File | Purpose |
| --- | --- |
| `p4src/proxy.p4` | P4 SYN Cookie proxy data plane (adapted for current BMv2/P4C) |
| `p4app-modern.json` | Current `p4-utils` / Mininet topology configuration |
| `s1-commands.txt` | IPv4 forwarding entries and mirror session |
| `controller_py3.py` | Python 3 digest listener and Thrift-based table updates |
| `test_incomplete_syn.py` | Single-SYN packet generator using Scapy |
| `p4app.json`, `controller.py` | Original example artifacts retained for comparison |

## Upstream attribution

This is a maintained *port of an existing implementation*. Credit for the original SYN Cookie mechanism and initial P4/controller implementation belongs to the [upstream SYN Proxy authors](https://github.com/syn-proxy/P4-implementations). The updates in this branch address build compatibility, controller APIs, topology configuration, environment-specific IPC permissions, documentation, and functional validation.

For the original SYN Cookie sequence-flow explanation and background, refer to the [upstream README](https://github.com/syn-proxy/P4-implementations/blob/master/bmv2/syn-cookie/README.md).
