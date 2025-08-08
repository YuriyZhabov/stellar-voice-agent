"""
LiveKit Ingress Service Usage Examples

This example demonstrates how to use the LiveKit Ingress Service for media import:
- RTMP/RTMPS Ingress for OBS, XSplit
- WHIP Ingress for WebRTC-HTTP protocol
- URL Input for HLS, MP4, MOV files
- Support for all audio formats
"""

import asyncio
import logging
from datetime import datetime, UTC

from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_ingress import (
    LiveKitIngressService,
    RTMPIngressOptions,
    WHIPIngressOptions,
    URLIngressOptions,
    create_ingress_service
)
from src.config import get_settings


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def rtmp_ingress_example():
    """Example: Create RTMP Ingress for OBS/XSplit streaming."""
    print("\n=== RTMP Ingress Example ===")
    
    # Initialize client and service
    settings = get_settings()
    client = LiveKitAPIClient(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    )
    
    ingress_service = create_ingress_service(client)
    
    try:
        # Create RTMP ingress with default options
        print("Creating RTMP ingress for OBS streaming...")
        rtmp_result = await ingress_service.create_rtmp_ingress(
            name="obs_stream",
            room_name="streaming_room",
            participant_identity="obs_streamer",
            participant_name="OBS Streamer"
        )
        
        print(f"RTMP Ingress created:")
        print(f"  Ingress ID: {rtmp_result['ingress_id']}")
        print(f"  RTMP URL: {rtmp_result['url']}")
        print(f"  Stream Key: {rtmp_result['stream_key']}")
        print(f"  Room: {rtmp_result['room_name']}")
        
        # Create RTMP ingress with custom transcoding options
        print("\nCreating RTMP ingress with custom options...")
        from livekit.api import IngressVideoEncodingPreset, IngressAudioEncodingPreset
        
        custom_options = RTMPIngressOptions(
            enable_transcoding=True,
            bypass_transcoding=False,
            video_preset=IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS,
            audio_preset=IngressAudioEncodingPreset.OPUS_STEREO_96KBPS
        )
        
        custom_rtmp_result = await ingress_service.create_rtmp_ingress(
            name="obs_stream_hd",
            room_name="hd_streaming_room",
            participant_identity="obs_streamer_hd",
            participant_name="OBS HD Streamer",
            options=custom_options
        )
        
        print(f"Custom RTMP Ingress created:")
        print(f"  Ingress ID: {custom_rtmp_result['ingress_id']}")
        print(f"  RTMP URL: {custom_rtmp_result['url']}")
        print(f"  Stream Key: {custom_rtmp_result['stream_key']}")
        
        # Instructions for OBS setup
        print("\n--- OBS Studio Setup Instructions ---")
        print("1. Open OBS Studio")
        print("2. Go to Settings > Stream")
        print("3. Set Service to 'Custom...'")
        print(f"4. Set Server to: {rtmp_result['url']}")
        print(f"5. Set Stream Key to: {rtmp_result['stream_key']}")
        print("6. Click OK and start streaming")
        
        return rtmp_result['ingress_id'], custom_rtmp_result['ingress_id']
        
    except Exception as e:
        logger.error(f"RTMP ingress example failed: {e}")
        raise


