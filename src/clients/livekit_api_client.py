"""
LiveKit API Client with Proper Twirp Endpoints

This module provides a comprehensive LiveKit API client that follows the official specification:
- Uses correct Twirp endpoints according to the API specification
- Implements proper Authorization: Bearer <token> headers
- Handles all HTTP error codes with appropriate error types
- Includes retry logic with exponential backoff
- Supports all RoomService API methods

Requirements addressed:
- 2.1: Correct Twirp endpoints usage
- 2.2: Proper room configuration parameters
- 2.3: Correct authorization headers
- 2.4: Comprehensive error handling
- 2.5: Retry logic with exponential backoff
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from uuid import uuid4
import random

import aiohttp
from livekit import api
from livekit.api import (
    Room, ParticipantInfo, LiveKitAPI
)

from src.auth.livekit_auth import LiveKitAuthManager, get_auth_manager
from src.config import get_settings


logger = logging.getLogger(__name__)


class LiveKitAPIError(Exception):
    """Base exception for LiveKit API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class LiveKitAuthenticationError(LiveKitAPIError):
    """Authentication related errors (401, 403)."""
    pass


class LiveKitNotFoundError(LiveKitAPIError):
    """Resource not found errors (404)."""
    pass


class LiveKitValidationError(LiveKitAPIError):
    """Validation errors (400)."""
    pass


class LiveKitRateLimitError(LiveKitAPIError):
    """Rate limiting errors (429)."""
    pass


class LiveKitServerError(LiveKitAPIError):
    """Server errors (5xx)."""
    pass


class LiveKitConnectionError(LiveKitAPIError):
    """Connection related errors."""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retryable_exceptions: List[type] = field(default_factory=lambda: [
        aiohttp.ClientConnectionError,
        aiohttp.ClientTimeout,
        asyncio.TimeoutError
    ])


