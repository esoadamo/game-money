#!/bin/bash
echo "Entry $(whoami)"
cd "$(realpath "$(dirname "$0")")/.." || { echo "ERR: Cannot cd to script dir"; exit 1; }

docker/iptables_one_port.sh || exit 2

source venv/bin/activate
su app -c 'python app.py'

