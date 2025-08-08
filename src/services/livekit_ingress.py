"""
LiveKit Ingress Service

This module provides comprehensive Ingress functionality for LiveKit according to the API specification:
- RTMP/RTMPS Ingress for OBS, XSplit
- WHIP Ingress for WebRTC-HTTP Ingestion Protocol
- URL Input for HLS, MP4, MOV files
- Support for all audio formats (OGG, MP3, M4A)
- Proper error handling and monitoring

Requirements addressed:
- 5.1: RTMP/RTMPS Ingress support for OBS, XSplit
- 5.2: WHIP Ingress for WebRTC-HTTP protocol
- 5.3: URL Input for HLS, MP4, MOV, MKV/WEBM, OGG, MP3, M4A
- 5.4: CreateIngress endpoint usage
- 5.5: ingressAdmin permission requirement
"""

import asyncio
import json
import logging
from datetime import datetime, UTC
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field

from livekit.api import (
    LiveKitAPI,
    CreateIngressRequest,
    UpdateIngressRequest,
    ListIngressRequest,
    DeleteIngressRequest,
    IngressInfo,
    IngressInput,
    IngressAudioOptions,
    IngressVideoOptions,
    IngressAudioEncodingPreset,
    IngressVideoEncodingPreset
)

from src.clients.livekit_api_client import LiveKitAPIClient
from src.metrics import get_metrics_collector, timer


logger = logging.getLogger(__name__)


class IngressType(str, Enum):
    """Ingress input types according to API specification."""
    RTMP_INPUT = "RTMP_INPUT"
    WHIP_INPUT = "WHIP_INPUT" 
    URL_INPUT = "URL_INPUT"


class IngressState(str, Enum):
    """Ingress state enumeration."""
    ENDPOINT_INACTIVE = "ENDPOINT_INACTIVE"
    ENDPOINT_BUFFERING = "ENDPOINT_BUFFERING"
    ENDPOINT_PUBLISHING = "ENDPOINT_PUBLISHING"
    ENDPOINT_ERROR = "ENDPOINT_ERROR"
    ENDPOINT_COMPLETE = "ENDPOINT_COMPLETE"


class AudioCodec(str, Enum):
    """Supported audio codecs."""
    OPUS = "opus"
    AAC = "aac"
    MP3 = "mp3"
    OGG = "ogg"
    FLAC = "flac"


class VideoCodec(str, Enum):
    """Supported video codecs."""
    H264_BASELINE = "h264_baseline"
    H264_MAIN = "h264_main"
    H264_HIGH = "h264_high"
    VP8 = "vp8"
    VP9 = "vp9"


class ContainerFormat(str, Enum):
    """Supported container formats."""
    MP4 = "mp4"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    AVI = "avi"
    FLV = "flv"
    TS = "ts"
    M4A = "m4a"
    OGG = "ogg"
    MP3 = "mp3"


@dataclass
class IngressConfig:
    """Ingress configuration tracking."""
    ingress_id: str
    name: str
    room_name: str
    participant_identity: str
    participant_name: str
    input_type: IngressType
    state: IngressState
    url: Optional[str] = None
    stream_key: Optional[str] = None
    created_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class RTMPIngressOptions:
    """RTMP Ingress specific options."""
    enable_transcoding: bool = True
    video_preset: Optional[IngressVideoEncodingPreset] = None
    audio_preset: Optional[IngressAudioEncodingPreset] = None
    bypass_transcoding: bool = False


@dataclass
class WHIPIngressOptions:
    """WHIP Ingress specific options."""
    bypass_transcoding: bool = False
    enable_transcoding: bool = True
    video_preset: Optional[IngressVideoEncodingPreset] = None
    audio_preset: Optional[IngressAudioEncodingPreset] = None


@dataclass
class URLIngressOptions:
    """URL Input specific options."""
    enable_transcoding: bool = True
    video_preset: Optional[IngressVideoEncodingPreset] = None
    audio_preset: Optional[IngressAudioEncodingPreset] = None
    bypass_transcoding: bool = False