@dataclass
class APIMetrics:
    """Metrics for API operations."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_attempts: int = 0
    average_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    
    def record_request(self, success: bool, latency_ms: float, retries: int = 0):
        """Record a request in metrics."""
        self.total_requests += 1
        self.retry_attempts += retries
        self.last_request_time = datetime.now(UTC)
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # Update average latency
        if self.total_requests == 1:
            self.average_latency_ms = latency_ms
        else:
            self.average_latency_ms = (
                (self.average_latency_ms * (self.total_requests - 1) + latency_ms) / 
                self.total_requests
            )


class LiveKitAPIClient:
    """
    LiveKit API Client with proper Twirp endpoints and comprehensive error handling.
    
    This client implements the official LiveKit API specification with:
    - Correct Twirp endpoint URLs
    - Proper Authorization: Bearer <token> headers
    - Comprehensive HTTP error handling
    - Retry logic with exponential backoff
    - Request/response logging and metrics
    """
    
    # Twirp endpoints according to LiveKit specification
    TWIRP_ENDPOINTS = {
        "create_room": "/twirp/livekit.RoomService/CreateRoom",
        "list_rooms": "/twirp/livekit.RoomService/ListRooms",
        "delete_room": "/twirp/livekit.RoomService/DeleteRoom",
        "list_participants": "/twirp/livekit.RoomService/ListParticipants",
        "get_participant": "/twirp/livekit.RoomService/GetParticipant",
        "remove_participant": "/twirp/livekit.RoomService/RemoveParticipant",
        "update_participant": "/twirp/livekit.RoomService/UpdateParticipant",
        "mute_published_track": "/twirp/livekit.RoomService/MutePublishedTrack",
        "update_subscriptions": "/twirp/livekit.RoomService/UpdateSubscriptions",
        "send_data": "/twirp/livekit.RoomService/SendData",
        "update_room_metadata": "/twirp/livekit.RoomService/UpdateRoomMetadata"
    }
    
    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        auth_manager: Optional[LiveKitAuthManager] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0
    ):
        """
        Initialize the LiveKit API client.
        
        Args:
            url: LiveKit server URL
            api_key: API key (defaults to settings)
            api_secret: API secret (defaults to settings)
            auth_manager: Authentication manager instance
            retry_config: Retry configuration
            timeout: Request timeout in seconds
        """
        self.settings = get_settings()
        self.url = url.rstrip('/')
        self.api_key = api_key or self.settings.livekit_api_key
        self.api_secret = api_secret or self.settings.livekit_api_secret
        self.timeout = timeout
        
        if not self.api_key or not self.api_secret or not self.api_key.strip() or not self.api_secret.strip():
            raise ValueError("LiveKit API key and secret are required")
        
        # Authentication manager
        self.auth_manager = auth_manager or get_auth_manager()
        
        # Retry configuration
        self.retry_config = retry_config or RetryConfig()
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Metrics
        self.metrics = APIMetrics()
        
        # Admin token for API operations
        self._admin_token: Optional[str] = None
        self._admin_token_expires: Optional[datetime] = None
        
        logger.info(f"LiveKit API Client initialized for {self.url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "LiveKit-Python-Client/1.0"
                }
            )
    
    async def _get_admin_token(self) -> str:
        """Get or refresh admin token for API operations."""
        now = datetime.now(UTC)
        
        # Check if we need a new token
        if (self._admin_token is None or 
            self._admin_token_expires is None or 
            now >= self._admin_token_expires - timedelta(minutes=5)):
            
            self._admin_token = self.auth_manager.create_admin_token(
                identity=f"api-client-{uuid4().hex[:8]}",
                ttl_minutes=60,
                auto_renew=False
            )
            self._admin_token_expires = now + timedelta(minutes=55)  # Refresh 5 minutes early
            
            logger.debug("Created new admin token for API operations")
        
        return self._admin_token
    
    def _map_http_error(self, status_code: int, response_text: str) -> LiveKitAPIError:
        """Map HTTP status codes to appropriate exception types."""
        error_message = f"HTTP {status_code}: {response_text}"
        
        if status_code == 400:
            return LiveKitValidationError(error_message, status_code)
        elif status_code == 401:
            return LiveKitAuthenticationError(f"Authentication failed: {response_text}", status_code)
        elif status_code == 403:
            return LiveKitAuthenticationError(f"Access forbidden: {response_text}", status_code)
        elif status_code == 404:
            return LiveKitNotFoundError(f"Resource not found: {response_text}", status_code)
        elif status_code == 429:
            return LiveKitRateLimitError(f"Rate limit exceeded: {response_text}", status_code)
        elif 500 <= status_code < 600:
            return LiveKitServerError(f"Server error: {response_text}", status_code)
        else:
            return LiveKitAPIError(error_message, status_code)
    
    async def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        custom_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and exponential backoff.
        
        Args:
            method: HTTP method
            endpoint: Twirp endpoint path
            data: Request data
            custom_token: Custom token to use instead of admin token
            
        Returns:
            Response data as dictionary
        """
        await self._ensure_session()
        
        url = f"{self.url}{endpoint}"
        token = custom_token or await self._get_admin_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        last_exception = None
        start_time = time.time()
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                request_start = time.time()
                
                async with self._session.request(
                    method,
                    url,
                    json=data,
                    headers=headers
                ) as response:
                    request_latency = (time.time() - request_start) * 1000
                    response_text = await response.text()
                    
                    # Log request details
                    logger.debug(
                        f"{method} {endpoint} - {response.status} ({request_latency:.1f}ms)",
                        extra={
                            "method": method,
                            "endpoint": endpoint,
                            "status_code": response.status,
                            "latency_ms": request_latency,
                            "attempt": attempt + 1
                        }
                    )
                    
                    if response.status == 200:
                        # Success
                        try:
                            result = json.loads(response_text) if response_text else {}
                            self.metrics.record_request(True, request_latency, attempt)
                            return result
                        except json.JSONDecodeError as e:
                            raise LiveKitAPIError(f"Invalid JSON response: {e}")
                    
                    # Handle HTTP errors
                    error = self._map_http_error(response.status, response_text)
                    
                    # Check if we should retry
                    if (response.status in self.retry_config.retryable_status_codes and 
                        attempt < self.retry_config.max_attempts - 1):
                        
                        delay = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Request failed with {response.status}, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{self.retry_config.max_attempts})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    
                    # No more retries or non-retryable error
                    self.metrics.record_request(False, request_latency, attempt)
                    raise error
                    
            except Exception as e:
                last_exception = e
                request_latency = (time.time() - request_start) * 1000 if 'request_start' in locals() else 0
                
                # Check if this is a retryable exception
                is_retryable = any(
                    isinstance(e, exc_type) 
                    for exc_type in self.retry_config.retryable_exceptions
                )
                
                if is_retryable and attempt < self.retry_config.max_attempts - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Request failed with {type(e).__name__}: {e}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_config.max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                # No more retries or non-retryable exception
                self.metrics.record_request(False, request_latency, attempt)
                
                if isinstance(e, LiveKitAPIError):
                    raise
                else:
                    raise LiveKitConnectionError(f"Connection error: {e}") from e
        
        # If we get here, all retries failed
        total_time = time.time() - start_time
        logger.error(
            f"All {self.retry_config.max_attempts} attempts failed for {method} {endpoint} "
            f"after {total_time:.1f}s"
        )
        
        if last_exception:
            if isinstance(last_exception, LiveKitAPIError):
                raise last_exception
            else:
                raise LiveKitConnectionError(f"All retries failed: {last_exception}") from last_exception
        else:
            raise LiveKitAPIError("All retries failed with unknown error")
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay
        )
        
        if self.retry_config.jitter:
            # Add random jitter (±25%)
            jitter = delay * 0.25 * (2 * random.random() - 1)
            delay += jitter
        
        return max(0, delay)
    
    # RoomService API methods according to specification
    
    async def create_room(
        self,
        name: str,
        empty_timeout: int = 300,
        departure_timeout: int = 20,
        max_participants: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        egress_template: Optional[Dict[str, Any]] = None
    ) -> Room:
        """
        Create a room using /twirp/livekit.RoomService/CreateRoom endpoint.
        
        Args:
            name: Room name (must be unique)
            empty_timeout: Timeout in seconds for empty room (default: 300)
            departure_timeout: Timeout in seconds after last participant leaves (default: 20)
            max_participants: Maximum number of participants (0 = unlimited)
            metadata: Room metadata as dictionary
            node_id: Specific node to create room on
            egress_template: Template for automatic egress
            
        Returns:
            Room object
        """
        request_data = {
            "name": name,
            "empty_timeout": empty_timeout,
            "departure_timeout": departure_timeout,
            "max_participants": max_participants
        }
        
        if metadata:
            request_data["metadata"] = json.dumps(metadata)
        
        if node_id:
            request_data["node_id"] = node_id
            
        if egress_template:
            request_data["egress"] = egress_template
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["create_room"],
                request_data
            )
            
            logger.info(f"Created room: {name}")
            return Room(**response)
            
        except Exception as e:
            logger.error(f"Failed to create room {name}: {e}")
            raise
    
    async def list_rooms(self, names: Optional[List[str]] = None) -> List[Room]:
        """
        List rooms using /twirp/livekit.RoomService/ListRooms endpoint.
        
        Args:
            names: Optional list of room names to filter by
            
        Returns:
            List of Room objects
        """
        request_data = {}
        if names:
            request_data["names"] = names
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["list_rooms"],
                request_data
            )
            
            rooms = [Room(**room_data) for room_data in response.get("rooms", [])]
            logger.debug(f"Listed {len(rooms)} rooms")
            return rooms
            
        except Exception as e:
            logger.error(f"Failed to list rooms: {e}")
            raise
    
    async def delete_room(self, room_name: str) -> None:
        """
        Delete a room using /twirp/livekit.RoomService/DeleteRoom endpoint.
        
        Args:
            room_name: Name of room to delete
        """
        request_data = {"room": room_name}
        
        try:
            await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["delete_room"],
                request_data
            )
            
            logger.info(f"Deleted room: {room_name}")
            
        except Exception as e:
            logger.error(f"Failed to delete room {room_name}: {e}")
            raise
    
    async def list_participants(self, room_name: str) -> List[ParticipantInfo]:
        """
        List participants using /twirp/livekit.RoomService/ListParticipants endpoint.
        
        Args:
            room_name: Room name
            
        Returns:
            List of ParticipantInfo objects
        """
        request_data = {"room": room_name}
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["list_participants"],
                request_data
            )
            
            participants = [
                ParticipantInfo(**participant_data) 
                for participant_data in response.get("participants", [])
            ]
            logger.debug(f"Listed {len(participants)} participants in room {room_name}")
            return participants
            
        except Exception as e:
            logger.error(f"Failed to list participants in room {room_name}: {e}")
            raise
    
    async def get_participant(self, room_name: str, identity: str) -> ParticipantInfo:
        """
        Get participant using /twirp/livekit.RoomService/GetParticipant endpoint.
        
        Args:
            room_name: Room name
            identity: Participant identity
            
        Returns:
            ParticipantInfo object
        """
        request_data = {
            "room": room_name,
            "identity": identity
        }
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["get_participant"],
                request_data
            )
            
            logger.debug(f"Retrieved participant {identity} from room {room_name}")
            return ParticipantInfo(**response)
            
        except Exception as e:
            logger.error(f"Failed to get participant {identity} in room {room_name}: {e}")
            raise
    
    async def remove_participant(self, room_name: str, identity: str) -> None:
        """
        Remove participant using /twirp/livekit.RoomService/RemoveParticipant endpoint.
        
        Args:
            room_name: Room name
            identity: Participant identity
        """
        request_data = {
            "room": room_name,
            "identity": identity
        }
        
        try:
            await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["remove_participant"],
                request_data
            )
            
            logger.info(f"Removed participant {identity} from room {room_name}")
            
        except Exception as e:
            logger.error(f"Failed to remove participant {identity} from room {room_name}: {e}")
            raise
    
    async def update_participant(
        self,
        room_name: str,
        identity: str,
        metadata: Optional[str] = None,
        permission: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None
    ) -> ParticipantInfo:
        """
        Update participant using /twirp/livekit.RoomService/UpdateParticipant endpoint.
        
        Args:
            room_name: Room name
            identity: Participant identity
            metadata: New metadata
            permission: New permissions
            name: New display name
            
        Returns:
            Updated ParticipantInfo object
        """
        request_data = {
            "room": room_name,
            "identity": identity
        }
        
        if metadata is not None:
            request_data["metadata"] = metadata
        if permission is not None:
            request_data["permission"] = permission
        if name is not None:
            request_data["name"] = name
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["update_participant"],
                request_data
            )
            
            logger.info(f"Updated participant {identity} in room {room_name}")
            return ParticipantInfo(**response)
            
        except Exception as e:
            logger.error(f"Failed to update participant {identity} in room {room_name}: {e}")
            raise
    
    async def mute_published_track(
        self,
        room_name: str,
        identity: str,
        track_sid: str,
        muted: bool
    ) -> None:
        """
        Mute/unmute track using /twirp/livekit.RoomService/MutePublishedTrack endpoint.
        
        Args:
            room_name: Room name
            identity: Participant identity
            track_sid: Track SID
            muted: Whether to mute the track
        """
        request_data = {
            "room": room_name,
            "identity": identity,
            "track_sid": track_sid,
            "muted": muted
        }
        
        try:
            await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["mute_published_track"],
                request_data
            )
            
            action = "Muted" if muted else "Unmuted"
            logger.info(f"{action} track {track_sid} for participant {identity} in room {room_name}")
            
        except Exception as e:
            logger.error(f"Failed to mute track {track_sid} for participant {identity}: {e}")
            raise
    
    async def update_subscriptions(
        self,
        room_name: str,
        identity: str,
        track_sids: List[str],
        subscribe: bool,
        participant_tracks: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Update subscriptions using /twirp/livekit.RoomService/UpdateSubscriptions endpoint.
        
        Args:
            room_name: Room name
            identity: Participant identity
            track_sids: List of track SIDs
            subscribe: Whether to subscribe or unsubscribe
            participant_tracks: Participant track information
        """
        request_data = {
            "room": room_name,
            "identity": identity,
            "track_sids": track_sids,
            "subscribe": subscribe
        }
        
        if participant_tracks:
            request_data["participant_tracks"] = participant_tracks
        
        try:
            await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["update_subscriptions"],
                request_data
            )
            
            action = "Subscribed to" if subscribe else "Unsubscribed from"
            logger.info(f"{action} {len(track_sids)} tracks for participant {identity}")
            
        except Exception as e:
            logger.error(f"Failed to update subscriptions for participant {identity}: {e}")
            raise
    
    async def send_data(
        self,
        room_name: str,
        data: bytes,
        kind: int = 0,  # DataPacket_Kind
        destination_sids: Optional[List[str]] = None,
        topic: Optional[str] = None
    ) -> None:
        """
        Send data using /twirp/livekit.RoomService/SendData endpoint.
        
        Args:
            room_name: Room name
            data: Data to send
            kind: Data packet kind (0=LOSSY, 1=RELIABLE)
            destination_sids: Destination participant SIDs
            topic: Data topic
        """
        import base64
        
        request_data = {
            "room": room_name,
            "data": base64.b64encode(data).decode('utf-8'),
            "kind": kind
        }
        
        if destination_sids:
            request_data["destination_sids"] = destination_sids
        if topic:
            request_data["topic"] = topic
        
        try:
            await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["send_data"],
                request_data
            )
            
            logger.debug(f"Sent {len(data)} bytes of data to room {room_name}")
            
        except Exception as e:
            logger.error(f"Failed to send data to room {room_name}: {e}")
            raise
    
    async def update_room_metadata(self, room_name: str, metadata: str) -> Room:
        """
        Update room metadata using /twirp/livekit.RoomService/UpdateRoomMetadata endpoint.
        
        Args:
            room_name: Room name
            metadata: New metadata
            
        Returns:
            Updated Room object
        """
        request_data = {
            "room": room_name,
            "metadata": metadata
        }
        
        try:
            response = await self._make_request_with_retry(
                "POST",
                self.TWIRP_ENDPOINTS["update_room_metadata"],
                request_data
            )
            
            logger.info(f"Updated metadata for room {room_name}")
            return Room(**response)
            
        except Exception as e:
            logger.error(f"Failed to update metadata for room {room_name}: {e}")
            raise
    
    # Utility methods
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check by listing rooms.
        
        Returns:
            Health check results
        """
        try:
            start_time = time.time()
            rooms = await self.list_rooms()
            latency = (time.time() - start_time) * 1000
            
            return {
                "healthy": True,
                "latency_ms": round(latency, 2),
                "rooms_count": len(rooms),
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get API client metrics."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": (
                self.metrics.successful_requests / max(1, self.metrics.total_requests)
            ),
            "retry_attempts": self.metrics.retry_attempts,
            "average_latency_ms": round(self.metrics.average_latency_ms, 2),
            "last_request_time": (
                self.metrics.last_request_time.isoformat() 
                if self.metrics.last_request_time else None
            )
        }
    
    def get_egress_client(self):
        """Get Egress API client."""
        from livekit.api import EgressClient
        return EgressClient(
            url=self.url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
    
    def get_ingress_client(self):
        """Get Ingress API client."""
        from livekit.api import IngressClient
        return IngressClient(
            url=self.url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
    
    def get_sip_client(self):
        """Get SIP API client."""
        from livekit.api import SIPClient
        return SIPClient(
            url=self.url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed HTTP session")


# Global client instance
_api_client: Optional[LiveKitAPIClient] = None


def get_api_client() -> LiveKitAPIClient:
    """
    Get the global API client instance.
    
    Returns:
        LiveKitAPIClient instance
    """
    global _api_client
    if _api_client is None:
        settings = get_settings()
        _api_client = LiveKitAPIClient(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret
        )
    return _api_client


async def shutdown_api_client():
    """Shutdown the global API client."""
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None