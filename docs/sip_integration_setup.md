# LiveKit SIP Integration Setup Guide

This guide explains how to configure and test the LiveKit SIP integration for the Voice AI Agent.

## Overview

The Voice AI Agent uses LiveKit SIP integration to handle incoming phone calls through SIP trunks. The system includes:

- **SIP Trunk Configuration**: Connection to MTS Exolve or other SIP providers
- **Audio Codec Optimization**: Configured for voice conversations
- **Call Routing**: Automatic routing of calls to LiveKit rooms
- **Webhook Integration**: Real-time event handling
- **Connection Monitoring**: Automatic reconnection and health checks

## Configuration Files

### 1. LiveKit SIP Configuration (`livekit-sip.yaml`)

The main configuration file that defines:
- SIP trunk settings
- Audio codec preferences
- Call routing rules
- LiveKit integration parameters
- Monitoring and health check settings

### 2. Environment Variables (`.env`)

Required environment variables for SIP integration:

```bash
# SIP Configuration (MTS Exolve or other provider)
SIP_NUMBER=+1234567890
SIP_SERVER=sip.your-provider.com
SIP_USERNAME=your_sip_username
SIP_PASSWORD=your_sip_password
SIP_TRANSPORT=UDP
SIP_PORT=5060

# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_SIP_URI=sip:voice-ai@your-livekit-server.com

# Network Configuration
DOMAIN=your-domain.com
PUBLIC_IP=203.0.113.1
PORT=8000

# Security
SECRET_KEY=your-secret-key-for-webhooks
```

## Setup Steps

### 1. Configure Environment Variables

Copy the environment template and fill in your values:

```bash
cp .env.template .env
# Edit .env with your SIP provider and LiveKit credentials
```

### 2. Verify Configuration

Run the SIP integration test to verify your configuration:

```bash
python test_sip_integration.py
```

This will test:
- Configuration file validation
- Environment variable setup
- SIP trunk connectivity
- LiveKit API connection
- Audio codec configuration
- Webhook endpoints
- Call simulation
- Health monitoring
- Error handling

### 3. Start the Voice AI Agent

Once configuration is verified, start the agent:

```bash
python -m src.main
```

The agent will:
- Initialize all AI service clients
- Set up LiveKit SIP integration
- Start the webhook server
- Begin monitoring for incoming calls

## SIP Provider Configuration

### MTS Exolve Setup

For MTS Exolve SIP trunk integration:

1. **Obtain SIP Credentials**:
   - SIP server hostname
   - Username and password
   - Assigned phone number

2. **Configure Network**:
   - Ensure your server's public IP is whitelisted
   - Configure firewall for SIP (port 5060) and RTP (ports 10000-20000)

3. **Set Environment Variables**:
   ```bash
   SIP_SERVER=sip.mts-exolve.com
   SIP_USERNAME=your_username
   SIP_PASSWORD=your_password
   SIP_NUMBER=+1234567890
   ```

### Other SIP Providers

The configuration supports any SIP provider. Adjust the following in your `.env`:

- `SIP_SERVER`: Your provider's SIP server
- `SIP_TRANSPORT`: UDP, TCP, or TLS
- `SIP_PORT`: Usually 5060 for UDP/TCP, 5061 for TLS

## LiveKit Cloud Setup

### 1. Create LiveKit Cloud Account

1. Sign up at [LiveKit Cloud](https://cloud.livekit.io/)
2. Create a new project
3. Note your server URL and API credentials

### 2. Configure SIP Integration

1. In LiveKit Cloud dashboard, enable SIP integration
2. Configure SIP trunk to point to your Voice AI Agent
3. Set up webhook URL: `https://your-domain.com/webhooks/livekit`

### 3. Set Environment Variables

```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=your_api_secret
```

## Audio Quality Optimization

The system is configured with optimal audio codecs for voice conversations:

1. **PCMU (G.711 μ-law)** - Primary codec for North American telephony
2. **PCMA (G.711 A-law)** - Secondary codec for international telephony
3. **G.722** - Wideband codec for better quality when supported
4. **G.729** - Low bandwidth codec (disabled by default due to licensing)

Audio processing includes:
- Echo cancellation
- Noise suppression
- Automatic gain control
- Voice activity detection

## Monitoring and Health Checks

The system includes comprehensive monitoring:

### Health Checks
- SIP trunk connectivity monitoring
- LiveKit API connection status
- Audio processing pipeline health
- Webhook endpoint availability

### Metrics Collection
- Call count and duration
- Success rates and error rates
- Audio quality metrics
- Latency measurements
- Codec usage statistics

### Logging
- Structured JSON logging
- Configurable log levels
- Log rotation and retention
- Sensitive data filtering

## Troubleshooting

### Common Issues

1. **SIP Connection Failed**
   - Verify SIP credentials
   - Check network connectivity
   - Ensure firewall allows SIP traffic

2. **LiveKit Connection Failed**
   - Verify API credentials
   - Check server URL format
   - Ensure network can reach LiveKit servers

3. **Webhook Events Not Received**
   - Verify webhook URL is accessible
   - Check webhook signature validation
   - Ensure server is running on correct port

4. **Audio Quality Issues**
   - Check codec configuration
   - Verify network bandwidth
   - Review audio processing settings

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

### Test Mode

Run in test mode to verify configuration without handling real calls:

```bash
TEST_MODE=true
```

## Security Considerations

1. **API Keys**: Store securely in environment variables
2. **Webhook Security**: Use strong secret key for signature validation
3. **Network Security**: Restrict access to SIP and webhook ports
4. **TLS/SRTP**: Enable for production deployments when supported
5. **Rate Limiting**: Configure to prevent abuse

## Performance Tuning

### Network Optimization
- Configure QoS for voice traffic
- Set appropriate jitter buffer sizes
- Optimize RTP port ranges

### System Resources
- Monitor CPU and memory usage
- Configure connection pooling
- Set appropriate thread counts

### Latency Optimization
- Minimize audio buffer sizes
- Optimize codec selection
- Reduce network hops

## Production Deployment

### Requirements
- Stable internet connection with low latency
- Sufficient bandwidth for concurrent calls
- Reliable server infrastructure
- Monitoring and alerting setup

### Scaling
- Configure load balancing for multiple instances
- Use Redis for session management
- Implement database clustering if needed

### Backup and Recovery
- Regular configuration backups
- Database backup procedures
- Disaster recovery planning

## Support

For issues with:
- **SIP Integration**: Check SIP provider documentation
- **LiveKit**: Refer to [LiveKit documentation](https://docs.livekit.io/)
- **Voice AI Agent**: Check application logs and health endpoints