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

## SYN-Authentication with Digest Implementation Visualization   
   
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

Simple forwarding switch implementation is extended to implement a control-plane mitigation mechanism for SYN-flood using SYN-authentication with reset on the first connection. After the client tries to connect to the server for the first time, the proxy responds with RST packet to reset the connection and then add the client source IP address to the white-list table in control plan. A legitimate client will try to reconnect, therefore, the white-list table will be checked if it does contain an entry for the client and then the connection can be forwarded to the server.


This implementation of SYN-Authentication is considered a control-plane approach since the white-list is implemented using a table in the control plane. In P4, in order to send data to control plan two approaches are available: copy to CPU approach that sends the whole packet using a specific port to the control plan controller to be processed. The second approach is Digest messages, where these message structure is defined in the P4 program and are sent to the control plan controller to be parsed accordingly, and then perform some operation on tables e.g. add, delete, update entries.

## Running on a modern BMv2 VM (`modern-bmv2-port`)

Use the VM and Python environment described in the [SYN Cookie setup guide](../syn-cookie/docs/RUN_MODERN_BMV2.md#1-environment-and-prerequisites). The original `p4app.json` and Python 2 `controller.py` are retained for comparison; use the modern files below.

**Terminal A, BMv2 and Mininet:**

```bash
cd ~/P4-implementations/bmv2/syn-auth-reset-digest
sudo /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/src/p4dev-python-venv/bin/p4run --config p4app-modern.json
```

**Terminal B, after the `mininet>` prompt appears:**

```bash
cd ~/P4-implementations/bmv2/syn-auth-reset-digest
sudo chgrp p4 /tmp/bmv2-1-notifications.ipc
sudo chmod 770 /tmp/bmv2-1-notifications.ipc
/home/p4/src/p4dev-python-venv/bin/python -u controller_py3.py
```

The socket is recreated on every BMv2 start, so repeat the permission commands. Wait for `Connecting to notification sub` before testing.

**Back in Mininet:**

```text
mininet> h3 python3 -m http.server 8080 &
mininet> h1 curl -v --max-time 10 http://10.0.0.3:8080/
```

The first `curl` should fail immediately: the switch answers the SYN with RST+ACK and sends a digest containing the client's source IP. Wait until the controller prints `Whitelisted: 10.0.0.1`, then run `h1 curl -v --max-time 10 http://10.0.0.3:8080/` again. The second request should return `HTTP/1.0 200 OK`. The controller is required: without it, the whitelist table is never updated.

For a single incomplete handshake, run `h2 /home/p4/src/p4dev-python-venv/bin/python test_incomplete_syn.py` at `mininet>`. Expect `h2:40001 -> h3:8080` SYN and an RST+ACK with `ack 1001` on the client-facing interface, but no matching SYN on the server-facing interface. The `pcap/s1-eth*_*.pcap` files or live `tcpdump` can be used to inspect packets.

The modern P4 change acknowledges the SYN in the RST and restricts authentication to pure SYNs; otherwise Linux ignores the reset or the switch may reset a server SYN-ACK. The controller installs a source-IP whitelist entry as soon as it receives the first SYN's digest. There is no proof that the source received the reset, no expiry, and a spoofed source can be admitted by a subsequent SYN. This is a functional demonstration, not a SYN-flood benchmark.
