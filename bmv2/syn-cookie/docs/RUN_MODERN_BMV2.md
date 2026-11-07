# Run the SYN Cookie Proxy on a Modern BMv2 VM

This tutorial documents the **`modern-bmv2-port` branch** of [gene466/P4-implementations](https://github.com/gene466/P4-implementations/tree/modern-bmv2-port). It consolidates the steps used for a functional end-to-end demonstration.

> **Scope:** Tested in the author's VMware-based Ubuntu 24.04 P4 development VM; not verified as a clean install on arbitrary Linux systems. This is an experimental BMv2 demonstration, not a production-grade SYN flood mitigation benchmark.

## 1. Environment and prerequisites

### Reference VM

- Use the [reference P4 VM image](https://drive.google.com/file/d/1_-Tr5mKCvjP1TCGQvjVTA5bqyNefGqSP/view?usp=sharing), and open it with VMware.
- Set the VM network adapter to **NAT** (the tested configuration).
- The documented shell user is `p4`; the Python environment is `/home/p4/src/p4dev-python-venv`.
- The VM should already provide `p4c-bm2-ss`, `simple_switch`, `simple_switch_CLI`, Mininet, and the P4 Python virtual environment. These are **preinstalled prerequisites**, not installed by this tutorial.

Verify the core executables:

```bash
command -v p4c-bm2-ss
command -v simple_switch
command -v simple_switch_CLI
ls -l /home/p4/src/p4dev-python-venv/bin/python
```

Install the tools used by the tutorial if they are missing:

```bash
sudo apt update
sudo apt install -y git curl tcpdump libnanomsg-dev
```

Make sure the Python virtual environment is active before executing the unqualified `python3` / `pip` commands below:

```bash
source /home/p4/src/p4dev-python-venv/bin/activate
which python3
python3 --version
```

### Repository checkout

```bash
cd ~
git clone https://github.com/gene466/P4-implementations.git
cd P4-implementations
git switch modern-bmv2-port
```

### Python dependencies

The tested VM uses a newer Python environment than the older `p4-utils` dependency pins. Installing `p4-utils` with all its historical dependencies can attempt to downgrade `grpcio` (notably a version incompatible with Python 3.12). The following is the **tested workaround**, not a general guarantee of dependency compatibility:

```bash
cd ~
git clone https://github.com/nsg-ethz/p4-utils.git
cd p4-utils

python3 -m pip install ipaddr ipaddress networkx
python3 -m pip install --no-deps -e .

python3 - <<'PY'
from p4utils.utils.topology import NetworkGraph
from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI
print('p4-utils imports OK')
PY
```

Also install `nnpy` (BMv2 Nanomsg digest notifications) and Scapy (the incomplete-SYN test):

```bash
python3 -m pip install nnpy scapy
python3 -c 'import nnpy, scapy; print("nnpy / Scapy OK")'
```

The local test used `networkx 3.7`, `grpcio 1.59.3`, and an existing Python 3.12-based venv; these values describe one working environment, not validated minimum/maximum requirements. `ipaddress` is in Python's standard library, but its separate package was installed in the original reproduction notes; remove it from the pip command only after verifying your controller imports still work.

## 2. Start BMv2 and Mininet

**Terminal A:**

```bash
cd ~/P4-implementations/bmv2/syn-cookie
sudo /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/src/p4dev-python-venv/bin/p4run \
  --config p4app-modern.json
```

The runner compiles `p4src/proxy.p4`, launches `simple_switch`, applies `s1-commands.txt`, and opens a `mininet>` prompt. Leave Terminal A running.

```text
mininet> nodes
mininet> net
```

In **Terminal B**, inspect the generated topology:

```bash
cd ~/P4-implementations/bmv2/syn-cookie
python3 - <<'PY'
from p4utils.utils.helper import load_topo
topo = load_topo('topology.json')
print('Switch thrift port:', topo.get_thrift_port('s1'))
print('Hosts:', list(topo.get_hosts()))
PY
```

Expected: `s1` Thrift port **9090** and hosts `h1`, `h2`, `h3`, with addresses `10.0.0.1`, `10.0.0.2`, `10.0.0.3` respectively.

The modernized branch already includes the corrected `mark_to_drop(standard_metadata)`, `SERVER_ADDRESS = 10.0.0.3`, modern topology JSON, and forwarding entries.

## 3. Start the Python 3 controller (critical IPC permission step)

When BMv2 is launched under `sudo`, its Nanomsg Unix socket may be root-owned and not writable by the ordinary `p4` user. A controller can appear to be waiting for messages even though it cannot connect.

In **Terminal B**, after the `mininet>` prompt exists:

```bash
cd ~/P4-implementations/bmv2/syn-cookie
ls -l /tmp/bmv2-1-notifications.ipc
sudo chgrp p4 /tmp/bmv2-1-notifications.ipc
sudo chmod 770 /tmp/bmv2-1-notifications.ipc
ls -l /tmp/bmv2-1-notifications.ipc
/home/p4/src/p4dev-python-venv/bin/python -u controller_py3.py
```

Expected socket mode (timestamp will differ):

```text
srwxrwx--- 1 root p4 ... /tmp/bmv2-1-notifications.ipc
```

Expected initial controller output:

```text
Connecting to notification sub: ipc:///tmp/bmv2-1-notifications.ipc
```

The controller remains in a receive loop. **Repeat the group/permission step after every BMv2 restart** because the socket may be recreated. Limit the permission change to this particular test VM/socket; do not grant world-write access.

## 4. Verify normal TCP and HTTP traffic

In **Terminal A** (`mininet>`):

```text
mininet> h1 ping -c 3 10.0.0.3
mininet> h3 python3 -m http.server 8080 &
mininet> h3 ss -ltnp
mininet> h1 curl -v --max-time 10 http://10.0.0.3:8080/
```

Expected: `ping` receives replies; `curl` returns **`HTTP/1.0 200 OK`** and an HTML directory listing. The controller should receive connection digests and install flow-state entries.

In **Terminal C**:

```bash
echo 'table_dump MyIngress.connections' | simple_switch_CLI --thrift-port 9090
```

Expected: non-empty entries once a successful connection has been processed. If HTTP times out after `Connected`, verify the socket permission, the running controller, digest output, and this table **before changing P4 code**.

## 5. Verify an incomplete TCP handshake

This functional test sends **a single SYN** from h2 without completing the three-way handshake. The goal is to observe that the SYN is intercepted and **does not trigger a matching server-side SYN**.

The test program is already included in the branch: `test_incomplete_syn.py`. It uses Scapy on `h2-eth0`, with TCP source port `40001`, destination `10.0.0.3:8080`, SYN flag, and sequence number `1000`.

**Terminal C — client-side switch interface:**

```bash
sudo tcpdump -i s1-eth2 -nn \
  'tcp and host 10.0.0.2 and host 10.0.0.3'
```

**Terminal D — server-facing switch interface:**

```bash
sudo tcpdump -i s1-eth3 -nn \
  'tcp and src host 10.0.0.2 and dst host 10.0.0.3 and src port 40001 and dst port 8080'
```

Start both monitors *before* sending the test packet. Then in **Terminal A**:

```text
mininet> h2 /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/P4-implementations/bmv2/syn-cookie/test_incomplete_syn.py
```

Expected on `s1-eth2`:

```text
10.0.0.2.40001 > 10.0.0.3.8080: Flags [S], seq 1000
10.0.0.3.8080 > 10.0.0.2.40001: Flags [S.], ack 1001
10.0.0.2.40001 > 10.0.0.3.8080: Flags [R]
```

The RST is normally generated by h2's Linux kernel, because Scapy did not open a normal kernel TCP socket. It is **not** proof of cookie validation. The important observation is that **no matching SYN appears on `s1-eth3`** for this source/destination tuple. Compare `connections` table entries before and after the test: the uncompleted connection should not add a new flow entry.

The controller may also print a `Debug: action executed successfully!` digest, but the message alone is not evidence of filtering. This one-SYN test demonstrates basic isolation only, **not** high-rate SYN-flood resistance.

## 6. Troubleshooting

| Symptom | Likely cause / next check |
| --- | --- |
| `ModuleNotFoundError: scapy` from Mininet | `h2 python3` may use system Python. Use `/home/p4/src/p4dev-python-venv/bin/python` and install Scapy in that venv. |
| `ModuleNotFoundError: nnpy` | Activate the P4 venv; install `libnanomsg-dev`, then `python3 -m pip install nnpy`. |
| `p4-utils` import failures | Use current imports (`load_topo`, `SimpleSwitchThriftAPI`); ensure editable install was done in the same venv. |
| P4 compilation error at `mark_to_drop()` | You may have checked out the upstream branch instead of `modern-bmv2-port`. |
| No `topology.json` | Start `p4run` successfully first, from `bmv2/syn-cookie`. |
| `Permission denied` connecting to `/tmp/bmv2-1-notifications.ipc` | Fix socket group/mode as in Section 3, and restart the controller. |
| Controller prints `Connecting...` but no digests / HTTP request times out | Look for `connections` entries; check `log/p4s.s1.log` for `Learning sample` and `Sending learning notification`; inspect socket mode. |
| `curl` prints `Connected` but no HTTP body | TCP client-to-proxy handshake alone is insufficient; verify controller digest delivery and server-side connection-state installation. |
| `curl` cannot connect | Check the HTTP server is listening on `h3`, the forwarding table, and `h1 ping -c 3 10.0.0.3`. |
| `tcpdump` sees TCP options/payload corruption | The original prototype does not fully handle all TCP options; disable timestamps/SACK/window scaling only as a controlled diagnostic, not as a general fix. |

Useful diagnostic commands:

```bash
# BMv2 packet traces (path generated by p4run)
grep -niE 'digest|learning|notification|error' log/p4s.s1.log | tail -80

# Forwarding entries
echo 'table_dump MyIngress.ipv4_lpm' | simple_switch_CLI --thrift-port 9090

# Flow state
echo 'table_dump MyIngress.connections' | simple_switch_CLI --thrift-port 9090
```

## 7. What this port changed vs. the upstream example

- Old P4 `mark_to_drop()` → `mark_to_drop(standard_metadata)`.
- Older `p4-utils` config/API → `p4app-modern.json` and `controller_py3.py` using `load_topo` + `SimpleSwitchThriftAPI`.
- Old sample topology addresses `10.0.1.x` → `10.0.0.x` forwarding entries and `SERVER_ADDRESS = 167772163` (`10.0.0.3`).
- BMv2 learning socket permissions: an **environment-specific runtime step**, not a source-code change.
- New Scapy-based single-SYN isolation test.

The original SYN Cookie implementation and protocol logic are credited to [syn-proxy/P4-implementations](https://github.com/syn-proxy/P4-implementations). This port has been functionally validated, but no comprehensive attack-throughput, security-hardening, or production-readiness claim is made.
