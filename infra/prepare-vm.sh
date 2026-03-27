#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# Скрипт первичной подготовки ВМ (Ubuntu 24.04)
# Запускать от root на свежей ВМ перед Ansible
# --------------------------------------------------

USERNAME="telnor"
SSH_PUB_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGLyikKhMXzLTMxXMH3vjpAMgrml2B2TzRdOlrSqeB7u mrTelnor@github"

echo ">>> Обновление пакетов..."
apt update && apt upgrade -y

echo ">>> Установка зависимостей для Ansible..."
apt install -y python3 python3-apt sudo

echo ">>> Создание пользователя ${USERNAME}..."
if id "${USERNAME}" &>/dev/null; then
    echo "Пользователь ${USERNAME} уже существует"
else
    adduser --disabled-password --gecos "" "${USERNAME}"
fi

echo ">>> Добавление в группу sudo..."
usermod -aG sudo "${USERNAME}"
echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}"
chmod 440 "/etc/sudoers.d/${USERNAME}"

echo ">>> Добавление SSH-ключа..."
SSH_DIR="/home/${USERNAME}/.ssh"
mkdir -p "${SSH_DIR}"
echo "${SSH_PUB_KEY}" > "${SSH_DIR}/authorized_keys"
chmod 700 "${SSH_DIR}"
chmod 600 "${SSH_DIR}/authorized_keys"
chown -R "${USERNAME}:${USERNAME}" "${SSH_DIR}"

echo ">>> Готово! Проверь подключение:"
echo "    ssh -i ~/.ssh/GitHub_SSH ${USERNAME}@<IP_ВМ>"
echo ""
echo ">>> После этого запусти initial-setup.yml из Ansible"
