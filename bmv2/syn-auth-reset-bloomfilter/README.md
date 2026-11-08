## Topology 


```
                                +--+      
                     client     |h1+----|
                                +--+    |    P4
                                        |   +--+     +--+
                                        |---+s1+-----+h3+  WebServer
                                        |   +--+     +--+
                                +--+    |  Proxy     
                     Attacker   |h2+----|
                                +--+      

```

The topology consists of 3 hosts (h1, h2, h3) and one P4 programmable switch (S1).

- **h1**: client.
- **h2**: attacker.
- **h3**: webserver.
- **s1**: P4 proxy.

## SYN-Authentication with Bloom filter Implementation Visualization   
   
        Client                          Proxy                         Server
        
                          SYN
                   ---------------->
                   seq = x, ack = 0
                                     check if source IP address is in the whitelist
                                     if white-listed --> forward
                                     o.w --> Reset connection
                          RST
                   <---------------       
        
    legitimate client reconnects
    
                         SYN
                   ---------------->   source IP is white-listed
                   seq = x, ack = 0
             
                                        Forward
                                   
                                   
                                                          SYN
                                                     --------------->
                                                     seq = x, ack = 0
                                   
                                                         SYN-ACK
                                       Forward      <----------------
                                                    seq = r, ack = x+1
                       SYN-ACK
                  <----------------   
                  seq = r, ack = x+1

                          ACK
                  ----------------->
                  seq = x+1, ack = r+1
                                      
                                      Forward

                                                          ACK
                                                    ----------------->
                                                    seq = x+1, ack = r+1

                      HTTP GET                           HTTP GET
                 ----------------->    FORWARD     ------------------>
                 seq = x+1, ack = r+1               seq = x+1, ack = r+1
    
                       ACK                                ACK
                 <-----------------     FORWARD     <------------------
                 seq = r+1, ack = x+1+payload      seq = r+1, ack = x+1+payload
                                          .
                                          .
                                          .
                                        FIN
                                  ---------------->    
                                  
                                       FIN-ACK
                                  <----------------
                                  
                                        ACK
                                  ---------------->


## Description 

Simple forwarding switch implementation is extended to implement a data-plane mitigation mechanism for SYN-flood using SYN-authentication with reset on the first connection. After the client tries to connect to the server for the first time, the proxy responds with a RST packet to reset the connection and then add the client source IP address to the bloom filter. A legitimate client will try to reconnect, therefore, the bloom filter will be checked if it does contain an entry for the client and then the connection can be forwarded to the server.


This implementation of SYN-Authentication is considered a data-plane the only approach since the white-list is implemented using a bloom filter. In P4 a bloom filter is implemented using register with a length of 4096 bits and width of 1 bit, also 2 hashes are computed for adding entries to the bloom filter. 

## Running on a modern BMv2 VM (`modern-bmv2-port` branch)

Environment setup (VM, `p4-utils`, Scapy) is identical to the SYN Cookie port; follow sections 1–2 of [`../syn-cookie/docs/RUN_MODERN_BMV2.md`](../syn-cookie/docs/RUN_MODERN_BMV2.md), but start the runner from this directory:

```bash
cd ~/P4-implementations/bmv2/syn-auth-reset-bloomfilter
sudo /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/src/p4dev-python-venv/bin/p4run \
  --config p4app-modern.json
```

**No controller is needed.** The whitelist is a P4 register (bloom filter) updated entirely in the data plane; the program emits no digests. The legacy `controller.py` is Python 2 and unused.

### Verify the first-connection reset

```text
mininet> h3 python3 -m http.server 8080 &
mininet> h1 curl -v --max-time 10 http://10.0.0.3:8080/
mininet> h1 curl -v --max-time 10 http://10.0.0.3:8080/
```

Expected: the first `curl` fails immediately with `Connection refused` (the proxy answered the SYN with a RST and added `10.0.0.1 → 10.0.0.3:8080` to the bloom filter); the second returns `HTTP/1.0 200 OK`. On `s1-eth1` the first attempt looks like:

```text
10.0.0.1.43442 > 10.0.0.3.8080: Flags [S], seq 2672981902
10.0.0.3.8080 > 10.0.0.1.43442: Flags [R.], seq 0, ack 2672981903
```

and nothing for that attempt appears on `s1-eth3` (server side).

### Verify a single unauthenticated SYN

Run `sudo tcpdump -i s1-eth2 -nn tcp` and `sudo tcpdump -i s1-eth3 -nn tcp` on separate new terminals, respectively, then:

```text
mininet> h2 /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/P4-implementations/bmv2/syn-auth-reset-bloomfilter/test_incomplete_syn.py
```

Expected on `s1-eth2`: `Flags [S], seq 1000` followed by `Flags [R.], seq 0, ack 1001`; nothing on `s1-eth3`.

Inspect the filter: `echo 'register_read MyIngress.bloom_filter' | simple_switch_CLI --thrift-port 9090` (bits set to 1 = whitelisted entries).

### What the port changed

- `mark_to_drop()` → `mark_to_drop(standard_metadata)` (required by current `v1model.p4`).
- `p4app-modern.json` and `10.0.0.x` forwarding entries in `s1-commands.txt`, same as the SYN Cookie port.
- **RST fix:** the original RST had `ACK=0, ack=0`. Linux ignores such a RST in `SYN_SENT`, so the client silently retransmitted the SYN ~1 s later and was let through; the reset was never observed. The RST now follows RFC 793 (`SEQ=0, ACK=1, ack=SEG.SEQ+1`).
- **SYN-ACK fix:** the whitelist check matched any segment with `SYN=1`, including the server's SYN-ACK, so the switch reset the *server* on every new client port. The check is now limited to pure SYNs (`syn == 1 && ack == 0`).
- Added `test_incomplete_syn.py` (reused from `../syn-cookie`).

### Limitations

The filter is set on the first SYN regardless of whether the client ever retries, so any non-spoofing host passes on its second SYN; only spoofed one-shot SYNs are blocked. The 4096×1-bit filter has no aging/reset and false positives grow with the number of distinct (src, dst, dport) tuples. This is a functional demonstration, not a SYN-flood benchmark.
