#!/bin/bash
# install_service.sh - Install cdc_v2.py as a systemd service

SERVICE_NAME="door-control"
USER=$(whoami)
WORKING_DIR=$(pwd)
PYTHON_PATH="$WORKING_DIR/venv/bin/python3"

echo "Creating systemd service for $SERVICE_NAME..."

sudo bash -c "cat > /etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=IntaDoor Control System v2
After=network.target

[Service]
ExecStart=$PYTHON_PATH $WORKING_DIR/cdc_v2.py
WorkingDirectory=$WORKING_DIR
StandardOutput=inherit
StandardError=inherit
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

echo "Adding $USER to the 'input' group for hardware scanner access..."
sudo usermod -a -G input $USER

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling and starting $SERVICE_NAME service..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "Service status:"
sudo systemctl status $SERVICE_NAME --no-pager