async def whip_ingress_example():
    """Example: Create WHIP Ingress for WebRTC-HTTP streaming."""
    print("\n=== WHIP Ingress Example ===")
    
    # Initialize client and service
    settings = get_settings()
    client = LiveKitAPIClient(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    )
    
    ingress_service = create_ingress_service(client)
    
    try:
        # Create WHIP ingress
        print("Creating WHIP ingress for WebRTC streaming...")
        whip_result = await ingress_service.create_whip_ingress(
            name="webrtc_stream",
            room_name="webrtc_room",
            participant_identity="webrtc_streamer",
            participant_name="WebRTC Streamer"
        )
        
        print(f"WHIP Ingress created:")
        print(f"  Ingress ID: {whip_result['ingress_id']}")
        print(f"  WHIP URL: {whip_result['url']}")
        print(f"  Room: {whip_result['room_name']}")
        
        # Create WHIP ingress with bypass transcoding for low latency
        print("\nCreating low-latency WHIP ingress...")
        low_latency_options = WHIPIngressOptions(
            bypass_transcoding=True,
            enable_transcoding=False
        )
        
        low_latency_result = await ingress_service.create_whip_ingress(
            name="webrtc_low_latency",
            room_name="low_latency_room",
            participant_identity="webrtc_low_latency",
            participant_name="Low Latency Streamer",
            options=low_latency_options
        )
        
        print(f"Low-latency WHIP Ingress created:")
        print(f"  Ingress ID: {low_latency_result['ingress_id']}")
        print(f"  WHIP URL: {low_latency_result['url']}")
        
        # Instructions for WHIP usage
        print("\n--- WHIP Usage Instructions ---")
        print("Use the WHIP URL with WebRTC-compatible streaming software:")
        print(f"  WHIP Endpoint: {whip_result['url']}")
        print("  Compatible with: FFmpeg with WHIP support, GStreamer, etc.")
        
        return whip_result['ingress_id'], low_latency_result['ingress_id']
        
    except Exception as e:
        logger.error(f"WHIP ingress example failed: {e}")
        raise


async def url_ingress_example():
    """Example: Create URL Input Ingress for various media formats."""
    print("\n=== URL Input Ingress Example ===")
    
    # Initialize client and service
    settings = get_settings()
    client = LiveKitAPIClient(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    )
    
    ingress_service = create_ingress_service(client)
    
    try:
        # Example URLs for different formats
        media_examples = [
            {
                "name": "mp4_video",
                "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "description": "MP4 Video File"
            },
            {
                "name": "hls_stream",
                "url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
                "description": "HLS Live Stream"
            },
            {
                "name": "mp3_audio",
                "url": "https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3",
                "description": "MP3 Audio File"
            }
        ]
        
        created_ingress = []
        
        for media in media_examples:
            print(f"\nCreating URL ingress for {media['description']}...")
            
            try:
                url_result = await ingress_service.create_url_ingress(
                    name=media['name'],
                    room_name=f"{media['name']}_room",
                    participant_identity=f"{media['name']}_participant",
                    url=media['url'],
                    participant_name=f"{media['description']} Player"
                )
                
                print(f"URL Ingress created:")
                print(f"  Ingress ID: {url_result['ingress_id']}")
                print(f"  Source URL: {url_result['source_url']}")
                print(f"  Room: {url_result['room_name']}")
                print(f"  Participant: {url_result['participant_identity']}")
                
                created_ingress.append(url_result['ingress_id'])
                
            except Exception as e:
                print(f"Failed to create ingress for {media['description']}: {e}")
        
        # Create URL ingress with custom transcoding options
        print("\nCreating URL ingress with custom transcoding...")
        custom_options = URLIngressOptions(
            enable_transcoding=True,
            bypass_transcoding=False
        )
        
        custom_url_result = await ingress_service.create_url_ingress(
            name="custom_transcoded_video",
            room_name="transcoded_room",
            participant_identity="transcoded_participant",
            url="https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
            participant_name="Transcoded Video Player",
            options=custom_options
        )
        
        print(f"Custom URL Ingress created:")
        print(f"  Ingress ID: {custom_url_result['ingress_id']}")
        print(f"  Source URL: {custom_url_result['source_url']}")
        
        created_ingress.append(custom_url_result['ingress_id'])
        
        # Show supported formats
        print("\n--- Supported URL Formats ---")
        supported_formats = ingress_service._get_supported_url_formats()
        print("Video containers:", [f for f in supported_formats if f.startswith('.') and f in ['.mp4', '.mov', '.mkv', '.webm', '.avi']])
        print("Audio formats:", [f for f in supported_formats if f.startswith('.') and f in ['.mp3', '.ogg', '.m4a', '.aac']])
        print("Streaming protocols:", [f for f in supported_formats if f.startswith(('http', 'rtmp', '.m3u8'))])
        
        return created_ingress
        
    except Exception as e:
        logger.error(f"URL ingress example failed: {e}")
        raise


