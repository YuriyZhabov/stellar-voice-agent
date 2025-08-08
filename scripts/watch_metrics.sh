#!/bin/bash

# Simple metrics watcher
echo "📊 Watching system metrics..."
echo "Press Ctrl+C to stop"
echo

while true; do
    echo "=== $(date '+%H:%M:%S') ==="
    
    # Check container status
    echo "🐳 Container Status:"
    docker compose -f docker-compose.simple.yml ps --format "table {{.Name}}\t{{.Status}}"
    echo
    
    # Check webhook endpoint
    echo "🌐 Webhook Status:"
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/webhooks/livekit | grep -q "405"; then
        echo "   ✅ Webhook endpoint accessible"
    else
        echo "   ❌ Webhook endpoint not accessible"
    fi
    echo
    
    # Check recent logs for activity
    echo "📋 Recent Activity (last 10 seconds):"
    docker compose -f docker-compose.simple.yml logs --since=10s --no-log-prefix | grep -E "(webhook|livekit|sip|call|participant|room)" | tail -3
    echo
    
    echo "----------------------------------------"
    sleep 10
done