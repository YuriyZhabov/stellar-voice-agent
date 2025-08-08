#!/bin/bash

# SSL Certificate Setup Script for Voice AI Agent
# This script sets up SSL/TLS certificates for production deployment

set -euo pipefail

# Configuration
DOMAIN="${DOMAIN:-agentio.ru}"
EMAIL="${SSL_EMAIL:-admin@${DOMAIN}}"
CERT_DIR="/etc/ssl/voice-ai-agent"
NGINX_CONF_DIR="/etc/nginx/sites-available"
SYSTEMCTL_AVAILABLE=$(command -v systemctl >/dev/null 2>&1 && echo "yes" || echo "no")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
}

# Install required packages
install_dependencies() {
    log "Installing SSL certificate dependencies..."
    
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y certbot python3-certbot-nginx nginx openssl
    elif command -v yum >/dev/null 2>&1; then
        yum update -y
        yum install -y certbot python3-certbot-nginx nginx openssl
    elif command -v dnf >/dev/null 2>&1; then
        dnf update -y
        dnf install -y certbot python3-certbot-nginx nginx openssl
    else
        error "Unsupported package manager. Please install certbot, nginx, and openssl manually."
        exit 1
    fi
}

# Create certificate directory
create_cert_directory() {
    log "Creating certificate directory..."
    mkdir -p "$CERT_DIR"
    chmod 755 "$CERT_DIR"
}

# Generate self-signed certificate for development/testing
generate_self_signed_cert() {
    log "Generating self-signed certificate for $DOMAIN..."
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$DOMAIN"
    
    chmod 600 "$CERT_DIR/privkey.pem"
    chmod 644 "$CERT_DIR/fullchain.pem"
    
    log "Self-signed certificate generated successfully"
}

# Obtain Let's Encrypt certificate
obtain_letsencrypt_cert() {
    log "Obtaining Let's Encrypt certificate for $DOMAIN..."
    
    # Stop nginx if running
    if [[ "$SYSTEMCTL_AVAILABLE" == "yes" ]]; then
        systemctl stop nginx 2>/dev/null || true
    fi
    
    # Obtain certificate using standalone mode
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN" \
        --cert-path "$CERT_DIR/cert.pem" \
        --key-path "$CERT_DIR/privkey.pem" \
        --fullchain-path "$CERT_DIR/fullchain.pem" \
        --chain-path "$CERT_DIR/chain.pem"
    
    if [[ $? -eq 0 ]]; then
        log "Let's Encrypt certificate obtained successfully"
        
        # Copy certificates to our directory
        cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/"
        cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/"
        cp "/etc/letsencrypt/live/$DOMAIN/cert.pem" "$CERT_DIR/"
        cp "/etc/letsencrypt/live/$DOMAIN/chain.pem" "$CERT_DIR/"
        
        chmod 600 "$CERT_DIR/privkey.pem"
        chmod 644 "$CERT_DIR"/*.pem
    else
        warn "Failed to obtain Let's Encrypt certificate, falling back to self-signed"
        generate_self_signed_cert
    fi
}

# Configure nginx with SSL
configure_nginx() {
    log "Configuring nginx with SSL..."
    
    cat > "$NGINX_CONF_DIR/voice-ai-agent" << EOF
# Voice AI Agent SSL Configuration

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    # SSL Configuration
    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES256-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'" always;
    
    # Rate Limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Proxy to Voice AI Agent
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
    
    # Metrics endpoint (restrict access)
    location /metrics {
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;
        
        proxy_pass http://127.0.0.1:9090/metrics;
    }
    
    # Block common attack patterns
    location ~* \.(php|asp|aspx|jsp)$ {
        return 444;
    }
    
    location ~* /\.(git|svn|hg) {
        return 444;
    }
    
    # Access and error logs
    access_log /var/log/nginx/voice-ai-agent-access.log;
    error_log /var/log/nginx/voice-ai-agent-error.log;
}
EOF

    # Enable the site
    ln -sf "$NGINX_CONF_DIR/voice-ai-agent" /etc/nginx/sites-enabled/
    
    # Test nginx configuration
    nginx -t
    
    if [[ $? -eq 0 ]]; then
        log "Nginx configuration is valid"
        
        if [[ "$SYSTEMCTL_AVAILABLE" == "yes" ]]; then
            systemctl enable nginx
            systemctl restart nginx
        fi
    else
        error "Nginx configuration is invalid"
        exit 1
    fi
}

# Setup certificate renewal
setup_cert_renewal() {
    log "Setting up automatic certificate renewal..."
    
    # Create renewal script
    cat > /usr/local/bin/renew-voice-ai-certs.sh << 'EOF'
#!/bin/bash

# Certificate renewal script for Voice AI Agent
CERT_DIR="/etc/ssl/voice-ai-agent"
DOMAIN="${DOMAIN:-agentio.ru}"

# Renew Let's Encrypt certificate
certbot renew --quiet

# Copy renewed certificates
if [[ -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]]; then
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/"
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/"
    cp "/etc/letsencrypt/live/$DOMAIN/cert.pem" "$CERT_DIR/"
    cp "/etc/letsencrypt/live/$DOMAIN/chain.pem" "$CERT_DIR/"
    
    chmod 600 "$CERT_DIR/privkey.pem"
    chmod 644 "$CERT_DIR"/*.pem
    
    # Reload nginx
    systemctl reload nginx
    
    # Restart Voice AI Agent if needed
    docker-compose -f /opt/voice-ai-agent/docker-compose.prod.yml restart voice-ai-agent
fi
EOF

    chmod +x /usr/local/bin/renew-voice-ai-certs.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/renew-voice-ai-certs.sh") | crontab -
    
    log "Certificate renewal scheduled for 2 AM daily"
}

# Generate DH parameters for enhanced security
generate_dh_params() {
    log "Generating DH parameters (this may take a while)..."
    
    if [[ ! -f "$CERT_DIR/dhparam.pem" ]]; then
        openssl dhparam -out "$CERT_DIR/dhparam.pem" 2048
        chmod 644 "$CERT_DIR/dhparam.pem"
        log "DH parameters generated successfully"
    else
        log "DH parameters already exist"
    fi
}

# Validate certificate installation
validate_certificate() {
    log "Validating certificate installation..."
    
    if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
        # Check certificate validity
        openssl x509 -in "$CERT_DIR/fullchain.pem" -text -noout > /dev/null
        
        if [[ $? -eq 0 ]]; then
            log "Certificate validation successful"
            
            # Show certificate details
            echo "Certificate Details:"
            openssl x509 -in "$CERT_DIR/fullchain.pem" -subject -dates -noout
        else
            error "Certificate validation failed"
            exit 1
        fi
    else
        error "Certificate files not found"
        exit 1
    fi
}

# Main execution
main() {
    log "Starting SSL certificate setup for Voice AI Agent..."
    
    check_root
    install_dependencies
    create_cert_directory
    
    # Choose certificate type
    if [[ "${USE_LETSENCRYPT:-yes}" == "yes" ]]; then
        obtain_letsencrypt_cert
        setup_cert_renewal
    else
        generate_self_signed_cert
    fi
    
    generate_dh_params
    configure_nginx
    validate_certificate
    
    log "SSL certificate setup completed successfully!"
    log "Your Voice AI Agent is now secured with HTTPS"
    log "Certificate location: $CERT_DIR"
    log "Nginx configuration: $NGINX_CONF_DIR/voice-ai-agent"
}

# Run main function
main "$@"