#!/usr/bin/env python3
"""Install native Samba on NAS, bind to 192.168.1.129 only. Zero downtime."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")


def run(cmd, timeout=30):
    _, out, err = nas.exec_command(cmd, timeout=timeout)
    return out.read().decode().strip(), err.read().decode().strip()


# Step 1: Install samba (but don't start yet)
print("\n=== Step 1: Install Samba ===")
out, err = run("sudo apt-get update -qq 2>&1 | tail -1", 60)
print(f"  apt update: {out}")

# Stop smbd/nmbd before install to prevent auto-start on 0.0.0.0
out, err = run("sudo apt-get install -y -qq samba 2>&1 | tail -3", 120)
print(f"  apt install: {out}")

# Immediately stop to prevent port conflict
run("sudo systemctl stop smbd nmbd 2>/dev/null")
print("  Stopped smbd/nmbd")

# Verify version
out, _ = run("smbd --version 2>/dev/null")
print(f"  Version: {out}")

# Step 2: Write smb.conf
print("\n=== Step 2: Configure smb.conf ===")

smb_conf = """[global]
   # Server identity
   workgroup = MLLAB
   server string = MLLAB NAS
   netbios name = MLLAB-NAS

   # Security - bind ONLY to LAN interface
   bind interfaces only = yes
   interfaces = 192.168.1.129
   hosts allow = 192.168.1.0/24
   hosts deny = 0.0.0.0/0

   # Protocol security
   server min protocol = SMB2_10
   disable netbios = yes
   wins support = no

   # Authentication
   security = user
   map to guest = never
   passdb backend = tdbsam

   # Performance (ML workload optimized)
   aio read size = 1
   aio write size = 1
   use sendfile = yes

   # Logging
   log file = /var/log/samba/log.%m
   max log size = 1000
   log level = 1

[MLLAB-public]
   comment = Student shared folders
   path = /mllab_nas/MLLAB-public
   browseable = yes
   read only = no
   create mask = 0775
   directory mask = 0775
   valid users = mllab

[server]
   comment = Server backups and datasets
   path = /mllab_nas/server
   browseable = yes
   read only = no
   create mask = 0775
   directory mask = 0775
   valid users = mllab

[datasets]
   comment = ML Datasets (read-only)
   path = /mllab_nas/server/datasets
   browseable = yes
   read only = yes
   guest ok = no
   valid users = mllab
"""

# Backup original config
run("sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak 2>/dev/null")

# Write new config
sftp = nas.open_sftp()
with sftp.open("/tmp/smb.conf", "w") as f:
    f.write(smb_conf)
sftp.close()
time.sleep(1)

run("sudo cp /tmp/smb.conf /etc/samba/smb.conf")
print("  smb.conf written")

# Verify config
out, _ = run("testparm -s 2>/dev/null | head -5")
print(f"  testparm: {out}")

# Step 3: Create Samba user
print("\n=== Step 3: Create Samba user ===")
out, _ = run("(echo 'examplepass'; echo 'examplepass') | sudo smbpasswd -a mllab 2>&1")
if "no such user" in out.lower():
    # Create system user first
    run("sudo useradd -M -s /usr/sbin/nologin mllab 2>/dev/null")
    out, _ = run("(echo 'examplepass'; echo 'examplepass') | sudo smbpasswd -a mllab 2>&1")
print(f"  smbpasswd: {out}")

# Also add god user
out, _ = run("(echo 'examplepass'; echo 'examplepass') | sudo smbpasswd -a god 2>&1")
print(f"  god user: {out}")

# Step 4: Start Samba
print("\n=== Step 4: Start Samba ===")
run("sudo systemctl start smbd")
run("sudo systemctl enable smbd")
time.sleep(2)

out, _ = run("systemctl is-active smbd")
print(f"  smbd: {out}")

out, _ = run("sudo ss -tlnp | grep 445")
print(f"  Port 445: {out}")

# Step 5: Verify from another server
print("\n=== Step 5: Verify ===")
nas.close()

# Connect to Pro6000 to test
srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect("192.168.1.123", username="ops", password="examplepass", timeout=5)
print("  Testing from Pro6000...")

# Install smbclient if needed
out, _ = srv.exec_command("which smbclient 2>/dev/null || echo missing", timeout=5)
result = out.read().decode().strip()
if "missing" in result:
    srv.exec_command("sudo apt-get install -y -qq smbclient 2>&1", timeout=60)
    time.sleep(3)

_, out, _ = srv.exec_command(
    "smbclient -L //192.168.1.129 -U mllab%examplepass 2>&1", timeout=15
)
print(f"  SMB shares:\n{out.read().decode().strip()}")

srv.close()
print("\n=== DONE ===")
print("\nSMB access: \\\\192.168.1.129\\MLLAB-public")
print("Username: mllab  Password: examplepass")
