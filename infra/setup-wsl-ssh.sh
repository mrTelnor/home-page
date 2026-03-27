#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# Копирование SSH-ключа из Windows в WSL
# Запускать один раз из WSL
# --------------------------------------------------

WIN_KEY="/mnt/c/Users/telnor/.ssh/GitHub_SSH"
WSL_DIR="$HOME/.ssh"
WSL_KEY="${WSL_DIR}/GitHub_SSH"

if [ ! -f "${WIN_KEY}" ]; then
    echo "Ошибка: ключ ${WIN_KEY} не найден"
    exit 1
fi

mkdir -p "${WSL_DIR}"
chmod 700 "${WSL_DIR}"
cp "${WIN_KEY}" "${WSL_KEY}"
chmod 600 "${WSL_KEY}"

ANSIBLE_DIR="/mnt/d/Gitlab/home-page/home-page/infra/ansible"
VAULT_PASS_SRC="${ANSIBLE_DIR}/.vault_pass"
VAULT_PASS_DST="$HOME/.vault_pass"

if [ -f "${VAULT_PASS_SRC}" ]; then
    cp "${VAULT_PASS_SRC}" "${VAULT_PASS_DST}"
    chmod 600 "${VAULT_PASS_DST}"
    echo "Vault password скопирован: ${VAULT_PASS_DST}"
else
    echo "Предупреждение: ${VAULT_PASS_SRC} не найден, vault password не настроен"
fi

echo ">>> Настройка переменных Ansible в ~/.bashrc..."
declare -A EXPORTS=(
    ["ANSIBLE_VAULT_PASSWORD_FILE"]="${VAULT_PASS_DST}"
    ["ANSIBLE_ROLES_PATH"]="${ANSIBLE_DIR}/roles"
    ["ANSIBLE_CONFIG"]="${ANSIBLE_DIR}/ansible.cfg"
)

for VAR in "${!EXPORTS[@]}"; do
    if ! grep -q "${VAR}" "$HOME/.bashrc" 2>/dev/null; then
        echo "export ${VAR}=${EXPORTS[$VAR]}" >> "$HOME/.bashrc"
        echo "  добавлен ${VAR}"
    else
        echo "  ${VAR} уже в ~/.bashrc"
    fi
done

echo ""
echo "Ключ скопирован: ${WSL_KEY}"
echo "Проверь подключение:"
echo "    ssh -i ${WSL_KEY} telnor@<IP_ВМ>"
echo ""
echo "Перезагрузи shell или выполни: source ~/.bashrc"
