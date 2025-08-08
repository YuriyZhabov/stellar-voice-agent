# LiveKit Ingress Service Usage Guide

The LiveKit Ingress Service provides comprehensive media import functionality according to the LiveKit API specification. This service supports multiple ingress types for importing media from various sources into LiveKit rooms.

## Overview

The service supports three main types of ingress:

1. **RTMP/RTMPS Ingress** - For streaming from OBS, XSplit, and other RTMP-compatible software
2. **WHIP Ingress** - For WebRTC-HTTP Ingestion Protocol streaming
3. **URL Input** - For importing media files and streams from URLs

## Requirements Addressed

- **5.1**: RTMP/RTMPS Ingress support for OBS, XSplit
- **5.2**: WHIP Ingress for WebRTC-HTTP protocol
- **5.3**: URL Input for HLS, MP4, MOV, MKV/WEBM, OGG, MP3, M4A
- **5.4**: CreateIngress endpoint usage
- **5.5**: ingressAdmin permission requirement

## Installation and Setup

```python
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_ingress import LiveKitIngressService, create_ingress_service

# Initialize client
client = LiveKitAPIClient(
    url="https://your-livekit-server.com",
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Create ingress service
ingress_service = create_ingress_service(client)
```

## RTMP/RTMPS Ingress

### Basic RTMP Ingress

Create an RTMP ingress for streaming from OBS or XSplit:

```python
rtmp_result = await ingress_service.create_rtmp_ingress(
    name="obs_stream",
    room_name="streaming_room",
    participant_identity="obs_streamer",
    participant_name="OBS Streamer"
)

print(f"RTMP URL: {rtmp_result['url']}")
print(f"Stream Key: {rtmp_result['stream_key']}")
```

### RTMP with Custom Options

```python
from src.services.livekit_ingress import RTMPIngressOptions
from livekit.api import IngressVideoEncodingPreset, IngressAudioEncodingPreset

options = RTMPIngressOptions(
    enable_transcoding=True,
    bypass_transcoding=False,
    video_preset=IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS,
    audio_preset=IngressAudioEncodingPreset.OPUS_STEREO_96KBPS
)

rtmp_result = await ingress_service.create_rtmp_ingress(
    name="obs_stream_hd",
    room_name="hd_streaming_room",
    participant_identity="obs_streamer_hd",
    options=options
)
```

### OBS Studio Setup

1. Open OBS Studio
2. Go to **Settings > Stream**
3. Set **Service** to "Custom..."
4. Set **Server** to the RTMP URL from the result
5. Set **Stream Key** to the stream key from the result
6. Click **OK** and start streaming

### XSplit Setup

1. Open XSplit Broadcaster
2. Go to **Broadcast > Custom RTMP**
3. Enter the RTMP URL and stream key
4. Click **OK** and start broadcasting

## WHIP Ingress

### Basic WHIP Ingress

Create a WHIP ingress for WebRTC-HTTP streaming:

```python
whip_result = await ingress_service.create_whip_ingress(
    name="webrtc_stream",
    room_name="webrtc_room",
    participant_identity="webrtc_streamer",
    participant_name="WebRTC Streamer"
)

print(f"WHIP URL: {whip_result['url']}")
```

### Low-Latency WHIP Ingress

```python
from src.services.livekit_ingress import WHIPIngressOptions

low_latency_options = WHIPIngressOptions(
    bypass_transcoding=True,
    enable_transcoding=False
)

whip_result = await ingress_service.create_whip_ingress(
    name="webrtc_low_latency",
    room_name="low_latency_room",
    participant_identity="webrtc_low_latency",
    options=low_latency_options
)
```

### WHIP Compatible Software

- **FFmpeg with WHIP support**
- **GStreamer with WHIP plugin**
- **Custom WebRTC applications**

Example FFmpeg command:
```bash
ffmpeg -i input.mp4 -f whip https://your-whip-endpoint
```

## URL Input Ingress

### Supported Formats

The URL Input ingress supports various media formats:

**Video Containers:**
- MP4 (.mp4)
- MOV (.mov)
- MKV (.mkv)
- WEBM (.webm)
- AVI (.avi)
- FLV (.flv)
- TS (.ts)

**Audio Formats:**
- MP3 (.mp3)
- OGG (.ogg)
- M4A (.m4a)
- AAC (.aac)
- FLAC (.flac)
- WAV (.wav)

**Streaming Protocols:**
- HLS (.m3u8)
- HTTP/HTTPS streams
- RTMP/RTMPS streams

### Basic URL Input

```python
# MP4 video file
url_result = await ingress_service.create_url_ingress(
    name="mp4_video",
    room_name="video_room",
    participant_identity="video_player",
    url="https://example.com/video.mp4",
    participant_name="Video Player"
)

# HLS stream
hls_result = await ingress_service.create_url_ingress(
    name="hls_stream",
    room_name="hls_room",
    participant_identity="hls_player",
    url="https://example.com/stream.m3u8",
    participant_name="HLS Player"
)

# MP3 audio file
audio_result = await ingress_service.create_url_ingress(
    name="mp3_audio",
    room_name="audio_room",
    participant_identity="audio_player",
    url="https://example.com/audio.mp3",
    participant_name="Audio Player"
)
```

### URL Input with Custom Options

