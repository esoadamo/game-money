#!/bin/bash
DIR_DATA="$1"

set -euo pipefail
DIR_DATA="$(realpath "$DIR_DATA")"
[ -z "$DIR_DATA" -o ! -d "$DIR_DATA" ] && { echo "ERR: Given data path '$DIR_DATA' is invalid"; exit 1; }

echo "Selected options are"
echo "- DATA: $DIR_DATA"

docker stop gamemoney &>/dev/null || true
docker rm gamemoney &>/dev/null || true
docker run \
  -p 8926:8926 \
  -v "$DIR_DATA:/opt/app/data/" \
  -it \
  --name gamemoney \
  gamemoney