async def ingress_management_example(ingress_ids):
    """Example: Manage ingress instances."""
    print("\n=== Ingress Management Example ===")
    
    # Initialize client and service
    settings = get_settings()
    client = LiveKitAPIClient(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    )
    
    ingress_service = create_ingress_service(client)
    
    try:
        # List all ingress instances
        print("Listing all ingress instances...")
        all_ingress = await ingress_service.list_ingress()
        
        print(f"Found {len(all_ingress)} ingress instances:")
        for ingress in all_ingress:
            print(f"  - {ingress['name']} ({ingress['ingress_id']}) - {ingress['input_type']} - {ingress['state']}")
        
        # Get status of specific ingress
        if ingress_ids:
            print(f"\nGetting status of ingress {ingress_ids[0]}...")
            status = ingress_service.get_ingress_status(ingress_ids[0])
            if status:
                print(f"Ingress Status:")
                print(f"  Name: {status['name']}")
                print(f"  Room: {status['room_name']}")
                print(f"  State: {status['state']}")
                print(f"  Created: {status['created_at']}")
        
        # Get active ingress count
        active_count = ingress_service.get_active_ingress_count()
        print(f"\nActive ingress count: {active_count}")
        
        # Update an ingress (if we have one)
        if ingress_ids:
            print(f"\nUpdating ingress {ingress_ids[0]}...")
            updated_result = await ingress_service.update_ingress(
                ingress_id=ingress_ids[0],
                name="updated_ingress_name",
                participant_name="Updated Participant Name"
            )
            print(f"Updated ingress:")
            print(f"  New name: {updated_result['name']}")
            print(f"  New participant name: {updated_result['participant_name']}")
        
        # Health check
        print("\nPerforming health check...")
        health_result = await ingress_service.health_check()
        print(f"Health check result:")
        print(f"  Status: {health_result['status']}")
        print(f"  Latency: {health_result.get('latency_ms', 'N/A')} ms")
        print(f"  Active ingress: {health_result.get('active_ingress_count', 'N/A')}")
        
        # Filter ingress by room
        if all_ingress:
            room_name = all_ingress[0]['room_name']
            print(f"\nGetting ingress for room '{room_name}'...")
            room_ingress = ingress_service.get_ingress_by_room(room_name)
            print(f"Found {len(room_ingress)} ingress instances in room '{room_name}'")
        
    except Exception as e:
        logger.error(f"Ingress management example failed: {e}")
        raise


async def cleanup_example(ingress_ids):
    """Example: Clean up created ingress instances."""
    print("\n=== Cleanup Example ===")
    
    # Initialize client and service
    settings = get_settings()
    client = LiveKitAPIClient(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    )
    
    ingress_service = create_ingress_service(client)
    
    try:
        # Delete created ingress instances
        for ingress_id in ingress_ids:
            print(f"Deleting ingress {ingress_id}...")
            try:
                await ingress_service.delete_ingress(ingress_id)
                print(f"  Successfully deleted {ingress_id}")
            except Exception as e:
                print(f"  Failed to delete {ingress_id}: {e}")
        
        print("Cleanup completed!")
        
    except Exception as e:
        logger.error(f"Cleanup example failed: {e}")
        raise


async def main():
    """Run all ingress examples."""
    print("LiveKit Ingress Service Examples")
    print("=" * 50)
    
    all_ingress_ids = []
    
    try:
        # Run RTMP ingress examples
        rtmp_ids = await rtmp_ingress_example()
        all_ingress_ids.extend(rtmp_ids)
        
        # Run WHIP ingress examples
        whip_ids = await whip_ingress_example()
        all_ingress_ids.extend(whip_ids)
        
        # Run URL ingress examples
        url_ids = await url_ingress_example()
        all_ingress_ids.extend(url_ids)
        
        # Run management examples
        await ingress_management_example(all_ingress_ids)
        
        # Wait a bit before cleanup
        print("\nWaiting 5 seconds before cleanup...")
        await asyncio.sleep(5)
        
        # Clean up created ingress
        await cleanup_example(all_ingress_ids)
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        # Still try to clean up
        if all_ingress_ids:
            print("\nAttempting cleanup after error...")
            await cleanup_example(all_ingress_ids)
        raise


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())