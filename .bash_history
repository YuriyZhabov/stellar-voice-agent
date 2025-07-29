whoami
ufw --version
which fail2ban-server
apt update
apt install -y fail2ban
ufw status
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
systemctl enable fail2ban
systemctl start fail2ban
systemctl status fail2ban
fail2ban-client status
fail2ban-client status sshd
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
cat /etc/ssh/sshd_config | grep -E "^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|MaxAuthTries|ClientAliveInterval|ClientAliveCountMax)"
sshd -t
systemctl reload sshd
systemctl reload ssh
ufw logging on
chmod +x /usr/local/bin/security-status.sh
chmod +x /root/usr/local/bin/security-status.sh
/root/usr/local/bin/security-status.sh
apt install -y net-tools
/root/usr/local/bin/security-status.sh
apt update
apt list --upgradable
apt upgrade -y
apt upgrade -y --fix-missing
apt list --upgradable
uname -r
systemctl status ssh
systemctl status fail2ban
ssh -V
systemctl --version
/root/usr/local/bin/security-status.sh
apt autoremove -y
apt autoclean
apt-get remove docker-compose
