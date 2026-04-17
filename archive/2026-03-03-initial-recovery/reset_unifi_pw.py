#!/usr/bin/env python3
"""Reset UniFi Controller admin password via MongoDB."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Step 1: Generate hash locally on NAS
_, out, _ = nas.exec_command(
    "python3 -c 'import crypt; print(crypt.crypt(\"examplepass\", crypt.mksalt(crypt.METHOD_SHA512)))'",
    timeout=5,
)
new_hash = out.read().decode().strip()
print(f"Hash: {new_hash[:40]}...")

# Step 2: Write a JS script for mongo
js_script = f'''
db.admin.updateOne(
  {{"name": "ops"}},
  {{$set: {{"x_shadow": "{new_hash}"}}}}
);
print("Updated");
var admin = db.admin.findOne({{"name": "ops"}});
print("Verify: " + admin.x_shadow.substring(0, 30));
'''

# Write JS to NAS filesystem
sftp = nas.open_sftp()
with sftp.open("/tmp/update_pw.js", "w") as f:
    f.write(js_script)
sftp.close()
print("JS script written")

# Step 3: Copy to container and execute
nas.exec_command("docker cp /tmp/update_pw.js unifi:/tmp/update_pw.js", timeout=5)
time.sleep(1)

_, out, _ = nas.exec_command(
    "docker exec unifi mongo --port 27117 ace /tmp/update_pw.js 2>&1",
    timeout=15,
)
print(f"Mongo: {out.read().decode().strip()}")

# Step 4: Test login
time.sleep(1)
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' 2>&1",
    timeout=15,
)
result = out.read().decode().strip()
print(f"Login: {result[:200]}")

if '"ok"' in result:
    print("\nSUCCESS! You can now login at https://192.168.1.129:8443")
    print("  Username: mllab")
    print("  Password: examplepass")

nas.close()
print("\n=== DONE ===")
