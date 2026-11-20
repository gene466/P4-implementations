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

## SYN-Authentication with cookie Implementation Visualization   
   
        Client                          Proxy                         Server
        
                          SYN
                   ---------------->
                   seq = x, ack = 0
                                     check if source IP address is in the whitelist
                                     if white-listed --> forward
                                     o.w 
                                     k= createCookie({srcAddr,dstAddr,srcPort,dstPort,protocol},MSS, time)
                                     seq= k
                        SYN-ACK     
                  <-----------------
                  seq = k, ack = x+1
                  
                         ACK
                  ------------------>
                  seq = x+1, ack = k+1  
                                     verify the cookie value k from the acknowledgment
                                     if valid cookie --> IP address is added to whitelist
                                     then reset the connection similar to SYN-Authentication
                                     o.w --> drop packet
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

Simple forwarding switch implementation is extended to implement a control-plane mitigation mechanism for SYN-flood using SYN-authentication with syn-cookie for verifying legitimate client on first use. This is considered a hybrid approach between SYN-authentication with connection reset and syn-cookie generation from the client's information. When a valid cookie is received by the proxy the client is white-listed and the connection is reset. A legitimate client will try to reconnect, therefore, the white-list table will be checked if it does contain an entry for the client and then the connection can be forwarded to the server.


This implementation of SYN-Authentication with cookies is considered a control-plane approach since the white-list is implemented using a table in the control plan. In P4, in order to send data to control plan two approaches are available: copy to CPU approach that sends the whole packet using a specific port to the control plan controller to be processed. The second approach is Digest messages, where these message structure is defined in the P4 program and are sent to the control plan controller to be parsed accordingly, and then perform some operation on tables e.g. add, delete, update entries. 

This approach is not fully transparent to the client, although the cookie generation and validation are totally transparent, the connection reset can be noticed by the client. the cookie is generated from the 5-tuple (srcAddr,dstAddr,srcPort,dstPort, protocol) in addition to MSS and time information to generate 32bit value that is used as a sequence number for the SYN-ACK packet sent to the client. Once the client responds with ACK packet with correct ack that contains the correct cookie value, the client is then verified and considered legitimate, therefore, the client IP address will be added to the white-list table in control plane and the connection is reset using RST packet. 

## Running on a modern BMv2 VM (`modern-bmv2-port`)

Use the VM and Python environment described in the [SYN Cookie setup guide](../syn-cookie/docs/RUN_MODERN_BMV2.md#1-environment-and-prerequisites). Run this example from its own directory. The original `p4app.json` and Python 2 `controller.py` are retained for comparison; use `p4app-modern.json` and `controller_py3.py` here.

**Terminal A, BMv2 and Mininet:**

```bash
cd ~/P4-implementations/bmv2/syn-auth-cookie
sudo /home/p4/src/p4dev-python-venv/bin/python \
  /home/p4/src/p4dev-python-venv/bin/p4run --config p4app-modern.json
```

**Terminal B, after the `mininet>` prompt appears:**

```bash
cd ~/P4-implementations/bmv2/syn-auth-cookie
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

The first `curl` should fail with a TCP reset. The switch answered the initial SYN with a cookie SYN-ACK, checked the client's ACK, sent a digest, and reset that established client-side connection. Wait until the controller prints `Whitelisted: 10.0.0.1` and `Whitelisted: 10.0.0.3`, then run `h1 curl -v --max-time 10 http://10.0.0.3:8080/` again. The second request should return `HTTP/1.0 200 OK`. The controller adds both IPs because the table matches source IP for traffic in both directions.

For a single incomplete handshake, run `h2 /home/p4/src/p4dev-python-venv/bin/python test_incomplete_syn.py` at `mininet>`. The client-side interface should show a SYN and cookie SYN-ACK. No matching `h2:40001 -> h3:8080` **SYN** should appear on the server-facing interface. The `h2` kernel may answer the SYN-ACK with a RST, which can be forwarded toward the server; that RST is not a completed handshake. Use the `pcap/s1-eth*_*.pcap` files or live `tcpdump` to inspect packets.

This is a functional compatibility port, not a secure SYN-flood defense. Cookie generation uses fixed time/MSS values and an unkeyed CRC; a correct ACK in this prototype is not strong proof of source ownership. After validation, the whitelist is keyed only by source IP, with no expiry. The first legitimate request is deliberately reset and must be retried.

