#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  PayShield — One-shot Ubuntu 22.04 deployment script
#  Run as: sudo bash scripts/deploy_ubuntu.sh yourdomain.com
# ─────────────────────────────────────────────────────────────────────────────
set -e
DOMAIN=${1:-"payshield.yourdomain.com"}
APP_DIR="/opt/payshield"
APP_USER="payshield"

echo "🛡  Deploying PayShield to $DOMAIN"

# 1. System packages
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

# 2. Create app user
id -u $APP_USER &>/dev/null || useradd --system --shell /bin/bash --home $APP_DIR $APP_USER

# 3. Clone / update code
if [ -d "$APP_DIR" ]; then
  echo "Updating existing installation..."
  cd $APP_DIR && git pull
else
  git clone https://github.com/YOUR_GITHUB_USERNAME/payshield.git $APP_DIR
fi
chown -R $APP_USER:$APP_USER $APP_DIR

# 4. Python venv + dependencies
cd $APP_DIR
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
# Uncomment for PostgreSQL support:
# venv/bin/pip install psycopg2-binary

# 5. Environment file
if [ ! -f "$APP_DIR/.env" ]; then
  cp $APP_DIR/.env.example $APP_DIR/.env
  echo "⚠  EDIT $APP_DIR/.env before proceeding!"
  echo "   Set SECRET_KEY, JWT_SECRET, DB config, Razorpay keys, etc."
fi

# 6. Initialise DB & keys
cd $APP_DIR
sudo -u $APP_USER venv/bin/python3 -c "
from crypto_utils import ensure_keys
from db import init_db
ensure_keys()
init_db()
print('✅ DB and keys initialised')
"

# 7. Systemd service
cat > /etc/systemd/system/payshield.service << UNIT
[Unit]
Description=PayShield Payment Receipt Server
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn app:app --workers 4 --threads 2 --worker-class gthread --timeout 120 --bind 127.0.0.1:5000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable payshield
systemctl restart payshield

# 8. Nginx config
cp $APP_DIR/nginx/payshield.conf /etc/nginx/sites-available/payshield
sed -i "s/payshield.yourdomain.com/$DOMAIN/g" /etc/nginx/sites-available/payshield
ln -sf /etc/nginx/sites-available/payshield /etc/nginx/sites-enabled/payshield
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 9. SSL certificate (Let's Encrypt)
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

echo ""
echo "✅ PayShield deployed at https://$DOMAIN"
echo "   Edit /opt/payshield/.env to configure Razorpay, PostgreSQL, KMS, etc."
