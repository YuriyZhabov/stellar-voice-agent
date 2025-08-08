#!/bin/bash

echo "=== Статус безопасности сервера ==="
echo ""

echo "1. Статус UFW:"
ufw status numbered
echo ""

echo "2. Статус Fail2ban:"
fail2ban-client status
echo ""

echo "3. Активные jail'ы Fail2ban:"
for jail in $(fail2ban-client status | grep "Jail list" | cut -d: -f2 | tr ',' ' '); do
    echo "--- $jail ---"
    fail2ban-client status $jail
    echo ""
done

echo "4. Последние заблокированные IP (из логов):"
tail -n 20 /var/log/fail2ban.log | grep "Ban " | tail -5
echo ""

echo "5. Активные SSH соединения:"
ss -tuln | grep :22
echo ""

echo "6. Последние попытки входа:"
tail -n 10 /var/log/auth.log | grep "Failed password"
echo ""

echo "7. Использование портов:"
netstat -tuln | grep LISTEN
echo ""

echo "=== Конец отчета ==="