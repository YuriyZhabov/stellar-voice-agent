"""
LiveKit Egress Service Usage Examples

This module demonstrates how to use the LiveKit Egress Service for various
recording and streaming scenarios according to the API specification.
"""

import asyncio
import logging
from datetime import datetime, UTC
from typing import List

from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import (
    LiveKitEgressService,
    S3Config,
    GCPConfig,
    AzureConfig,
    OutputFormat,
    start_room_recording_to_s3,
    start_room_streaming_to_rtmp,
    start_room_hls_streaming
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_room_recording_to_s3():
    """Example: Record room to S3 storage."""
    logger.info("=== Room Recording to S3 Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    # Configure S3 storage
    s3_config = S3Config(
        access_key="your_s3_access_key",
        secret="your_s3_secret",
        region="us-east-1",
        bucket="your-recordings-bucket",
        metadata={
            "project": "voice-ai-agent",
            "environment": "production"
        }
    )
    
    try:
        # Start room recording
        room_name = "voice-ai-call-12345"
        filename = f"recordings/{room_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.mp4"
        
        egress_id = await start_room_recording_to_s3(
            egress_service=egress_service,
            room_name=room_name,
            filename=filename,
            s3_config=s3_config,
            output_format=OutputFormat.MP4,
            audio_only=False,
            video_only=False
        )
        
        logger.info(f"Started room recording with egress ID: {egress_id}")
        
        # Monitor recording status
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to start room recording: {e}")


async def example_room_streaming_to_rtmp():
    """Example: Stream room to RTMP endpoints."""
    logger.info("=== Room RTMP Streaming Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    try:
        # Configure RTMP endpoints
        rtmp_urls = [
            "rtmp://live.twitch.tv/live/your_stream_key",
            "rtmp://a.rtmp.youtube.com/live2/your_youtube_key",
            "rtmp://ingest.globalcdn.live/your_custom_key"
        ]
        
        # Start RTMP streaming
        room_name = "live-presentation-room"
        layout = "https://your-domain.com/layouts/presentation.html"
        
        egress_id = await start_room_streaming_to_rtmp(
            egress_service=egress_service,
            room_name=room_name,
            rtmp_urls=rtmp_urls,
            layout=layout
        )
        
        logger.info(f"Started RTMP streaming with egress ID: {egress_id}")
        
        # Monitor streaming status
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to start RTMP streaming: {e}")


async def example_hls_streaming():
    """Example: Create HLS streaming with segments."""
    logger.info("=== HLS Streaming Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    # Configure S3 for HLS segments
    s3_config = S3Config(
        access_key="your_s3_access_key",
        secret="your_s3_secret",
        region="us-east-1",
        bucket="your-hls-bucket"
    )
    
    try:
        # Start HLS streaming
        room_name = "live-event-room"
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        filename_prefix = f"hls/{room_name}_{timestamp}/segment"
        playlist_name = f"hls/{room_name}_{timestamp}/playlist.m3u8"
        
        egress_id = await start_room_hls_streaming(
            egress_service=egress_service,
            room_name=room_name,
            filename_prefix=filename_prefix,
            playlist_name=playlist_name,
            s3_config=s3_config,
            segment_duration=6
        )
        
        logger.info(f"Started HLS streaming with egress ID: {egress_id}")
        logger.info(f"HLS playlist will be available at: s3://{s3_config.bucket}/{playlist_name}")
        
        # Monitor streaming status
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to start HLS streaming: {e}")


async def example_track_composite_recording():
    """Example: Record specific audio and video tracks."""
    logger.info("=== Track Composite Recording Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    # Configure multiple storage outputs
    s3_config = S3Config(
        access_key="your_s3_access_key",
        secret="your_s3_secret",
        region="us-east-1",
        bucket="your-recordings-bucket"
    )
    
    gcp_config = GCPConfig(
        credentials='{"type": "service_account", "project_id": "your-project"}',
        bucket="your-gcp-bucket"
    )
    
    try:
        # Create multiple file outputs
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        
        s3_output = egress_service.create_s3_file_output(
            filename=f"tracks/s3_recording_{timestamp}.mp4",
            s3_config=s3_config,
            output_format=OutputFormat.MP4
        )
        
        gcp_output = egress_service.create_gcp_file_output(
            filename=f"tracks/gcp_recording_{timestamp}.webm",
            gcp_config=gcp_config,
            output_format=OutputFormat.WEBM
        )
        
        # Create custom encoding options
        encoding_options = egress_service.create_encoding_options(
            width=1280,
            height=720,
            framerate=30,
            video_bitrate=2500,
            audio_bitrate=128,
            video_codec="h264_baseline",
            audio_codec="opus"
        )
        
        # Start track composite egress
        egress_id = await egress_service.start_track_composite_egress(
            room_name="interview-room",
            audio_track_id="interviewer_audio",
            video_track_id="interviewer_video",
            file_outputs=[s3_output, gcp_output],
            options=encoding_options
        )
        
        logger.info(f"Started track composite recording with egress ID: {egress_id}")
        
        # Monitor recording status
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to start track composite recording: {e}")


async def example_multi_format_recording():
    """Example: Record room in multiple formats simultaneously."""
    logger.info("=== Multi-Format Recording Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    # Configure storage
    s3_config = S3Config(
        access_key="your_s3_access_key",
        secret="your_s3_secret",
        region="us-east-1",
        bucket="your-recordings-bucket"
    )
    
    try:
        room_name = "multi-format-room"
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        
        # Create multiple file outputs with different formats
        mp4_output = egress_service.create_s3_file_output(
            filename=f"recordings/{room_name}_{timestamp}.mp4",
            s3_config=s3_config,
            output_format=OutputFormat.MP4
        )
        
        webm_output = egress_service.create_s3_file_output(
            filename=f"recordings/{room_name}_{timestamp}.webm",
            s3_config=s3_config,
            output_format=OutputFormat.WEBM
        )
        
        ogg_output = egress_service.create_s3_file_output(
            filename=f"recordings/{room_name}_{timestamp}.ogg",
            s3_config=s3_config,
            output_format=OutputFormat.OGG
        )
        
        # Create RTMP stream output
        rtmp_output = egress_service.create_rtmp_stream_output([
            "rtmp://live.example.com/stream/key123"
        ])
        
        # Create HLS segment output
        hls_output = egress_service.create_hls_segment_output(
            filename_prefix=f"hls/{room_name}_{timestamp}/segment",
            playlist_name=f"hls/{room_name}_{timestamp}/playlist.m3u8",
            s3_config=s3_config,
            segment_duration=6
        )
        
        # Start multi-format egress
        egress_id = await egress_service.start_room_composite_egress(
            room_name=room_name,
            file_outputs=[mp4_output, webm_output, ogg_output],
            stream_outputs=[rtmp_output],
            segment_outputs=[hls_output]
        )
        
        logger.info(f"Started multi-format recording with egress ID: {egress_id}")
        logger.info("Recording formats: MP4, WebM, OGG")
        logger.info("Streaming: RTMP, HLS")
        
        # Monitor recording status
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to start multi-format recording: {e}")


async def example_egress_management():
    """Example: Manage active egress instances."""
    logger.info("=== Egress Management Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    try:
        # List all active egress instances
        logger.info("Listing all active egress instances...")
        active_egress = await egress_service.list_egress(active=True)
        
        logger.info(f"Found {len(active_egress)} active egress instances:")
        for egress in active_egress:
            logger.info(f"  - ID: {egress['egress_id']}, Room: {egress['room_name']}, Status: {egress['status']}")
        
        # List egress for specific room
        room_name = "specific-room"
        room_egress = await egress_service.list_egress(room_name=room_name)
        logger.info(f"Found {len(room_egress)} egress instances for room '{room_name}'")
        
        # Get service health status
        health_status = egress_service.get_health_status()
        logger.info("Egress Service Health Status:")
        logger.info(f"  - Status: {health_status['status']}")
        logger.info(f"  - Active Egress: {health_status['active_egress']}")
        logger.info(f"  - Completed Egress: {health_status['completed_egress']}")
        logger.info(f"  - Failed Egress: {health_status['failed_egress']}")
        logger.info(f"  - Supported Formats: {', '.join(health_status['supported_formats'])}")
        logger.info(f"  - Supported Storage: {', '.join(health_status['supported_storage'])}")
        
        # Get active egress count
        active_count = await egress_service.get_active_egress_count()
        logger.info(f"Current active egress count: {active_count}")
        
        # Cleanup completed egress
        cleaned_count = await egress_service.cleanup_completed_egress()
        logger.info(f"Cleaned up {cleaned_count} completed egress instances")
        
    except Exception as e:
        logger.error(f"Failed to manage egress instances: {e}")


async def monitor_egress_status(egress_service: LiveKitEgressService, egress_id: str):
    """Monitor egress status until completion."""
    logger.info(f"Monitoring egress {egress_id}...")
    
    max_wait_time = 300  # 5 minutes
    check_interval = 10  # 10 seconds
    elapsed_time = 0
    
    while elapsed_time < max_wait_time:
        try:
            # Get current status
            status = await egress_service.get_egress_status(egress_id)
            
            if status:
                logger.info(f"Egress {egress_id} status: {status.status}")
                
                # Check if completed
                if status.status in ["EGRESS_COMPLETE", "EGRESS_FAILED", "EGRESS_ABORTED"]:
                    if status.status == "EGRESS_COMPLETE":
                        logger.info(f"Egress {egress_id} completed successfully!")
                        if status.file_results:
                            logger.info("File results:")
                            for result in status.file_results:
                                logger.info(f"  - {result}")
                        if status.stream_results:
                            logger.info("Stream results:")
                            for result in status.stream_results:
                                logger.info(f"  - {result}")
                    else:
                        logger.error(f"Egress {egress_id} failed with status: {status.status}")
                        if status.error:
                            logger.error(f"Error: {status.error}")
                    break
            else:
                logger.warning(f"Could not get status for egress {egress_id}")
            
            # Wait before next check
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
            
        except Exception as e:
            logger.error(f"Error monitoring egress status: {e}")
            break
    
    if elapsed_time >= max_wait_time:
        logger.warning(f"Monitoring timeout for egress {egress_id}")


async def example_dynamic_stream_management():
    """Example: Dynamically manage stream outputs during egress."""
    logger.info("=== Dynamic Stream Management Example ===")
    
    # Initialize clients
    livekit_client = LiveKitAPIClient(
        url="wss://your-livekit-server.com",
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    egress_service = LiveKitEgressService(livekit_client)
    
    try:
        # Start initial streaming
        initial_rtmp_urls = ["rtmp://stream1.example.com/live/key1"]
        
        rtmp_output = egress_service.create_rtmp_stream_output(initial_rtmp_urls)
        
        egress_id = await egress_service.start_room_composite_egress(
            room_name="dynamic-stream-room",
            stream_outputs=[rtmp_output]
        )
        
        logger.info(f"Started streaming with egress ID: {egress_id}")
        logger.info(f"Initial streams: {initial_rtmp_urls}")
        
        # Wait a bit, then add more streams
        await asyncio.sleep(30)
        
        additional_urls = [
            "rtmp://stream2.example.com/live/key2",
            "rtmp://stream3.example.com/live/key3"
        ]
        
        logger.info("Adding additional stream outputs...")
        await egress_service.update_stream(
            egress_id=egress_id,
            add_output_urls=additional_urls
        )
        
        logger.info(f"Added streams: {additional_urls}")
        
        # Wait a bit more, then remove one stream
        await asyncio.sleep(30)
        
        remove_urls = ["rtmp://stream1.example.com/live/key1"]
        
        logger.info("Removing stream output...")
        await egress_service.update_stream(
            egress_id=egress_id,
            remove_output_urls=remove_urls
        )
        
        logger.info(f"Removed streams: {remove_urls}")
        
        # Continue monitoring
        await monitor_egress_status(egress_service, egress_id)
        
    except Exception as e:
        logger.error(f"Failed to manage dynamic streams: {e}")


async def main():
    """Run all examples."""
    logger.info("Starting LiveKit Egress Service Examples")
    
    examples = [
        ("Room Recording to S3", example_room_recording_to_s3),
        ("Room RTMP Streaming", example_room_streaming_to_rtmp),
        ("HLS Streaming", example_hls_streaming),
        ("Track Composite Recording", example_track_composite_recording),
        ("Multi-Format Recording", example_multi_format_recording),
        ("Egress Management", example_egress_management),
        ("Dynamic Stream Management", example_dynamic_stream_management)
    ]
    
    for name, example_func in examples:
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running: {name}")
            logger.info(f"{'='*50}")
            
            await example_func()
            
            logger.info(f"✅ {name} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")
        
        # Wait between examples
        await asyncio.sleep(2)
    
    logger.info("\n🎉 All examples completed!")


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())