#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# Откат настроек ВМ к состоянию "после prepare-vm.sh"
# Запускать от root через VNC-консоль
# --------------------------------------------------

echo ">>> Откат SSH на порт 22..."
sed -i 's/^Port 9922/Port 22/' /etc/ssh/sshd_config
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^PermitRootLogin no/PermitRootLogin yes/' /etc/ssh/sshd_config

rm -rf /etc/systemd/system/ssh.socket.d

systemctl daemon-reload
systemctl restart ssh.socket ssh.service

echo ">>> Удаление firewalld..."
systemctl stop firewalld 2>/dev/null || true
apt remove -y firewalld 2>/dev/null || true

echo ">>> Удаление Docker..."
systemctl stop docker 2>/dev/null || true
apt remove -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true
rm -f /etc/apt/sources.list.d/download_docker_com_linux_ubuntu.list
rm -f /etc/apt/keyrings/docker.asc

echo ">>> Очистка..."
apt autoremove -y

echo ">>> Проверка SSH..."
ss -tlnp | grep ssh

echo ">>> Готово. SSH снова на порту 22 с паролями."