class LiveKitIngressService:
    """
    LiveKit Ingress Service for media import according to API specification.
    
    Supports:
    - RTMP/RTMPS Ingress for OBS, XSplit
    - WHIP Ingress for WebRTC-HTTP Ingestion Protocol
    - URL Input for HLS, MP4, MOV, MKV/WEBM files
    - All audio formats (OGG, MP3, M4A)
    - Comprehensive monitoring and error handling
    """
    
    def __init__(self, client: LiveKitAPIClient):
        """
        Initialize LiveKit Ingress Service.
        
        Args:
            client: LiveKit API client instance
        """
        self.client = client
        self.livekit_api = LiveKitAPI(
            url=client.url,
            api_key=client.api_key,
            api_secret=client.api_secret
        )
        self.metrics_collector = get_metrics_collector()
        
        # Active ingress tracking
        self.active_ingress: Dict[str, IngressConfig] = {}
        
        logger.info("LiveKit Ingress Service initialized")
    
    # RTMP/RTMPS Ingress Methods
    
    async def create_rtmp_ingress(
        self,
        name: str,
        room_name: str,
        participant_identity: str,
        participant_name: Optional[str] = None,
        options: Optional[RTMPIngressOptions] = None
    ) -> Dict[str, Any]:
        """
        Create RTMP/RTMPS Ingress for OBS, XSplit according to specification.
        
        Args:
            name: Ingress name
            room_name: Target room name
            participant_identity: Participant identity
            participant_name: Display name for participant
            options: RTMP-specific options
            
        Returns:
            Dictionary with ingress_id, url, and stream_key
        """
        try:
            with timer("ingress_create_rtmp_duration"):
                # Set default options
                if options is None:
                    options = RTMPIngressOptions()
                
                # Build the request
                request = CreateIngressRequest()
                request.input_type = IngressInput.RTMP_INPUT
                request.name = name
                request.room_name = room_name
                request.participant_identity = participant_identity
                request.participant_name = participant_name or participant_identity
                request.bypass_transcoding = options.bypass_transcoding
                request.enable_transcoding = options.enable_transcoding
                
                # Set encoding presets if provided
                if options.video_preset:
                    video_options = IngressVideoOptions()
                    video_options.preset = options.video_preset
                    request.video.CopyFrom(video_options)
                
                if options.audio_preset:
                    audio_options = IngressAudioOptions()
                    audio_options.preset = options.audio_preset
                    request.audio.CopyFrom(audio_options)
                
                # Create ingress
                response = await self.livekit_api.ingress.create_ingress(request)
                
                # Track ingress
                ingress_config = IngressConfig(
                    ingress_id=response.ingress_id,
                    name=name,
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name=participant_name or participant_identity,
                    input_type=IngressType.RTMP_INPUT,
                    state=IngressState.ENDPOINT_INACTIVE,
                    url=response.url,
                    stream_key=response.stream_key,
                    created_at=datetime.now(UTC)
                )
                self.active_ingress[response.ingress_id] = ingress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "ingress_created_total",
                    labels={"type": "rtmp", "room": room_name}
                )
                
                result = {
                    "ingress_id": response.ingress_id,
                    "url": response.url,
                    "stream_key": response.stream_key,
                    "name": name,
                    "room_name": room_name,
                    "participant_identity": participant_identity,
                    "state": ingress_config.state
                }
                
                logger.info(
                    f"Created RTMP ingress {response.ingress_id} for room {room_name}",
                    extra={
                        "ingress_id": response.ingress_id,
                        "name": name,
                        "room_name": room_name,
                        "participant_identity": participant_identity,
                        "url": response.url
                    }
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to create RTMP ingress: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "rtmp", "error": "create_failed"}
            )
            raise
    
    # WHIP Ingress Methods
    
    async def create_whip_ingress(
        self,
        name: str,
        room_name: str,
        participant_identity: str,
        participant_name: Optional[str] = None,
        options: Optional[WHIPIngressOptions] = None
    ) -> Dict[str, Any]:
        """
        Create WHIP Ingress for WebRTC-HTTP Ingestion Protocol according to specification.
        
        Args:
            name: Ingress name
            room_name: Target room name
            participant_identity: Participant identity
            participant_name: Display name for participant
            options: WHIP-specific options
            
        Returns:
            Dictionary with ingress_id and url
        """
        try:
            with timer("ingress_create_whip_duration"):
                # Set default options
                if options is None:
                    options = WHIPIngressOptions()
                
                # Build the request
                request = CreateIngressRequest()
                request.input_type = IngressInput.WHIP_INPUT
                request.name = name
                request.room_name = room_name
                request.participant_identity = participant_identity
                request.participant_name = participant_name or participant_identity
                request.bypass_transcoding = options.bypass_transcoding
                request.enable_transcoding = options.enable_transcoding
                
                # Set encoding presets if provided
                if options.video_preset:
                    video_options = IngressVideoOptions()
                    video_options.preset = options.video_preset
                    request.video.CopyFrom(video_options)
                
                if options.audio_preset:
                    audio_options = IngressAudioOptions()
                    audio_options.preset = options.audio_preset
                    request.audio.CopyFrom(audio_options)
                
                # Create ingress
                response = await self.livekit_api.ingress.create_ingress(request)
                
                # Track ingress
                ingress_config = IngressConfig(
                    ingress_id=response.ingress_id,
                    name=name,
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name=participant_name or participant_identity,
                    input_type=IngressType.WHIP_INPUT,
                    state=IngressState.ENDPOINT_INACTIVE,
                    url=response.url,
                    created_at=datetime.now(UTC)
                )
                self.active_ingress[response.ingress_id] = ingress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "ingress_created_total",
                    labels={"type": "whip", "room": room_name}
                )
                
                result = {
                    "ingress_id": response.ingress_id,
                    "url": response.url,
                    "name": name,
                    "room_name": room_name,
                    "participant_identity": participant_identity,
                    "state": ingress_config.state
                }
                
                logger.info(
                    f"Created WHIP ingress {response.ingress_id} for room {room_name}",
                    extra={
                        "ingress_id": response.ingress_id,
                        "name": name,
                        "room_name": room_name,
                        "participant_identity": participant_identity,
                        "url": response.url
                    }
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to create WHIP ingress: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "whip", "error": "create_failed"}
            )
            raise
    
    # URL Input Methods
    
    async def create_url_ingress(
        self,
        name: str,
        room_name: str,
        participant_identity: str,
        url: str,
        participant_name: Optional[str] = None,
        options: Optional[URLIngressOptions] = None
    ) -> Dict[str, Any]:
        """
        Create URL Input Ingress for HLS, MP4, MOV files according to specification.
        
        Supports formats:
        - HLS streams
        - MP4, MOV files
        - MKV/WEBM containers
        - OGG, MP3, M4A audio
        
        Args:
            name: Ingress name
            room_name: Target room name
            participant_identity: Participant identity
            url: Source URL
            participant_name: Display name for participant
            options: URL Input specific options
            
        Returns:
            Dictionary with ingress_id and configuration
        """
        try:
            with timer("ingress_create_url_duration"):
                # Validate URL format
                supported_formats = self._get_supported_url_formats()
                if not self._is_supported_url_format(url, supported_formats):
                    raise ValueError(f"Unsupported URL format. Supported: {', '.join(supported_formats)}")
                
                # Set default options
                if options is None:
                    options = URLIngressOptions()
                
                # Build the request
                request = CreateIngressRequest()
                request.input_type = IngressInput.URL_INPUT
                request.name = name
                request.room_name = room_name
                request.participant_identity = participant_identity
                request.participant_name = participant_name or participant_identity
                request.url = url
                request.bypass_transcoding = options.bypass_transcoding
                request.enable_transcoding = options.enable_transcoding
                
                # Set encoding presets if provided
                if options.video_preset:
                    video_options = IngressVideoOptions()
                    video_options.preset = options.video_preset
                    request.video.CopyFrom(video_options)
                
                if options.audio_preset:
                    audio_options = IngressAudioOptions()
                    audio_options.preset = options.audio_preset
                    request.audio.CopyFrom(audio_options)
                
                # Create ingress
                response = await self.livekit_api.ingress.create_ingress(request)
                
                # Track ingress
                ingress_config = IngressConfig(
                    ingress_id=response.ingress_id,
                    name=name,
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name=participant_name or participant_identity,
                    input_type=IngressType.URL_INPUT,
                    state=IngressState.ENDPOINT_INACTIVE,
                    url=url,
                    created_at=datetime.now(UTC)
                )
                self.active_ingress[response.ingress_id] = ingress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "ingress_created_total",
                    labels={"type": "url", "room": room_name}
                )
                
                result = {
                    "ingress_id": response.ingress_id,
                    "name": name,
                    "room_name": room_name,
                    "participant_identity": participant_identity,
                    "source_url": url,
                    "state": ingress_config.state
                }
                
                logger.info(
                    f"Created URL ingress {response.ingress_id} for room {room_name}",
                    extra={
                        "ingress_id": response.ingress_id,
                        "name": name,
                        "room_name": room_name,
                        "participant_identity": participant_identity,
                        "source_url": url
                    }
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to create URL ingress: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "url", "error": "create_failed"}
            )
            raise
    
    # Ingress Management Methods
    
    async def update_ingress(
        self,
        ingress_id: str,
        name: Optional[str] = None,
        room_name: Optional[str] = None,
        participant_identity: Optional[str] = None,
        participant_name: Optional[str] = None,
        bypass_transcoding: Optional[bool] = None,
        enable_transcoding: Optional[bool] = None,
        audio_preset: Optional[IngressAudioEncodingPreset] = None,
        video_preset: Optional[IngressVideoEncodingPreset] = None
    ) -> Dict[str, Any]:
        """
        Update existing ingress configuration.
        
        Args:
            ingress_id: Ingress ID to update
            name: New name (optional)
            room_name: New room name (optional)
            participant_identity: New participant identity (optional)
            participant_name: New participant name (optional)
            bypass_transcoding: Bypass transcoding flag (optional)
            enable_transcoding: Enable transcoding flag (optional)
            audio_preset: Audio encoding preset (optional)
            video_preset: Video encoding preset (optional)
            
        Returns:
            Updated ingress information
        """
        try:
            with timer("ingress_update_duration"):
                # Build the request
                request = UpdateIngressRequest()
                request.ingress_id = ingress_id
                
                if name is not None:
                    request.name = name
                if room_name is not None:
                    request.room_name = room_name
                if participant_identity is not None:
                    request.participant_identity = participant_identity
                if participant_name is not None:
                    request.participant_name = participant_name
                if bypass_transcoding is not None:
                    request.bypass_transcoding = bypass_transcoding
                if enable_transcoding is not None:
                    request.enable_transcoding = enable_transcoding
                
                # Set encoding presets if provided
                if video_preset is not None:
                    video_options = IngressVideoOptions()
                    video_options.preset = video_preset
                    request.video.CopyFrom(video_options)
                
                if audio_preset is not None:
                    audio_options = IngressAudioOptions()
                    audio_options.preset = audio_preset
                    request.audio.CopyFrom(audio_options)
                
                # Update ingress
                response = await self.livekit_api.ingress.update_ingress(request)
                
                # Update tracking
                if ingress_id in self.active_ingress:
                    config = self.active_ingress[ingress_id]
                    if name is not None:
                        config.name = name
                    if room_name is not None:
                        config.room_name = room_name
                    if participant_identity is not None:
                        config.participant_identity = participant_identity
                    if participant_name is not None:
                        config.participant_name = participant_name
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "ingress_updated_total",
                    labels={"ingress_id": ingress_id}
                )
                
                result = {
                    "ingress_id": response.ingress_id,
                    "name": response.name,
                    "room_name": response.room_name,
                    "participant_identity": response.participant_identity,
                    "participant_name": response.participant_name,
                    "state": response.state,
                    "url": response.url,
                    "stream_key": getattr(response, 'stream_key', None)
                }
                
                logger.info(f"Updated ingress {ingress_id}")
                return result
                
        except Exception as e:
            logger.error(f"Failed to update ingress {ingress_id}: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "update", "error": "update_failed"}
            )
            raise
    
    async def list_ingress(
        self,
        room_name: Optional[str] = None,
        ingress_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List ingress instances.
        
        Args:
            room_name: Filter by room name (optional)
            ingress_id: Filter by ingress ID (optional)
            
        Returns:
            List of ingress information
        """
        try:
            with timer("ingress_list_duration"):
                request = ListIngressRequest()
                if room_name:
                    request.room_name = room_name
                if ingress_id:
                    request.ingress_id = ingress_id
                
                response = await self.livekit_api.ingress.list_ingress(request)
                
                ingress_list = []
                for ingress_info in response.items:
                    ingress_data = {
                        "ingress_id": ingress_info.ingress_id,
                        "name": ingress_info.name,
                        "stream_key": getattr(ingress_info, 'stream_key', None),
                        "url": ingress_info.url,
                        "input_type": ingress_info.input_type,
                        "bypass_transcoding": ingress_info.bypass_transcoding,
                        "enable_transcoding": ingress_info.enable_transcoding,
                        "room_name": ingress_info.room_name,
                        "participant_identity": ingress_info.participant_identity,
                        "participant_name": ingress_info.participant_name,
                        "reusable": ingress_info.reusable,
                        "state": ingress_info.state
                    }
                    ingress_list.append(ingress_data)
                
                logger.info(f"Listed {len(ingress_list)} ingress instances")
                return ingress_list
                
        except Exception as e:
            logger.error(f"Failed to list ingress: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "list", "error": "list_failed"}
            )
            raise
    
    async def delete_ingress(self, ingress_id: str) -> None:
        """
        Delete ingress instance.
        
        Args:
            ingress_id: Ingress ID to delete
        """
        try:
            with timer("ingress_delete_duration"):
                request = DeleteIngressRequest(ingress_id=ingress_id)
                await self.livekit_api.ingress.delete_ingress(request)
                
                # Remove from tracking
                if ingress_id in self.active_ingress:
                    del self.active_ingress[ingress_id]
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "ingress_deleted_total",
                    labels={"ingress_id": ingress_id}
                )
                
                logger.info(f"Deleted ingress {ingress_id}")
                
        except Exception as e:
            logger.error(f"Failed to delete ingress {ingress_id}: {e}")
            self.metrics_collector.increment_counter(
                "ingress_errors_total",
                labels={"type": "delete", "error": "delete_failed"}
            )
            raise
    
    # Utility Methods
    
    def _get_supported_url_formats(self) -> List[str]:
        """Get list of supported URL formats."""
        return [
            # Video containers
            ".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".ts",
            # Audio formats
            ".m4a", ".ogg", ".mp3", ".aac", ".flac", ".wav",
            # Streaming protocols
            ".m3u8",  # HLS
            "rtmp://", "rtmps://",  # RTMP
            "http://", "https://"   # HTTP streams
        ]
    
    def _is_supported_url_format(self, url: str, supported_formats: List[str]) -> bool:
        """Check if URL format is supported."""
        url_lower = url.lower()
        
        # Check for file extensions first (more specific)
        for fmt in supported_formats:
            if fmt.startswith('.') and url_lower.endswith(fmt):
                return True
        
        # Check for protocol prefixes only if no file extension matched
        # and the URL doesn't have a file extension or has a supported one
        has_extension = '.' in url_lower.split('/')[-1]  # Check if last part has extension
        if not has_extension:
            # No extension, check protocols
            for fmt in supported_formats:
                if not fmt.startswith('.') and url_lower.startswith(fmt):
                    return True
        
        return False
    
    def get_ingress_status(self, ingress_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of tracked ingress.
        
        Args:
            ingress_id: Ingress ID
            
        Returns:
            Ingress status information or None if not found
        """
        if ingress_id in self.active_ingress:
            config = self.active_ingress[ingress_id]
            return {
                "ingress_id": config.ingress_id,
                "name": config.name,
                "room_name": config.room_name,
                "participant_identity": config.participant_identity,
                "participant_name": config.participant_name,
                "input_type": config.input_type,
                "state": config.state,
                "url": config.url,
                "stream_key": config.stream_key,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "error": config.error
            }
        return None
    
    def get_active_ingress_count(self) -> int:
        """Get count of active ingress instances."""
        return len(self.active_ingress)
    
    def get_ingress_by_room(self, room_name: str) -> List[Dict[str, Any]]:
        """
        Get all ingress instances for a specific room.
        
        Args:
            room_name: Room name to filter by
            
        Returns:
            List of ingress instances for the room
        """
        room_ingress = []
        for config in self.active_ingress.values():
            if config.room_name == room_name:
                room_ingress.append({
                    "ingress_id": config.ingress_id,
                    "name": config.name,
                    "participant_identity": config.participant_identity,
                    "participant_name": config.participant_name,
                    "input_type": config.input_type,
                    "state": config.state,
                    "url": config.url,
                    "stream_key": config.stream_key,
                    "created_at": config.created_at.isoformat() if config.created_at else None
                })
        return room_ingress
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for Ingress service.
        
        Returns:
            Health check results
        """
        try:
            # Test listing ingress to verify API connectivity
            start_time = datetime.now(UTC)
            await self.list_ingress()
            end_time = datetime.now(UTC)
            
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "service": "ingress",
                "latency_ms": round(latency_ms, 2),
                "active_ingress_count": self.get_active_ingress_count(),
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "ingress",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }


# Factory function for creating ingress service
def create_ingress_service(client: LiveKitAPIClient) -> LiveKitIngressService:
    """
    Factory function to create LiveKit Ingress Service.
    
    Args:
        client: LiveKit API client
        
    Returns:
        LiveKitIngressService instance
    """
    return LiveKitIngressService(client)