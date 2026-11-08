# Implementations of TCP SYN proxies

This repository is a fork of [syn-proxy/P4-implementations](https://github.com/syn-proxy/P4-implementations), which provides implementations of TCP SYN proxy mechanisms using **P4/BMv2** and **Libmoon/DPDK**.

## Modern BMv2 / Python 3 port

The [`modern-bmv2-port`](https://github.com/gene466/P4-implementations/tree/modern-bmv2-port) branch contains a reproducibility-oriented modernization of the original **P4 SYN Cookie** example (`bmv2/syn-cookie`). It has been tested on a VMware Ubuntu 24.04 P4 development VM.

**[SYN Cookie overview and topology](bmv2/syn-cookie/README.md)** · **[Complete setup, run, and validation tutorial](bmv2/syn-cookie/docs/RUN_MODERN_BMV2.md)**

### What was updated in this fork

- Adapted the P4 program for the installed `v1model.p4` / modern `p4c-bm2-ss` interface (`mark_to_drop(standard_metadata)`).
- Added `p4app-modern.json` for the current `p4-utils` topology format.
- Updated IPv4 forwarding entries and the configured web-server address to the generated `10.0.0.x` topology.
- Ported the digest controller to Python 3 and the current `p4utils` Thrift API (`controller_py3.py`).
- Documented the BMv2 Nanomsg IPC socket permission issue and its fix.
- Added `test_incomplete_syn.py` and procedures for successful HTTP requests and incomplete TCP handshakes.

### SYN authentication with bloom filter

`bmv2/syn-auth-reset-bloomfilter` has also been ported (compile fix, modern config, plus fixes to the RST format and SYN-ACK handling). See **[its README](bmv2/syn-auth-reset-bloomfilter/README.md#running-on-a-modern-bmv2-vm-modern-bmv2-port-branch)**.

### Scope and limitations

These changes are an **environment compatibility port and functional validation**, not a new SYN Cookie algorithm or a production-hardened SYN-flood defense. The underlying P4 SYN Cookie design and original implementation are attributable to the [upstream authors](https://github.com/syn-proxy/P4-implementations). Passing the single-SYN isolation test does not establish resilience or performance under high-volume SYN flooding.

The documented setup is tied to the referenced P4 VM and paths; other Linux versions and newer `p4-utils` revisions may require adjustments. Review the upstream project's licensing/permissions before redistributing material outside the GitHub fork context.

## Other original implementations

- **Libmoon/DPDK:** `libmoon/`
- **Other P4/BMv2 examples:** `bmv2/`

For the original project and its research context, see [syn-proxy/P4-implementations](https://github.com/syn-proxy/P4-implementations).