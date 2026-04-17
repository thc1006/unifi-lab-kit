#!/usr/bin/env python3
"""Query USG info from MongoDB inside UniFi container."""
import paramiko

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

# Write JS to NAS, then copy into container
js_content = """
db.device.find().forEach(function(d){
    print("DEVICE: " + d.name + " type=" + d.type + " ip=" + d.ip + " state=" + d.state);
    print("  inform=" + d.inform_url);
    print("  adopted=" + d.adopted);
    print("  authkey=" + (d.x_authkey || "none").substring(0,50));
});
print("---MGMT---");
db.setting.find({key:"mgmt"}).forEach(function(d){
    print("ssh_user=" + d.x_ssh_username);
    print("ssh_pw=" + d.x_ssh_password);
    print("ssh_enabled=" + d.x_ssh_enabled);
});
"""

sftp = nas.open_sftp()
with sftp.open("/tmp/query_usg.js", "w") as f:
    f.write(js_content)
sftp.close()

# Copy to container
nas.exec_command("docker cp /tmp/query_usg.js unifi:/tmp/query_usg.js", timeout=5)

import time
time.sleep(1)

# Execute
_, out, _ = nas.exec_command(
    "docker exec unifi mongo --port 27117 --quiet ace /tmp/query_usg.js 2>&1",
    timeout=15,
)
print(out.read().decode().strip())

# Also scan for the new device the user just turned on
print("\n--- Scanning for new device ---")
import subprocess, socket
prev = {1,106,108,109,111,113,115,120,121,122,123,129,200,203,204,205,206,212,215,217,219,220,222}
for i in range(1, 255):
    ip = f"192.168.1.{i}"
    r = subprocess.run(["ping", "-n", "1", "-w", "300", ip], capture_output=True)
    if "TTL=" in r.stdout.decode(errors="replace") and i not in prev:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        ssh = s.connect_ex((ip, 22)) == 0
        s.close()
        print(f"  NEW: .{i} {ip} SSH:{'OPEN' if ssh else 'closed'}")

nas.close()
print("\n=== DONE ===")
