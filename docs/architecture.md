# Architecture — C4 Mermaid views

GitHub renders these natively. Re-render offline with `mmdc`.

---

## C4 — System Context

```mermaid
C4Context
    title mllab-network — system context
    Person(admin, "Lab administrator", "Runs make targets from a laptop")
    System_Boundary(lab, "Lab subnet") {
        System(usg, "USG-3P", "Edge gateway\nport-forwards & NAT")
        System(sw, "UniFi Switch", "L2 backbone")
        System(nas, "NAS", "Docker host: Controller + Samba")
        System_Ext(servers, "GPU servers (~10)", "Ubuntu; SSH + CUDA")
    }
    System_Ext(school, "University backbone", "Static /24, blocks port 445 egress")
    Rel(admin, usg, "SSH via LAN_GATEWAY or WAN_IP:22")
    Rel(admin, nas, "Controller UI :8443")
    Rel(usg, school, "WAN uplink")
    Rel(sw, usg, "Trunk to LAN interface")
    Rel(sw, nas, "")
    Rel(sw, servers, "")
```

---

## C4 — Container view (NAS)

```mermaid
C4Container
    title NAS Docker composition
    Person(admin, "Admin")
    System_Boundary(nas, "NAS host") {
        Container(samba, "Samba 4.15.13", "native apt package", "LAN file shares; bind 192.168.1.x:445")
        Container_Boundary(docker, "Docker engine") {
            Container(ctrl, "UniFi Controller", "lscr.io/linuxserver/unifi-network-application", "Device adoption & UI")
            Container(nginx, "wan-nginx", "nginx reverse proxy", "Public HTTPS endpoints")
            Container(services, "Legacy apps", "Nextcloud, HackMD, Overleaf, Pi-hole, MinIO", "On legacy-nat macvlan")
        }
    }
    Rel(admin, samba, "CIFS/SMB", "LAN only")
    Rel(admin, ctrl, "HTTPS 8443")
    Rel(ctrl, nginx, "manages")
```

---

## Flow — `make provision`

```mermaid
sequenceDiagram
    actor Admin
    participant Makefile
    participant usg.py
    participant USG as USG (EdgeOS)
    participant controller.py
    participant Controller as UniFi Controller

    Admin->>Makefile: make provision
    Makefile->>usg.py: python -m mllab_net.usg
    usg.py->>USG: SSH mllab@LAN_GATEWAY
    usg.py->>USG: configure; set WAN static
    usg.py->>USG: delete port-forward
    loop each rule from inventory
        usg.py->>USG: set port-forward rule N ...
    end
    usg.py->>USG: commit; save
    USG-->>usg.py: committed
    Makefile->>controller.py: python -m mllab_net.controller
    controller.py->>Controller: POST /api/login
    controller.py->>Controller: DELETE all /rest/portforward
    loop each rule
        controller.py->>Controller: POST /rest/portforward
    end
    controller.py->>Controller: PUT /rest/networkconf WAN=static
    controller.py->>USG: mca-cli-op set-inform http://NAS:8080/inform
    Controller-->>Admin: USG adopted, rules live
```

---

## Decision tree — "the network is broken"

```mermaid
flowchart TD
    A[Issue reported] --> B{Can I ping USG_LAN?}
    B -- No --> C[Switch / L2 problem<br/>check port LEDs]
    B -- Yes --> D{Can I ping WAN_GATEWAY?}
    D -- No --> E[WAN uplink down<br/>check with IT]
    D -- Yes --> F{make verify passes?}
    F -- No, port-forwards missing --> G[Re-run make provision-usg]
    F -- No, SSH auth fails --> H[Re-run make deploy-keys]
    F -- Yes --> I[Issue is host-specific<br/>inspect that one server]
    G --> J[make verify]
    H --> J
```
