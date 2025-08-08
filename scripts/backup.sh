#!/bin/bash
# Production backup script for Voice AI Agent

set -e

# Configuration
BACKUP_DIR="/app/backups"
DATA_DIR="/app/data"
LOGS_DIR="/app/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting backup process at $(date)"

# Backup database
if [ -f "$DATA_DIR/voice_ai.db" ]; then
    echo "📊 Backing up database..."
    cp "$DATA_DIR/voice_ai.db" "$BACKUP_DIR/voice_ai_${TIMESTAMP}.db"
    gzip "$BACKUP_DIR/voice_ai_${TIMESTAMP}.db"
    echo "✅ Database backup completed"
fi

# Backup configuration
echo "⚙️  Backing up configuration..."
tar -czf "$BACKUP_DIR/config_${TIMESTAMP}.tar.gz" -C /app config/ .env.production 2>/dev/null || true
echo "✅ Configuration backup completed"

# Backup recent logs (last 7 days)
echo "📝 Backing up recent logs..."
find "$LOGS_DIR" -name "*.log" -mtime -7 -exec tar -czf "$BACKUP_DIR/logs_${TIMESTAMP}.tar.gz" {} + 2>/dev/null || true
echo "✅ Logs backup completed"

# Cleanup old backups
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "✅ Backup process completed at $(date)"
echo "📁 Backup files:"
ls -la "$BACKUP_DIR" | grep "$TIMESTAMP"