```python
from src.services.livekit_ingress import URLIngressOptions

options = URLIngressOptions(
    enable_transcoding=True,
    bypass_transcoding=False
)

url_result = await ingress_service.create_url_ingress(
    name="transcoded_video",
    room_name="transcoded_room",
    participant_identity="transcoded_player",
    url="https://example.com/video.mov",
    options=options
)
```

## Ingress Management

### List Ingress Instances

```python
# List all ingress
all_ingress = await ingress_service.list_ingress()

# Filter by room
room_ingress = await ingress_service.list_ingress(room_name="specific_room")

# Get specific ingress
specific_ingress = await ingress_service.list_ingress(ingress_id="ingress_id")
```

### Update Ingress

```python
updated_result = await ingress_service.update_ingress(
    ingress_id="ingress_id",
    name="new_name",
    room_name="new_room",
    participant_identity="new_identity",
    participant_name="New Name"
)
```

### Delete Ingress

```python
await ingress_service.delete_ingress("ingress_id")
```

### Get Ingress Status

```python
# Get status of tracked ingress
status = ingress_service.get_ingress_status("ingress_id")
if status:
    print(f"State: {status['state']}")
    print(f"Created: {status['created_at']}")

# Get active ingress count
count = ingress_service.get_active_ingress_count()

# Get ingress by room
room_ingress = ingress_service.get_ingress_by_room("room_name")
```

## Health Monitoring

### Health Check

```python
health_result = await ingress_service.health_check()
print(f"Status: {health_result['status']}")
print(f"Latency: {health_result.get('latency_ms')} ms")
print(f"Active ingress: {health_result.get('active_ingress_count')}")
```

### Metrics

The service automatically tracks metrics:

- `ingress_created_total` - Total ingress created
- `ingress_updated_total` - Total ingress updated
- `ingress_deleted_total` - Total ingress deleted
- `ingress_errors_total` - Total ingress errors

## Error Handling

The service includes comprehensive error handling:

```python
try:
    result = await ingress_service.create_rtmp_ingress(
        name="test_stream",
        room_name="test_room",
        participant_identity="test_user"
    )
except Exception as e:
    logger.error(f"Failed to create ingress: {e}")
    # Handle error appropriately
```

## Best Practices

### 1. Naming Convention

Use descriptive names for ingress instances:

```python
# Good
name = "obs_main_camera_stream"
name = "conference_room_audio_feed"
name = "presentation_video_file"

# Avoid
name = "stream1"
name = "test"
```

### 2. Room Organization

Organize ingress by purpose:

```python
# Separate rooms for different content types
room_name = "live_streams"      # For RTMP/WHIP
room_name = "media_playback"    # For URL inputs
room_name = "conference_feeds"  # For conference content
```

### 3. Participant Identity

Use meaningful participant identities:

```python
# Include source information
participant_identity = "obs_camera_1"
participant_identity = "presentation_video"
participant_identity = "background_music"
```

### 4. Transcoding Options

Choose appropriate transcoding settings:

```python
# For live streaming (balance quality/latency)
options = RTMPIngressOptions(
    enable_transcoding=True,
    video_preset=IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS
)

# For low latency (bypass transcoding)
options = WHIPIngressOptions(
    bypass_transcoding=True,
    enable_transcoding=False
)

# For file playback (optimize quality)
options = URLIngressOptions(
    enable_transcoding=True,
    video_preset=IngressVideoEncodingPreset.H264_1080P_30FPS_3_LAYERS
)
```

### 5. Resource Management

Clean up unused ingress instances:

```python
# List and clean up inactive ingress
all_ingress = await ingress_service.list_ingress()
for ingress in all_ingress:
    if ingress['state'] == 'ENDPOINT_COMPLETE':
        await ingress_service.delete_ingress(ingress['ingress_id'])
```

## Troubleshooting

### Common Issues

1. **Unsupported URL Format**
   ```python
   # Error: Unsupported URL format
   # Solution: Check supported formats
   supported = ingress_service._get_supported_url_formats()
   print("Supported formats:", supported)
   ```

2. **RTMP Connection Issues**
   - Verify RTMP URL and stream key
   - Check firewall settings
   - Ensure OBS/XSplit is configured correctly

3. **WHIP Streaming Problems**
   - Verify WHIP endpoint URL
   - Check WebRTC compatibility
   - Ensure proper network connectivity

4. **URL Input Failures**
   - Verify URL accessibility
   - Check media format compatibility
   - Ensure proper transcoding settings

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('src.services.livekit_ingress').setLevel(logging.DEBUG)
```

Check ingress status:

```python
status = ingress_service.get_ingress_status("ingress_id")
if status and status['error']:
    print(f"Ingress error: {status['error']}")
```

## Integration Examples

### With Voice AI Agent

```python
# Create ingress for AI processing
rtmp_result = await ingress_service.create_rtmp_ingress(
    name="ai_voice_input",
    room_name="ai_processing_room",
    participant_identity="voice_input_stream"
)

# The Voice AI Agent can then join the same room
# and process the incoming audio stream
```

### With Recording System

```python
# Create ingress and start recording
rtmp_result = await ingress_service.create_rtmp_ingress(
    name="recorded_stream",
    room_name="recording_room",
    participant_identity="stream_source"
)

# Start egress recording of the same room
from src.services.livekit_egress import LiveKitEgressService
egress_service = LiveKitEgressService(client)
recording_id = await egress_service.start_room_composite_egress(
    room_name="recording_room",
    file_outputs=[s3_output_config]
)
```

This comprehensive guide covers all aspects of using the LiveKit Ingress Service for media import according to the API specification.