#!/usr/bin/env bash
# Run as root on Ubuntu 24.04 after copying source to /opt/devopspilot
# and credentials separately to /etc/devopspilot/environment (mode 0600).
set -euo pipefail
APP=/opt/devopspilot
ENV_FILE=/etc/devopspilot/environment
if [[ $(id -u) != 0 ]]; then
  echo 'Run as root on the target cloud instance.' >&2
  exit 1
fi
[[ -f "$APP/pyproject.toml" && -f "$ENV_FILE" ]] || {
  echo 'Source or private environment file is missing.' >&2
  exit 1
}
# Package files must remain readable by the dedicated service user even when
# the operator used umask 077 for the separate credential transfer.
umask 022
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip git nginx curl
id devopspilot >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/devopspilot --shell /usr/sbin/nologin devopspilot
install -d -o devopspilot -g devopspilot -m 0700 /var/lib/devopspilot
chown root:devopspilot /etc/devopspilot "$ENV_FILE"
chmod 0750 /etc/devopspilot
chmod 0640 "$ENV_FILE"
ln -sfn "$ENV_FILE" "$APP/.env"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/python" -m pip install -e "$APP"
"$APP/.venv/bin/python" -m pip install -r "$APP/requirements-runtime.txt"
install -m 0644 "$APP/docs/deployment/devopspilot.service" /etc/systemd/system/devopspilot.service
install -m 0644 "$APP/docs/deployment/devopspilot.nginx.conf" /etc/nginx/sites-available/devopspilot
ln -sfn /etc/nginx/sites-available/devopspilot /etc/nginx/sites-enabled/devopspilot
# This dedicated instance has no other website. Disable the default port 80 site.
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now devopspilot
systemctl restart nginx
curl --fail --silent --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8080/api/status >/dev/null
echo 'Service started; external access and Live model acceptance remain to be verified.'
