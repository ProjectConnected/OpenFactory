#!/usr/bin/env bash
set -euo pipefail

sudo install -m 0644 deploy/systemd/openfactory-watchdog.service /etc/systemd/system/openfactory-watchdog.service
sudo install -m 0644 deploy/systemd/openfactory-watchdog.timer /etc/systemd/system/openfactory-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl enable --now openfactory-watchdog.timer
