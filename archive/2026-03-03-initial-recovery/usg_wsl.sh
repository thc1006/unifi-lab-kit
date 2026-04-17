#!/usr/bin/env bash
# Use sshpass or expect to connect to USG with the real password

PASS="examplewifipass"
USER="ops"
HOST="192.168.1.1"

echo "=== Testing SSH connection to USG ==="
echo "User: $USER, Host: $HOST"
echo ""

# Method 1: Try with SSH_ASKPASS
export SSH_ASKPASS_REQUIRE=force
export SSH_ASKPASS="/tmp/askpass.sh"
echo "#!/bin/bash" > /tmp/askpass.sh
echo "echo '$PASS'" >> /tmp/askpass.sh
chmod +x /tmp/askpass.sh

echo "--- Method: SSH_ASKPASS ---"
timeout 10 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o PubkeyAuthentication=no -o PreferredAuthentications=password "$USER@$HOST" "show version" < /dev/null 2>&1
echo "exit: $?"
echo ""

# Method 2: Try with expect if available
if command -v expect > /dev/null 2>&1; then
    echo "--- Method: expect ---"
    expect -c "
        set timeout 10
        spawn ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no $USER@$HOST
        expect {
            \"password:\" { send \"$PASS\r\" }
            \"Password:\" { send \"$PASS\r\" }
        }
        expect {\$}
        send \"show version\r\"
        expect {\$}
        send \"show interfaces\r\"
        expect {\$}
        send \"show configuration commands\r\"
        expect {\$}
        send \"show nat rules\r\"
        expect {\$}
        send \"show dhcp leases\r\"
        expect {\$}
        send \"show arp\r\"
        expect {\$}
        send \"exit\r\"
        expect eof
    " 2>&1
    echo "exit: $?"
else
    echo "expect not available"
    echo ""
    echo "--- Method: Python pexpect ---"
    python3 -c "
import sys
try:
    import pexpect
except ImportError:
    print('pexpect not available either')
    sys.exit(1)

child = pexpect.spawn('ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no ${USER}@${HOST}', timeout=15)
child.expect('[Pp]assword')
child.sendline('${PASS}')
child.expect(['\\\$', '#', '>'])
for cmd in ['show version', 'show interfaces', 'show configuration commands', 'show nat rules', 'show dhcp leases', 'show arp']:
    child.sendline(cmd)
    child.expect(['\\\$', '#', '>'], timeout=10)
    print(child.before.decode())
child.sendline('exit')
child.close()
" 2>&1
fi

echo ""
echo "=== DONE ==="
