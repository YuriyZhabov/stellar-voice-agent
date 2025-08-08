"""
LiveKit Egress Service

This module provides comprehensive Egress functionality for LiveKit according to the API specification:
- Room Composite Egress with support for MP4, OGG, RTMP, HLS
- Track Composite Egress for audio/video synchronization
- File output configurations for S3, Azure Blob, Google Cloud Storage
- RTMP streaming output support
- Proper error handling and monitoring
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
    RoomCompositeEgressRequest,
    TrackCompositeEgressRequest,
    TrackEgressRequest,
    ParticipantEgressRequest,
    StopEgressRequest,
    ListEgressRequest,
    ListEgressResponse,
    UpdateLayoutRequest,
    UpdateStreamRequest,
    EncodedFileOutput,
    StreamOutput,
    SegmentedFileOutput,
    ImageOutput,
    S3Upload,
    GCPUpload,
    AzureBlobUpload,
    AliOSSUpload,
    EncodingOptions,
    EncodingOptionsPreset,
    EgressInfo,
    EgressStatus as APIEgressStatus
)

from src.clients.livekit_api_client import LiveKitAPIClient
from src.metrics import get_metrics_collector, timer


logger = logging.getLogger(__name__)


class EgressStatus(str, Enum):
    """Egress status enumeration."""
    EGRESS_STARTING = "EGRESS_STARTING"
    EGRESS_ACTIVE = "EGRESS_ACTIVE"
    EGRESS_ENDING = "EGRESS_ENDING"
    EGRESS_COMPLETE = "EGRESS_COMPLETE"
    EGRESS_FAILED = "EGRESS_FAILED"
    EGRESS_ABORTED = "EGRESS_ABORTED"
    EGRESS_LIMIT_REACHED = "EGRESS_LIMIT_REACHED"


class OutputFormat(str, Enum):
    """Supported output formats."""
    MP4 = "mp4"
    OGG = "ogg"
    WEBM = "webm"
    TS = "ts"
    HLS = "hls"
    RTMP = "rtmp"
    SRT = "srt"


class StorageProvider(str, Enum):
    """Supported cloud storage providers."""
    S3 = "s3"
    GCP = "gcp"
    AZURE = "azure"
    ALIOSS = "alioss"


@dataclass
class EgressConfig:
    """Base egress configuration."""
    egress_id: str
    room_name: str
    status: EgressStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error: Optional[str] = None
    file_results: List[Dict[str, Any]] = field(default_factory=list)
    stream_results: List[Dict[str, Any]] = field(default_factory=list)
    segment_results: List[Dict[str, Any]] = field(default_factory=list)
    image_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class S3Config:
    """S3 storage configuration."""
    access_key: str
    secret: str
    region: str
    bucket: str
    endpoint: Optional[str] = None
    force_path_style: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    tagging: Optional[str] = None


@dataclass
class GCPConfig:
    """Google Cloud Platform storage configuration."""
    credentials: str  # JSON credentials as string
    bucket: str


@dataclass
class AzureConfig:
    """Azure Blob storage configuration."""
    account_name: str
    account_key: str
    container_name: str


@dataclass
class AliOSSConfig:
    """Alibaba Cloud OSS storage configuration."""
    access_key: str
    secret: str
    region: str
    bucket: str
    endpoint: Optional[str] = None


class LiveKitEgressService:
    """
    LiveKit Egress Service for recording and exporting according to API specification.
    
    Supports:
    - Room Composite Egress (MP4, OGG, RTMP, HLS)
    - Track Composite Egress (audio/video sync)
    - Track Egress (individual tracks)
    - Multiple cloud storage providers
    - RTMP streaming output
    - Comprehensive monitoring and error handling
    """
    
    def __init__(self, client: LiveKitAPIClient):
        """
        Initialize LiveKit Egress Service.
        
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
        
        # Active egress tracking
        self.active_egress: Dict[str, EgressConfig] = {}
        
        logger.info("LiveKit Egress Service initialized")
    
    # Room Composite Egress Methods
    
    async def start_room_composite_egress(
        self,
        room_name: str,
        layout: Optional[str] = None,
        audio_only: bool = False,
        video_only: bool = False,
        custom_base_url: Optional[str] = None,
        file_outputs: Optional[List[EncodedFileOutput]] = None,
        stream_outputs: Optional[List[StreamOutput]] = None,
        segment_outputs: Optional[List[SegmentedFileOutput]] = None,
        image_outputs: Optional[List[ImageOutput]] = None,
        options: Optional[EncodingOptions] = None,
        preset: Optional[EncodingOptionsPreset] = None
    ) -> str:
        """
        Start Room Composite Egress according to API specification.
        
        Args:
            room_name: Name of the room to record
            layout: Custom layout URL or built-in layout name
            audio_only: Record audio only
            video_only: Record video only
            custom_base_url: Custom base URL for layout
            file_outputs: List of file outputs (MP4, OGG, etc.)
            stream_outputs: List of stream outputs (RTMP, SRT)
            segment_outputs: List of segmented outputs (HLS)
            image_outputs: List of image outputs
            options: Custom encoding options
            preset: Encoding preset
            
        Returns:
            Egress ID
        """
        try:
            with timer("egress_start_room_composite_duration"):
                # Build the request
                request = RoomCompositeEgressRequest(
                    room_name=room_name,
                    layout=layout or "",
                    audio_only=audio_only,
                    video_only=video_only,
                    custom_base_url=custom_base_url or ""
                )
                
                # Add outputs
                if file_outputs:
                    if len(file_outputs) == 1:
                        request.file = file_outputs[0]
                    else:
                        # For multiple outputs, use the first one as primary
                        request.file = file_outputs[0]
                
                if stream_outputs:
                    if len(stream_outputs) == 1:
                        request.stream = stream_outputs[0]
                    else:
                        # For multiple outputs, use the first one as primary
                        request.stream = stream_outputs[0]
                
                if segment_outputs:
                    if len(segment_outputs) == 1:
                        request.segments = segment_outputs[0]
                
                # Set encoding options
                if options:
                    request.advanced = options
                elif preset:
                    request.preset = preset
                
                # Start egress
                response = await self.livekit_api.egress.start_room_composite_egress(request)
                
                # Track egress
                egress_config = EgressConfig(
                    egress_id=response.egress_id,
                    room_name=room_name,
                    status=EgressStatus.EGRESS_STARTING,
                    started_at=datetime.now(UTC)
                )
                self.active_egress[response.egress_id] = egress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "egress_started_total",
                    labels={"type": "room_composite", "room": room_name}
                )
                
                logger.info(
                    f"Started room composite egress {response.egress_id} for room {room_name}",
                    extra={
                        "egress_id": response.egress_id,
                        "room_name": room_name,
                        "audio_only": audio_only,
                        "video_only": video_only
                    }
                )
                
                return response.egress_id
                
        except Exception as e:
            logger.error(f"Failed to start room composite egress: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "room_composite", "error": "start_failed"}
            )
            raise
    
    async def start_track_composite_egress(
        self,
        room_name: str,
        audio_track_id: Optional[str] = None,
        video_track_id: Optional[str] = None,
        file_outputs: Optional[List[EncodedFileOutput]] = None,
        stream_outputs: Optional[List[StreamOutput]] = None,
        segment_outputs: Optional[List[SegmentedFileOutput]] = None,
        image_outputs: Optional[List[ImageOutput]] = None,
        options: Optional[EncodingOptions] = None,
        preset: Optional[EncodingOptionsPreset] = None
    ) -> str:
        """
        Start Track Composite Egress for synchronized audio/video tracks.
        
        Args:
            room_name: Name of the room
            audio_track_id: Audio track ID to record
            video_track_id: Video track ID to record
            file_outputs: List of file outputs
            stream_outputs: List of stream outputs
            segment_outputs: List of segmented outputs
            image_outputs: List of image outputs
            options: Custom encoding options
            preset: Encoding preset
            
        Returns:
            Egress ID
        """
        try:
            with timer("egress_start_track_composite_duration"):
                # Build the request
                request = TrackCompositeEgressRequest(
                    room_name=room_name,
                    audio_track_id=audio_track_id or "",
                    video_track_id=video_track_id or ""
                )
                
                # Add outputs
                if file_outputs:
                    request.file = file_outputs[0]
                
                if stream_outputs:
                    request.stream = stream_outputs[0]
                
                if segment_outputs:
                    request.segments = segment_outputs[0]
                
                # Set encoding options
                if options:
                    request.advanced = options
                elif preset:
                    request.preset = preset
                
                # Start egress
                response = await self.livekit_api.egress.start_track_composite_egress(request)
                
                # Track egress
                egress_config = EgressConfig(
                    egress_id=response.egress_id,
                    room_name=room_name,
                    status=EgressStatus.EGRESS_STARTING,
                    started_at=datetime.now(UTC)
                )
                self.active_egress[response.egress_id] = egress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "egress_started_total",
                    labels={"type": "track_composite", "room": room_name}
                )
                
                logger.info(
                    f"Started track composite egress {response.egress_id} for room {room_name}",
                    extra={
                        "egress_id": response.egress_id,
                        "room_name": room_name,
                        "audio_track_id": audio_track_id,
                        "video_track_id": video_track_id
                    }
                )
                
                return response.egress_id
                
        except Exception as e:
            logger.error(f"Failed to start track composite egress: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "track_composite", "error": "start_failed"}
            )
            raise
    
    async def start_track_egress(
        self,
        room_name: str,
        track_id: str,
        file_output: Optional[EncodedFileOutput] = None,
        websocket_url: Optional[str] = None
    ) -> str:
        """
        Start individual Track Egress.
        
        Args:
            room_name: Name of the room
            track_id: Track ID to record
            file_output: File output configuration
            websocket_url: WebSocket URL for raw track data
            
        Returns:
            Egress ID
        """
        try:
            with timer("egress_start_track_duration"):
                # Build the request
                request = TrackEgressRequest(
                    room_name=room_name,
                    track_id=track_id
                )
                
                # Add output
                if file_output:
                    request.file = file_output
                elif websocket_url:
                    request.websocket_url = websocket_url
                
                # Start egress
                response = await self.livekit_api.egress.start_track_egress(request)
                
                # Track egress
                egress_config = EgressConfig(
                    egress_id=response.egress_id,
                    room_name=room_name,
                    status=EgressStatus.EGRESS_STARTING,
                    started_at=datetime.now(UTC)
                )
                self.active_egress[response.egress_id] = egress_config
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "egress_started_total",
                    labels={"type": "track", "room": room_name}
                )
                
                logger.info(
                    f"Started track egress {response.egress_id} for track {track_id}",
                    extra={
                        "egress_id": response.egress_id,
                        "room_name": room_name,
                        "track_id": track_id
                    }
                )
                
                return response.egress_id
                
        except Exception as e:
            logger.error(f"Failed to start track egress: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "track", "error": "start_failed"}
            )
            raise    

    # Egress Management Methods
    
    async def stop_egress(self, egress_id: str) -> None:
        """
        Stop active egress.
        
        Args:
            egress_id: Egress ID to stop
        """
        try:
            with timer("egress_stop_duration"):
                request = StopEgressRequest(egress_id=egress_id)
                response = await self.livekit_api.egress.stop_egress(request)
                
                # Update tracking
                if egress_id in self.active_egress:
                    self.active_egress[egress_id].status = EgressStatus.EGRESS_ENDING
                    self.active_egress[egress_id].ended_at = datetime.now(UTC)
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "egress_stopped_total",
                    labels={"egress_id": egress_id}
                )
                
                logger.info(f"Stopped egress {egress_id}")
                
        except Exception as e:
            logger.error(f"Failed to stop egress {egress_id}: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "stop", "error": "stop_failed"}
            )
            raise
    
    async def list_egress(
        self,
        room_name: Optional[str] = None,
        egress_id: Optional[str] = None,
        active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        List egress instances.
        
        Args:
            room_name: Filter by room name
            egress_id: Filter by egress ID
            active: Filter by active status
            
        Returns:
            List of egress information
        """
        try:
            with timer("egress_list_duration"):
                request = ListEgressRequest(
                    room_name=room_name or "",
                    egress_id=egress_id or "",
                    active=active if active is not None else False
                )
                
                response = await self.livekit_api.egress.list_egress(request)
                
                egress_list = []
                for egress_info in response.items:
                    egress_data = {
                        "egress_id": egress_info.egress_id,
                        "room_id": egress_info.room_id,
                        "room_name": egress_info.room_name,
                        "status": egress_info.status,
                        "started_at": egress_info.started_at,
                        "ended_at": egress_info.ended_at,
                        "error": egress_info.error,
                        "file_results": [
                            {
                                "filename": result.filename,
                                "started_at": result.started_at,
                                "ended_at": result.ended_at,
                                "duration": result.duration,
                                "size": result.size,
                                "location": result.location
                            }
                            for result in egress_info.file_results
                        ],
                        "stream_results": [
                            {
                                "url": result.url,
                                "started_at": result.started_at,
                                "ended_at": result.ended_at,
                                "duration": result.duration,
                                "error": result.error
                            }
                            for result in egress_info.stream_results
                        ]
                    }
                    egress_list.append(egress_data)
                
                logger.info(f"Listed {len(egress_list)} egress instances")
                return egress_list
                
        except Exception as e:
            logger.error(f"Failed to list egress: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "list", "error": "list_failed"}
            )
            raise
    
    async def update_layout(self, egress_id: str, layout: str) -> None:
        """
        Update layout for active room composite egress.
        
        Args:
            egress_id: Egress ID to update
            layout: New layout URL or name
        """
        try:
            with timer("egress_update_layout_duration"):
                request = UpdateLayoutRequest(
                    egress_id=egress_id,
                    layout=layout
                )
                
                await self.livekit_api.egress.update_layout(request)
                
                logger.info(f"Updated layout for egress {egress_id}")
                
        except Exception as e:
            logger.error(f"Failed to update layout for egress {egress_id}: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "update_layout", "error": "update_failed"}
            )
            raise
    
    async def update_stream(
        self,
        egress_id: str,
        add_output_urls: Optional[List[str]] = None,
        remove_output_urls: Optional[List[str]] = None
    ) -> None:
        """
        Update stream outputs for active egress.
        
        Args:
            egress_id: Egress ID to update
            add_output_urls: URLs to add
            remove_output_urls: URLs to remove
        """
        try:
            with timer("egress_update_stream_duration"):
                request = UpdateStreamRequest(
                    egress_id=egress_id,
                    add_output_urls=add_output_urls or [],
                    remove_output_urls=remove_output_urls or []
                )
                
                await self.livekit_api.egress.update_stream(request)
                
                logger.info(f"Updated stream outputs for egress {egress_id}")
                
        except Exception as e:
            logger.error(f"Failed to update stream for egress {egress_id}: {e}")
            self.metrics_collector.increment_counter(
                "egress_errors_total",
                labels={"type": "update_stream", "error": "update_failed"}
            )
            raise
    
    # Output Configuration Methods
    
    def create_s3_file_output(
        self,
        filename: str,
        s3_config: S3Config,
        output_format: OutputFormat = OutputFormat.MP4,
        disable_manifest: bool = False
    ) -> EncodedFileOutput:
        """
        Create S3 file output configuration.
        
        Args:
            filename: Output filename
            s3_config: S3 configuration
            output_format: Output format (MP4, OGG, etc.)
            disable_manifest: Disable manifest generation
            
        Returns:
            EncodedFileOutput configuration
        """
        try:
            s3_upload = S3Upload()
            s3_upload.access_key = s3_config.access_key
            s3_upload.secret = s3_config.secret
            s3_upload.region = s3_config.region
            s3_upload.bucket = s3_config.bucket
            s3_upload.endpoint = s3_config.endpoint or ""
            s3_upload.force_path_style = s3_config.force_path_style
            for key, value in s3_config.metadata.items():
                s3_upload.metadata[key] = value
            s3_upload.tagging = s3_config.tagging or ""
            
            output = EncodedFileOutput()
            output.file_type = self._get_file_type_from_format(output_format)
            output.filepath = filename
            output.disable_manifest = disable_manifest
            output.s3.CopyFrom(s3_upload)
            
            logger.debug(f"Created S3 file output configuration for {filename}")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create S3 file output: {e}")
            raise
    
    def create_gcp_file_output(
        self,
        filename: str,
        gcp_config: GCPConfig,
        output_format: OutputFormat = OutputFormat.MP4,
        disable_manifest: bool = False
    ) -> EncodedFileOutput:
        """
        Create Google Cloud Platform file output configuration.
        
        Args:
            filename: Output filename
            gcp_config: GCP configuration
            output_format: Output format
            disable_manifest: Disable manifest generation
            
        Returns:
            EncodedFileOutput configuration
        """
        try:
            gcp_upload = GCPUpload()
            gcp_upload.credentials = gcp_config.credentials
            gcp_upload.bucket = gcp_config.bucket
            
            output = EncodedFileOutput()
            output.file_type = self._get_file_type_from_format(output_format)
            output.filepath = filename
            output.disable_manifest = disable_manifest
            output.gcp.CopyFrom(gcp_upload)
            
            logger.debug(f"Created GCP file output configuration for {filename}")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create GCP file output: {e}")
            raise
    
    def create_azure_file_output(
        self,
        filename: str,
        azure_config: AzureConfig,
        output_format: OutputFormat = OutputFormat.MP4,
        disable_manifest: bool = False
    ) -> EncodedFileOutput:
        """
        Create Azure Blob Storage file output configuration.
        
        Args:
            filename: Output filename
            azure_config: Azure configuration
            output_format: Output format
            disable_manifest: Disable manifest generation
            
        Returns:
            EncodedFileOutput configuration
        """
        try:
            azure_upload = AzureBlobUpload()
            azure_upload.account_name = azure_config.account_name
            azure_upload.account_key = azure_config.account_key
            azure_upload.container_name = azure_config.container_name
            
            output = EncodedFileOutput()
            output.file_type = self._get_file_type_from_format(output_format)
            output.filepath = filename
            output.disable_manifest = disable_manifest
            output.azure.CopyFrom(azure_upload)
            
            logger.debug(f"Created Azure file output configuration for {filename}")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create Azure file output: {e}")
            raise
    
    def create_alioss_file_output(
        self,
        filename: str,
        alioss_config: AliOSSConfig,
        output_format: OutputFormat = OutputFormat.MP4,
        disable_manifest: bool = False
    ) -> EncodedFileOutput:
        """
        Create Alibaba Cloud OSS file output configuration.
        
        Args:
            filename: Output filename
            alioss_config: AliOSS configuration
            output_format: Output format
            disable_manifest: Disable manifest generation
            
        Returns:
            EncodedFileOutput configuration
        """
        try:
            alioss_upload = AliOSSUpload()
            alioss_upload.access_key = alioss_config.access_key
            alioss_upload.secret = alioss_config.secret
            alioss_upload.region = alioss_config.region
            alioss_upload.bucket = alioss_config.bucket
            alioss_upload.endpoint = alioss_config.endpoint or ""
            
            output = EncodedFileOutput()
            output.file_type = self._get_file_type_from_format(output_format)
            output.filepath = filename
            output.disable_manifest = disable_manifest
            output.aliOSS.CopyFrom(alioss_upload)
            
            logger.debug(f"Created AliOSS file output configuration for {filename}")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create AliOSS file output: {e}")
            raise
    
    def create_rtmp_stream_output(
        self,
        urls: List[str]
    ) -> StreamOutput:
        """
        Create RTMP stream output configuration.
        
        Args:
            urls: List of RTMP URLs
            
        Returns:
            StreamOutput configuration
        """
        try:
            from livekit.api import RTMP
            
            output = StreamOutput()
            output.protocol = RTMP
            output.urls.extend(urls)
            
            logger.debug(f"Created RTMP stream output for {len(urls)} URLs")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create RTMP stream output: {e}")
            raise
    
    def create_srt_stream_output(
        self,
        urls: List[str]
    ) -> StreamOutput:
        """
        Create SRT stream output configuration.
        
        Args:
            urls: List of SRT URLs
            
        Returns:
            StreamOutput configuration
        """
        try:
            from livekit.api import SRT
            
            output = StreamOutput()
            output.protocol = SRT
            output.urls.extend(urls)
            
            logger.debug(f"Created SRT stream output for {len(urls)} URLs")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create SRT stream output: {e}")
            raise
    
    def create_hls_segment_output(
        self,
        filename_prefix: str,
        playlist_name: str,
        segment_duration: int = 6,
        s3_config: Optional[S3Config] = None,
        gcp_config: Optional[GCPConfig] = None,
        azure_config: Optional[AzureConfig] = None
    ) -> SegmentedFileOutput:
        """
        Create HLS segmented output configuration.
        
        Args:
            filename_prefix: Prefix for segment files
            playlist_name: Name of the playlist file
            segment_duration: Duration of each segment in seconds
            s3_config: S3 configuration (optional)
            gcp_config: GCP configuration (optional)
            azure_config: Azure configuration (optional)
            
        Returns:
            SegmentedFileOutput configuration
        """
        try:
            from livekit.api import HLS_PROTOCOL
            
            output = SegmentedFileOutput()
            output.protocol = HLS_PROTOCOL
            output.filename_prefix = filename_prefix
            output.playlist_name = playlist_name
            output.segment_duration = segment_duration
            
            # Add cloud storage if provided
            if s3_config:
                s3_upload = S3Upload()
                s3_upload.access_key = s3_config.access_key
                s3_upload.secret = s3_config.secret
                s3_upload.region = s3_config.region
                s3_upload.bucket = s3_config.bucket
                s3_upload.endpoint = s3_config.endpoint or ""
                s3_upload.force_path_style = s3_config.force_path_style
                for key, value in s3_config.metadata.items():
                    s3_upload.metadata[key] = value
                s3_upload.tagging = s3_config.tagging or ""
                output.s3.CopyFrom(s3_upload)
            elif gcp_config:
                gcp_upload = GCPUpload()
                gcp_upload.credentials = gcp_config.credentials
                gcp_upload.bucket = gcp_config.bucket
                output.gcp.CopyFrom(gcp_upload)
            elif azure_config:
                azure_upload = AzureBlobUpload()
                azure_upload.account_name = azure_config.account_name
                azure_upload.account_key = azure_config.account_key
                azure_upload.container_name = azure_config.container_name
                output.azure.CopyFrom(azure_upload)
            
            logger.debug(f"Created HLS segment output with prefix {filename_prefix}")
            return output
            
        except Exception as e:
            logger.error(f"Failed to create HLS segment output: {e}")
            raise
    
    def create_encoding_options(
        self,
        width: int = 1920,
        height: int = 1080,
        depth: int = 24,
        framerate: int = 30,
        audio_codec: str = "opus",
        audio_bitrate: int = 128,
        audio_frequency: int = 48000,
        video_codec: str = "h264_baseline",
        video_bitrate: int = 4500,
        key_frame_interval: float = 4.0
    ) -> EncodingOptions:
        """
        Create custom encoding options.
        
        Args:
            width: Video width
            height: Video height
            depth: Color depth
            framerate: Video framerate
            audio_codec: Audio codec
            audio_bitrate: Audio bitrate in kbps
            audio_frequency: Audio frequency in Hz
            video_codec: Video codec
            video_bitrate: Video bitrate in kbps
            key_frame_interval: Key frame interval in seconds
            
        Returns:
            EncodingOptions configuration
        """
        try:
            options = EncodingOptions()
            options.width = width
            options.height = height
            options.depth = depth
            options.framerate = framerate
            options.audio_codec = audio_codec
            options.audio_bitrate = audio_bitrate
            options.audio_frequency = audio_frequency
            options.video_codec = video_codec
            options.video_bitrate = video_bitrate
            options.key_frame_interval = key_frame_interval
            
            logger.debug(f"Created encoding options: {width}x{height}@{framerate}fps")
            return options
            
        except Exception as e:
            logger.error(f"Failed to create encoding options: {e}")
            raise
    
    # Utility Methods
    
    def _get_file_type_from_format(self, output_format: OutputFormat) -> int:
        """
        Get file type enum value from output format.
        
        Args:
            output_format: Output format
            
        Returns:
            File type enum value
        """
        from livekit.api import EncodedFileType
        
        format_mapping = {
            OutputFormat.MP4: EncodedFileType.MP4,
            OutputFormat.OGG: EncodedFileType.OGG,
            OutputFormat.WEBM: EncodedFileType.DEFAULT_FILETYPE,  # WebM not directly supported, use default
            OutputFormat.TS: EncodedFileType.DEFAULT_FILETYPE,   # TS not directly supported, use default
        }
        
        return format_mapping.get(output_format, EncodedFileType.DEFAULT_FILETYPE)
    
    async def get_egress_status(self, egress_id: str) -> Optional[EgressConfig]:
        """
        Get status of specific egress.
        
        Args:
            egress_id: Egress ID
            
        Returns:
            EgressConfig if found, None otherwise
        """
        return self.active_egress.get(egress_id)
    
    async def get_active_egress_count(self) -> int:
        """
        Get count of active egress instances.
        
        Returns:
            Number of active egress instances
        """
        active_count = sum(
            1 for config in self.active_egress.values()
            if config.status in [EgressStatus.EGRESS_STARTING, EgressStatus.EGRESS_ACTIVE]
        )
        
        self.metrics_collector.set_gauge("egress_active_count", active_count)
        return active_count
    
    async def cleanup_completed_egress(self) -> int:
        """
        Clean up completed egress instances from tracking.
        
        Returns:
            Number of cleaned up instances
        """
        completed_statuses = [
            EgressStatus.EGRESS_COMPLETE,
            EgressStatus.EGRESS_FAILED,
            EgressStatus.EGRESS_ABORTED
        ]
        
        to_remove = [
            egress_id for egress_id, config in self.active_egress.items()
            if config.status in completed_statuses
        ]
        
        for egress_id in to_remove:
            del self.active_egress[egress_id]
        
        logger.info(f"Cleaned up {len(to_remove)} completed egress instances")
        return len(to_remove)
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of the egress service.
        
        Returns:
            Health status information
        """
        active_count = sum(
            1 for config in self.active_egress.values()
            if config.status in [EgressStatus.EGRESS_STARTING, EgressStatus.EGRESS_ACTIVE]
        )
        
        completed_count = sum(
            1 for config in self.active_egress.values()
            if config.status == EgressStatus.EGRESS_COMPLETE
        )
        
        failed_count = sum(
            1 for config in self.active_egress.values()
            if config.status in [EgressStatus.EGRESS_FAILED, EgressStatus.EGRESS_ABORTED]
        )
        
        return {
            "service": "livekit_egress",
            "status": "healthy",
            "active_egress": active_count,
            "completed_egress": completed_count,
            "failed_egress": failed_count,
            "total_tracked": len(self.active_egress),
            "supported_formats": [format.value for format in OutputFormat],
            "supported_storage": [provider.value for provider in StorageProvider]
        }


# Convenience functions for common use cases

async def start_room_recording_to_s3(
    egress_service: LiveKitEgressService,
    room_name: str,
    filename: str,
    s3_config: S3Config,
    output_format: OutputFormat = OutputFormat.MP4,
    audio_only: bool = False,
    video_only: bool = False
) -> str:
    """
    Convenience function to start room recording to S3.
    
    Args:
        egress_service: Egress service instance
        room_name: Room to record
        filename: Output filename
        s3_config: S3 configuration
        output_format: Output format
        audio_only: Record audio only
        video_only: Record video only
        
    Returns:
        Egress ID
    """
    file_output = egress_service.create_s3_file_output(
        filename=filename,
        s3_config=s3_config,
        output_format=output_format
    )
    
    return await egress_service.start_room_composite_egress(
        room_name=room_name,
        audio_only=audio_only,
        video_only=video_only,
        file_outputs=[file_output]
    )


async def start_room_streaming_to_rtmp(
    egress_service: LiveKitEgressService,
    room_name: str,
    rtmp_urls: List[str],
    layout: Optional[str] = None
) -> str:
    """
    Convenience function to start room streaming to RTMP.
    
    Args:
        egress_service: Egress service instance
        room_name: Room to stream
        rtmp_urls: List of RTMP URLs
        layout: Custom layout
        
    Returns:
        Egress ID
    """
    stream_output = egress_service.create_rtmp_stream_output(urls=rtmp_urls)
    
    return await egress_service.start_room_composite_egress(
        room_name=room_name,
        layout=layout,
        stream_outputs=[stream_output]
    )


async def start_room_hls_streaming(
    egress_service: LiveKitEgressService,
    room_name: str,
    filename_prefix: str,
    playlist_name: str,
    s3_config: Optional[S3Config] = None,
    segment_duration: int = 6
) -> str:
    """
    Convenience function to start room HLS streaming.
    
    Args:
        egress_service: Egress service instance
        room_name: Room to stream
        filename_prefix: Prefix for segment files
        playlist_name: Playlist filename
        s3_config: S3 configuration for storage
        segment_duration: Segment duration in seconds
        
    Returns:
        Egress ID
    """
    segment_output = egress_service.create_hls_segment_output(
        filename_prefix=filename_prefix,
        playlist_name=playlist_name,
        segment_duration=segment_duration,
        s3_config=s3_config
    )
    
    return await egress_service.start_room_composite_egress(
        room_name=room_name,
        segment_outputs=[segment_output]
    )