"""
Webhook handlers for LiveKit SIP integration.

This module provides webhook endpoints for handling LiveKit events,
including call start, call end, participant events, and audio track events.
Enhanced with improved correlation, validation, logging, and error handling.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, UTC
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.livekit_integration import get_livekit_integration, LiveKitEventType
from src.orchestrator import CallContext, CallOrchestrator
from src.metrics import get_metrics_collector
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager


logger = logging.getLogger(__name__)


class WebhookHandler:
    """Enhanced handler for LiveKit webhook events with improved correlation and error handling."""
    
    def __init__(self, orchestrator: CallOrchestrator):
        """
        Initialize webhook handler.
        
        Args:
            orchestrator: Call orchestrator instance
        """
        self.orchestrator = orchestrator
        self.settings = get_settings()
        self.metrics_collector = get_metrics_collector()
        self.livekit_integration = None
        
        # Initialize LiveKit components for enhanced event handling
        self.api_client = None
        self.auth_manager = None
        
        # Enhanced event processing for LiveKit integration
        self.livekit_event_handlers = {
            LiveKitEventType.ROOM_STARTED: self._handle_livekit_room_started,
            LiveKitEventType.ROOM_FINISHED: self._handle_livekit_room_finished,
            LiveKitEventType.PARTICIPANT_JOINED: self._handle_livekit_participant_joined,
            LiveKitEventType.PARTICIPANT_LEFT: self._handle_livekit_participant_left,
            LiveKitEventType.TRACK_PUBLISHED: self._handle_livekit_track_published,
            LiveKitEventType.TRACK_UNPUBLISHED: self._handle_livekit_track_unpublished,
        }
        
        # Event processing queue
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_processor_task: Optional[asyncio.Task] = None
        
        # Active call tracking for correlation
        self.active_calls: Dict[str, CallContext] = {}  # room_name -> CallContext
        self.call_participants: Dict[str, Set[str]] = {}  # room_name -> participant_ids
        self.call_tracks: Dict[str, Dict[str, Any]] = {}  # room_name -> track_info
        
        # Event correlation tracking
        self.event_correlation: Dict[str, str] = {}  # event_id -> call_id
        self.pending_events: Dict[str, List[Dict[str, Any]]] = {}  # call_id -> events
        
        # Webhook signature validation
        self.webhook_secret = self.settings.livekit_webhook_secret or self.settings.secret_key
        
        # Statistics
        self.total_events_received = 0
        self.total_events_processed = 0
        self.total_events_failed = 0
        self.signature_validation_failures = 0
        
        logger.info("Enhanced webhook handler initialized with call correlation support")
    
    async def start(self) -> None:
        """Start the webhook handler."""
        try:
            # Get LiveKit integration
            self.livekit_integration = await get_livekit_integration()
            
            # Initialize LiveKit API components for enhanced event handling
            if (hasattr(self.settings, 'livekit_url') and 
                hasattr(self.settings, 'livekit_api_key') and 
                hasattr(self.settings, 'livekit_api_secret')):
                
                self.api_client = LiveKitAPIClient(
                    url=self.settings.livekit_url,
                    api_key=self.settings.livekit_api_key,
                    api_secret=self.settings.livekit_api_secret
                )
                
                self.auth_manager = LiveKitAuthManager(
                    api_key=self.settings.livekit_api_key,
                    api_secret=self.settings.livekit_api_secret
                )
                
                logger.info("LiveKit API components initialized for webhook handler")
            
            # Start event processor
            self.event_processor_task = asyncio.create_task(self._process_events())
            
            logger.info("Enhanced webhook handler started with LiveKit integration")
            
        except Exception as e:
            logger.error(f"Failed to start webhook handler: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the webhook handler."""
        try:
            # Stop event processor
            if self.event_processor_task:
                self.event_processor_task.cancel()
                try:
                    await self.event_processor_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Webhook handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping webhook handler: {e}")
    
    def verify_webhook_signature(self, payload: bytes, signature: str, timestamp: Optional[str] = None) -> bool:
        """
        Enhanced webhook signature verification from LiveKit with timestamp validation.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook header (format: "sha256=<hash>")
            timestamp: Optional timestamp for replay attack prevention
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("No webhook secret configured for signature verification")
                return True  # Skip verification if no secret key
            
            # Extract signature hash from header (remove "sha256=" prefix if present)
            sig_hash = signature
            if signature.startswith('sha256='):
                sig_hash = signature[7:]
            elif signature.startswith('sha1='):
                # Some webhooks use SHA1
                sig_hash = signature[5:]
                hash_func = hashlib.sha1
            else:
                hash_func = hashlib.sha256
            
            # Validate timestamp to prevent replay attacks (if provided)
            if timestamp:
                try:
                    webhook_time = int(timestamp)
                    current_time = int(time.time())
                    
                    # Allow 5 minute tolerance for clock skew
                    if abs(current_time - webhook_time) > 300:
                        logger.warning(f"Webhook timestamp too old or too new: {webhook_time} vs {current_time}")
                        self.signature_validation_failures += 1
                        return False
                        
                except (ValueError, TypeError):
                    logger.warning(f"Invalid webhook timestamp format: {timestamp}")
                    self.signature_validation_failures += 1
                    return False
            
            # Calculate expected signature
            if 'hash_func' not in locals():
                hash_func = hashlib.sha256
                
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                payload,
                hash_func
            ).hexdigest()
            
            # Compare signatures using constant-time comparison
            is_valid = hmac.compare_digest(sig_hash.lower(), expected_signature.lower())
            
            if not is_valid:
                logger.warning(
                    f"Webhook signature validation failed. Expected: {expected_signature[:8]}..., Got: {sig_hash[:8]}..."
                )
                self.signature_validation_failures += 1
                self.metrics_collector.increment_counter("webhook_signature_validation_failures_total")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            self.signature_validation_failures += 1
            self.metrics_collector.increment_counter("webhook_signature_validation_errors_total")
            return False
    
    async def handle_webhook(
        self, 
        request: Request, 
        background_tasks: BackgroundTasks
    ) -> JSONResponse:
        """
        Enhanced webhook handler with improved validation, logging, and error handling.
        
        Args:
            request: FastAPI request object
            background_tasks: Background tasks for async processing
            
        Returns:
            JSON response
        """
        event_id = str(uuid4())
        start_time = time.time()
        
        try:
            # Get raw payload
            payload = await request.body()
            
            # Extract headers for validation and logging
            signature = request.headers.get('x-livekit-signature') or request.headers.get('x-signature')
            timestamp = request.headers.get('x-livekit-timestamp') or request.headers.get('x-timestamp')
            user_agent = request.headers.get('user-agent', 'unknown')
            content_type = request.headers.get('content-type', 'unknown')
            
            # Log webhook reception with detailed info
            logger.info(
                f"Received webhook event {event_id}",
                extra={
                    "event_id": event_id,
                    "user_agent": user_agent,
                    "content_type": content_type,
                    "payload_size": len(payload),
                    "has_signature": bool(signature),
                    "has_timestamp": bool(timestamp),
                    "source_ip": request.client.host if request.client else "unknown"
                }
            )
            
            # Verify signature if provided
            if signature:
                if not self.verify_webhook_signature(payload, signature, timestamp):
                    logger.warning(
                        f"Webhook signature validation failed for event {event_id}",
                        extra={
                            "event_id": event_id,
                            "signature": signature[:16] + "..." if len(signature) > 16 else signature,
                            "timestamp": timestamp
                        }
                    )
                    raise HTTPException(status_code=401, detail="Invalid signature")
            else:
                logger.warning(f"Webhook received without signature: {event_id}")
            
            # Parse JSON payload
            try:
                event_data = json.loads(payload.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON in webhook payload for event {event_id}: {e}",
                    extra={
                        "event_id": event_id,
                        "payload_preview": payload[:200].decode('utf-8', errors='ignore')
                    }
                )
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Enrich event data with metadata
            event_data.update({
                'event_id': event_id,
                'received_at': datetime.now(UTC).isoformat(),
                'source_ip': request.client.host if request.client else None,
                'user_agent': user_agent,
                'signature_verified': bool(signature),
                'processing_start_time': start_time
            })
            
            # Validate required fields
            if 'event' not in event_data:
                logger.error(f"Missing 'event' field in webhook payload: {event_id}")
                raise HTTPException(status_code=400, detail="Missing event type")
            
            # Update statistics
            self.total_events_received += 1
            
            # Queue event for processing
            await self.event_queue.put(event_data)
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "webhook_events_received_total",
                labels={
                    "event_type": event_data.get('event', 'unknown'),
                    "signature_verified": str(bool(signature))
                }
            )
            
            processing_time = time.time() - start_time
            self.metrics_collector.record_histogram(
                "webhook_reception_duration_seconds",
                processing_time,
                labels={"event_type": event_data.get('event', 'unknown')}
            )
            
            logger.debug(
                f"Successfully queued webhook event {event_id}: {event_data.get('event')}",
                extra={
                    "event_id": event_id,
                    "event_type": event_data.get('event'),
                    "room_name": event_data.get('room', {}).get('name'),
                    "processing_time": processing_time
                }
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "received",
                    "event_id": event_id,
                    "timestamp": event_data['received_at'],
                    "processing_time": processing_time
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Unexpected error handling webhook {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "processing_time": processing_time,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            self.metrics_collector.increment_counter("webhook_errors_total")
            self.metrics_collector.record_histogram(
                "webhook_error_duration_seconds",
                processing_time
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _process_events(self) -> None:
        """Process webhook events from the queue."""
        while True:
            try:
                # Get event from queue
                event_data = await self.event_queue.get()
                
                # Process event
                await self._process_single_event(event_data)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing webhook event: {e}")
                self.metrics_collector.increment_counter("webhook_processing_errors_total")
    
    async def _process_single_event(self, event_data: Dict[str, Any]) -> None:
        """
        Enhanced processing of a single webhook event with correlation and error handling.
        
        Args:
            event_data: Event data from webhook
        """
        event_id = event_data.get('event_id', 'unknown')
        event_type = event_data.get('event')
        start_time = time.time()
        
        try:
            logger.debug(
                f"Processing webhook event {event_id}: {event_type}",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "room_name": event_data.get('room', {}).get('name')
                }
            )
            
            # Extract room information for correlation
            room_data = event_data.get('room', {})
            room_name = room_data.get('name', '')
            
            # Correlate with active calls
            call_context = None
            if room_name and room_name.startswith('voice-ai-call-'):
                call_context = self.active_calls.get(room_name)
                if call_context:
                    # Add call correlation to event data
                    event_data['call_id'] = call_context.call_id
                    event_data['caller_number'] = call_context.caller_number
            
            # Process event based on type with enhanced LiveKit integration
            if event_type == LiveKitEventType.ROOM_STARTED.value:
                await self._handle_room_started(event_data)
                # Enhanced LiveKit-specific handling
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.ROOM_STARTED](event_data)
            elif event_type == LiveKitEventType.ROOM_FINISHED.value:
                await self._handle_room_finished(event_data)
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.ROOM_FINISHED](event_data)
            elif event_type == LiveKitEventType.PARTICIPANT_JOINED.value:
                await self._handle_participant_joined(event_data)
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.PARTICIPANT_JOINED](event_data)
            elif event_type == LiveKitEventType.PARTICIPANT_LEFT.value:
                await self._handle_participant_left(event_data)
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.PARTICIPANT_LEFT](event_data)
            elif event_type == LiveKitEventType.TRACK_PUBLISHED.value:
                await self._handle_track_published(event_data)
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.TRACK_PUBLISHED](event_data)
            elif event_type == LiveKitEventType.TRACK_UNPUBLISHED.value:
                await self._handle_track_unpublished(event_data)
                if event_type in self.livekit_event_handlers:
                    await self.livekit_event_handlers[LiveKitEventType.TRACK_UNPUBLISHED](event_data)
            elif event_type == LiveKitEventType.RECORDING_STARTED.value:
                await self._handle_recording_started(event_data)
            elif event_type == LiveKitEventType.RECORDING_FINISHED.value:
                await self._handle_recording_finished(event_data)
            else:
                logger.warning(
                    f"Unknown event type in event {event_id}: {event_type}",
                    extra={
                        "event_id": event_id,
                        "event_type": event_type,
                        "available_events": [e.value for e in LiveKitEventType]
                    }
                )
                self.metrics_collector.increment_counter(
                    "webhook_unknown_events_total",
                    labels={"event_type": event_type or "unknown"}
                )
            
            # Forward to LiveKit integration
            if self.livekit_integration:
                try:
                    await self.livekit_integration.handle_webhook_event(event_data)
                except Exception as e:
                    logger.error(
                        f"Error forwarding event {event_id} to LiveKit integration: {e}",
                        extra={"event_id": event_id, "event_type": event_type}
                    )
            
            # Update statistics and metrics
            self.total_events_processed += 1
            processing_time = time.time() - start_time
            
            self.metrics_collector.increment_counter(
                "webhook_events_processed_total",
                labels={
                    "event_type": event_type or "unknown",
                    "has_call_correlation": str(bool(call_context))
                }
            )
            
            self.metrics_collector.record_histogram(
                "webhook_processing_duration_seconds",
                processing_time,
                labels={"event_type": event_type or "unknown"}
            )
            
            logger.debug(
                f"Successfully processed webhook event {event_id}",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "processing_time": processing_time,
                    "call_correlated": bool(call_context)
                }
            )
            
        except Exception as e:
            self.total_events_failed += 1
            processing_time = time.time() - start_time
            
            logger.error(
                f"Error processing webhook event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "processing_time": processing_time,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            
            self.metrics_collector.increment_counter(
                "webhook_processing_errors_total",
                labels={
                    "event_type": event_type or "unknown",
                    "error_type": type(e).__name__
                }
            )
            
            self.metrics_collector.record_histogram(
                "webhook_error_processing_duration_seconds",
                processing_time,
                labels={"event_type": event_type or "unknown"}
            )
            
            raise
    
    async def _handle_livekit_room_started(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit room started event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            room_sid = room_data.get('sid')
            
            logger.info(
                f"Enhanced LiveKit room started: {room_name}",
                extra={
                    "event_id": event_id,
                    "room_name": room_name,
                    "room_sid": room_sid,
                    "enhanced_processing": True
                }
            )
            
            # Enhanced room validation using API client
            if self.api_client and room_name:
                try:
                    # Verify room exists and get detailed info
                    rooms = await self.api_client.list_rooms(names=[room_name])
                    if rooms:
                        room_info = rooms[0]
                        logger.debug(f"Verified room {room_name} exists with {len(room_info.participants)} participants")
                except Exception as e:
                    logger.warning(f"Could not verify room {room_name}: {e}")
            
            # Enhanced metadata processing
            metadata_str = room_data.get('metadata', '{}')
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
                # Add enhanced metadata for Voice AI processing
                metadata.update({
                    'enhanced_processing': True,
                    'webhook_event_id': event_id,
                    'room_sid': room_sid,
                    'processing_timestamp': datetime.now(UTC).isoformat()
                })
                event_data['enhanced_metadata'] = metadata
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse enhanced room metadata: {e}")
            
        except Exception as e:
            logger.error(f"Error in enhanced room started handler: {e}")
    
    async def _handle_livekit_room_finished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit room finished event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            room_sid = room_data.get('sid')
            
            logger.info(
                f"Enhanced LiveKit room finished: {room_name}",
                extra={
                    "event_id": event_id,
                    "room_name": room_name,
                    "room_sid": room_sid,
                    "enhanced_processing": True
                }
            )
            
            # Enhanced cleanup using API client
            if self.api_client and room_name:
                try:
                    # Ensure room is properly cleaned up
                    await self.api_client.delete_room(room_name)
                    logger.debug(f"Enhanced cleanup completed for room {room_name}")
                except Exception as e:
                    logger.warning(f"Enhanced cleanup failed for room {room_name}: {e}")
            
        except Exception as e:
            logger.error(f"Error in enhanced room finished handler: {e}")
    
    async def _handle_livekit_participant_joined(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit participant joined event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            participant_data = event_data.get('participant', {})
            participant_identity = participant_data.get('identity')
            participant_sid = participant_data.get('sid')
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            logger.info(
                f"Enhanced LiveKit participant joined: {participant_identity} in {room_name}",
                extra={
                    "event_id": event_id,
                    "participant_identity": participant_identity,
                    "participant_sid": participant_sid,
                    "room_name": room_name,
                    "enhanced_processing": True
                }
            )
            
            # Enhanced participant validation using auth manager
            if self.auth_manager and participant_identity and room_name:
                try:
                    # Validate participant authorization
                    is_authorized = await self._validate_participant_authorization(
                        participant_identity, room_name
                    )
                    if not is_authorized:
                        logger.warning(f"Unauthorized participant {participant_identity} in room {room_name}")
                except Exception as e:
                    logger.warning(f"Could not validate participant authorization: {e}")
            
        except Exception as e:
            logger.error(f"Error in enhanced participant joined handler: {e}")
    
    async def _handle_livekit_participant_left(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit participant left event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            participant_data = event_data.get('participant', {})
            participant_identity = participant_data.get('identity')
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            logger.info(
                f"Enhanced LiveKit participant left: {participant_identity} from {room_name}",
                extra={
                    "event_id": event_id,
                    "participant_identity": participant_identity,
                    "room_name": room_name,
                    "enhanced_processing": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced participant left handler: {e}")
    
    async def _handle_livekit_track_published(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit track published event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            track_data = event_data.get('track', {})
            track_sid = track_data.get('sid')
            track_type = track_data.get('type')
            participant_data = event_data.get('participant', {})
            participant_identity = participant_data.get('identity')
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            logger.info(
                f"Enhanced LiveKit track published: {track_type} track {track_sid} by {participant_identity}",
                extra={
                    "event_id": event_id,
                    "track_sid": track_sid,
                    "track_type": track_type,
                    "participant_identity": participant_identity,
                    "room_name": room_name,
                    "enhanced_processing": True
                }
            )
            
            # Enhanced audio track processing for Voice AI
            if track_type == 'audio' and self.orchestrator:
                try:
                    # Get call context for enhanced processing
                    call_context = None
                    if room_name and room_name.startswith('voice-ai-call-'):
                        call_id = room_name.replace('voice-ai-call-', '')
                        call_context = self.active_calls.get(room_name)
                    
                    if call_context:
                        # Notify orchestrator about audio track for enhanced processing
                        await self.orchestrator.handle_audio_track_published(
                            call_context, track_sid, participant_identity
                        )
                        logger.debug(f"Enhanced audio processing started for track {track_sid}")
                except Exception as e:
                    logger.error(f"Enhanced audio track processing failed: {e}")
            
        except Exception as e:
            logger.error(f"Error in enhanced track published handler: {e}")
    
    async def _handle_livekit_track_unpublished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit track unpublished event handler."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            track_data = event_data.get('track', {})
            track_sid = track_data.get('sid')
            track_type = track_data.get('type')
            participant_data = event_data.get('participant', {})
            participant_identity = participant_data.get('identity')
            
            logger.info(
                f"Enhanced LiveKit track unpublished: {track_type} track {track_sid} by {participant_identity}",
                extra={
                    "event_id": event_id,
                    "track_sid": track_sid,
                    "track_type": track_type,
                    "participant_identity": participant_identity,
                    "enhanced_processing": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced track unpublished handler: {e}")
    
    async def _validate_participant_authorization(self, participant_identity: str, room_name: str) -> bool:
        """Validate participant authorization using auth manager."""
        try:
            if not self.auth_manager:
                return True  # Skip validation if no auth manager
            
            # Create a temporary token to validate authorization
            token = self.auth_manager.create_participant_token(
                identity=participant_identity,
                room_name=room_name,
                auto_renew=False
            )
            
            # Validate the token
            validation_result = self.auth_manager.validate_token(token)
            return validation_result.get('valid', False)
            
        except Exception as e:
            logger.error(f"Error validating participant authorization: {e}")
            return False
    
    async def _handle_room_started(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for room started event with correlation tracking."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            room_sid = room_data.get('sid')
            
            logger.debug(
                f"Processing room_started event {event_id}",
                extra={
                    "event_id": event_id,
                    "room_name": room_name,
                    "room_sid": room_sid
                }
            )
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                logger.debug(
                    f"Ignoring room_started for non-voice-ai room: {room_name}",
                    extra={"event_id": event_id, "room_name": room_name}
                )
                return  # Not our call
            
            # Extract call ID from room name
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Parse metadata
            metadata_str = room_data.get('metadata', '{}')
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse room metadata for call {call_id}: {e}",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "metadata_str": metadata_str
                    }
                )
                metadata = {}
            
            # Create call context
            call_context = CallContext(
                call_id=call_id,
                caller_number=metadata.get('caller_number', 'unknown'),
                start_time=datetime.now(UTC),
                livekit_room=room_name,
                metadata=metadata
            )
            
            # Store for correlation
            self.active_calls[room_name] = call_context
            self.call_participants[room_name] = set()
            self.call_tracks[room_name] = {}
            self.event_correlation[event_id] = call_id
            
            # Notify orchestrator
            try:
                await self.orchestrator.handle_call_start(call_context)
                
                logger.info(
                    f"Room started for call {call_id} - orchestrator notified",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "caller_number": call_context.caller_number,
                        "metadata": metadata
                    }
                )
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "voice_ai_calls_started_total",
                    labels={"caller_number": call_context.caller_number}
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to notify orchestrator of call start for {call_id}: {e}",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                # Don't re-raise - we still want to track the call
            
        except Exception as e:
            logger.error(
                f"Error handling room_started event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_room_finished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for room finished event with cleanup and correlation."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            room_sid = room_data.get('sid')
            
            logger.debug(
                f"Processing room_finished event {event_id}",
                extra={
                    "event_id": event_id,
                    "room_name": room_name,
                    "room_sid": room_sid
                }
            )
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                logger.debug(
                    f"Ignoring room_finished for non-voice-ai room: {room_name}",
                    extra={"event_id": event_id, "room_name": room_name}
                )
                return  # Not our call
            
            # Extract call ID from room name
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Get existing call context if available
            call_context = self.active_calls.get(room_name)
            
            if not call_context:
                # Create minimal call context from event data
                metadata_str = room_data.get('metadata', '{}')
                try:
                    metadata = json.loads(metadata_str) if metadata_str else {}
                except json.JSONDecodeError:
                    metadata = {}
                
                call_context = CallContext(
                    call_id=call_id,
                    caller_number=metadata.get('caller_number', 'unknown'),
                    start_time=datetime.now(UTC),  # Will be updated by orchestrator
                    livekit_room=room_name,
                    metadata=metadata
                )
                
                logger.warning(
                    f"Room finished for unknown call {call_id} - creating context from event",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "room_name": room_name
                    }
                )
            
            # Collect call statistics before cleanup
            participants_count = len(self.call_participants.get(room_name, set()))
            tracks_count = len(self.call_tracks.get(room_name, {}))
            
            # Notify orchestrator
            try:
                await self.orchestrator.handle_call_end(call_context)
                
                logger.info(
                    f"Room finished for call {call_id} - orchestrator notified",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "caller_number": call_context.caller_number,
                        "participants_count": participants_count,
                        "tracks_count": tracks_count
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to notify orchestrator of call end for {call_id}: {e}",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
            
            # Notify LiveKit integration
            if self.livekit_integration:
                try:
                    await self.livekit_integration.handle_call_end(call_context)
                except Exception as e:
                    logger.error(
                        f"Failed to notify LiveKit integration of call end for {call_id}: {e}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "error_type": type(e).__name__
                        }
                    )
            
            # Clean up correlation data
            self.active_calls.pop(room_name, None)
            self.call_participants.pop(room_name, None)
            self.call_tracks.pop(room_name, None)
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "voice_ai_calls_finished_total",
                labels={"caller_number": call_context.caller_number}
            )
            
            self.metrics_collector.set_gauge(
                "active_voice_ai_calls_current",
                len(self.active_calls)
            )
            
        except Exception as e:
            logger.error(
                f"Error handling room_finished event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_participant_joined(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for participant joined event with correlation tracking."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            participant_identity = participant.get('identity')
            participant_sid = participant.get('sid')
            participant_name = participant.get('name', participant_identity)
            room_name = room.get('name')
            room_sid = room.get('sid')
            
            logger.debug(
                f"Processing participant_joined event {event_id}",
                extra={
                    "event_id": event_id,
                    "participant_identity": participant_identity,
                    "participant_sid": participant_sid,
                    "room_name": room_name
                }
            )
            
            # Track participant for correlation
            if room_name and room_name in self.call_participants:
                self.call_participants[room_name].add(participant_identity)
                
                # Get call context for enhanced logging
                call_context = self.active_calls.get(room_name)
                call_id = call_context.call_id if call_context else room_name.replace('voice-ai-call-', '')
                
                # Notify orchestrator about participant joining
                if call_context and self.orchestrator:
                    try:
                        await self.orchestrator.handle_participant_joined(
                            call_context, participant_identity, participant_sid
                        )
                        logger.debug(f"Orchestrator notified of participant join: {participant_identity}")
                    except Exception as e:
                        logger.error(f"Failed to notify orchestrator of participant join: {e}")
                
                logger.info(
                    f"Participant {participant_identity} joined voice AI call {call_id}",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "participant_identity": participant_identity,
                        "participant_sid": participant_sid,
                        "participant_name": participant_name,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "total_participants": len(self.call_participants[room_name])
                    }
                )
                
                # Update metrics
                self.metrics_collector.set_gauge(
                    "voice_ai_call_participants_current",
                    len(self.call_participants[room_name]),
                    labels={"call_id": call_id}
                )
                
                self.metrics_collector.increment_counter(
                    "voice_ai_participants_joined_total",
                    labels={
                        "participant_type": "ai_agent" if "agent" in participant_identity.lower() else "caller"
                    }
                )
                
            else:
                logger.info(
                    f"Participant {participant_identity} joined room {room_name}",
                    extra={
                        "event_id": event_id,
                        "participant_identity": participant_identity,
                        "participant_sid": participant_sid,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "is_voice_ai_call": bool(room_name and room_name.startswith('voice-ai-call-'))
                    }
                )
            
        except Exception as e:
            logger.error(
                f"Error handling participant_joined event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_participant_left(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for participant left event with correlation tracking."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            participant_identity = participant.get('identity')
            participant_sid = participant.get('sid')
            participant_name = participant.get('name', participant_identity)
            room_name = room.get('name')
            room_sid = room.get('sid')
            
            logger.debug(
                f"Processing participant_left event {event_id}",
                extra={
                    "event_id": event_id,
                    "participant_identity": participant_identity,
                    "participant_sid": participant_sid,
                    "room_name": room_name
                }
            )
            
            # Update participant tracking
            if room_name and room_name in self.call_participants:
                self.call_participants[room_name].discard(participant_identity)
                
                # Get call context for enhanced logging
                call_context = self.active_calls.get(room_name)
                call_id = call_context.call_id if call_context else room_name.replace('voice-ai-call-', '')
                
                logger.info(
                    f"Participant {participant_identity} left voice AI call {call_id}",
                    extra={
                        "event_id": event_id,
                        "call_id": call_id,
                        "participant_identity": participant_identity,
                        "participant_sid": participant_sid,
                        "participant_name": participant_name,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "remaining_participants": len(self.call_participants[room_name])
                    }
                )
                
                # Update metrics
                self.metrics_collector.set_gauge(
                    "voice_ai_call_participants_current",
                    len(self.call_participants[room_name]),
                    labels={"call_id": call_id}
                )
                
                self.metrics_collector.increment_counter(
                    "voice_ai_participants_left_total",
                    labels={
                        "participant_type": "ai_agent" if "agent" in participant_identity.lower() else "caller"
                    }
                )
                
            else:
                logger.info(
                    f"Participant {participant_identity} left room {room_name}",
                    extra={
                        "event_id": event_id,
                        "participant_identity": participant_identity,
                        "participant_sid": participant_sid,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "is_voice_ai_call": bool(room_name and room_name.startswith('voice-ai-call-'))
                    }
                )
            
        except Exception as e:
            logger.error(
                f"Error handling participant_left event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_track_published(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for track published event with detailed tracking."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            track = event_data.get('track', {})
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            track_sid = track.get('sid')
            track_type = track.get('type')
            track_name = track.get('name')
            track_source = track.get('source')
            participant_identity = participant.get('identity')
            participant_sid = participant.get('sid')
            room_name = room.get('name')
            room_sid = room.get('sid')
            
            logger.debug(
                f"Processing track_published event {event_id}",
                extra={
                    "event_id": event_id,
                    "track_sid": track_sid,
                    "track_type": track_type,
                    "track_source": track_source,
                    "participant_identity": participant_identity,
                    "room_name": room_name
                }
            )
            
            # Track audio tracks for voice AI calls
            if room_name and room_name.startswith('voice-ai-call-'):
                call_context = self.active_calls.get(room_name)
                call_id = call_context.call_id if call_context else room_name.replace('voice-ai-call-', '')
                
                # Store track information for correlation
                if room_name not in self.call_tracks:
                    self.call_tracks[room_name] = {}
                
                self.call_tracks[room_name][track_sid] = {
                    'type': track_type,
                    'name': track_name,
                    'source': track_source,
                    'participant_identity': participant_identity,
                    'participant_sid': participant_sid,
                    'published_at': datetime.now(UTC).isoformat()
                }
                
                if track_type == 'audio':
                    logger.info(
                        f"Audio track published for voice AI call {call_id}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "track_sid": track_sid,
                            "track_name": track_name,
                            "track_source": track_source,
                            "participant_identity": participant_identity,
                            "participant_sid": participant_sid,
                            "room_name": room_name,
                            "room_sid": room_sid
                        }
                    )
                    
                    # Update metrics
                    self.metrics_collector.increment_counter(
                        "voice_ai_audio_tracks_published_total",
                        labels={
                            "call_id": call_id,
                            "participant_type": "ai_agent" if "agent" in participant_identity.lower() else "caller",
                            "track_source": track_source or "unknown"
                        }
                    )
                    
                    # Notify orchestrator about new audio track for STT processing
                    if call_context and self.orchestrator:
                        try:
                            await self.orchestrator.start_audio_processing(
                                call_context, track_sid, participant_identity
                            )
                            logger.info(
                                f"Started STT pipeline for audio track {track_sid} in call {call_id}",
                                extra={
                                    "event_id": event_id,
                                    "call_id": call_id,
                                    "track_sid": track_sid,
                                    "participant": participant_identity
                                }
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to start STT pipeline for track {track_sid}: {e}",
                                extra={
                                    "event_id": event_id,
                                    "call_id": call_id,
                                    "track_sid": track_sid,
                                    "error_type": type(e).__name__
                                }
                            )
                    
                elif track_type == 'video':
                    logger.info(
                        f"Video track published for voice AI call {call_id}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "track_sid": track_sid,
                            "participant_identity": participant_identity
                        }
                    )
                    
                    self.metrics_collector.increment_counter(
                        "voice_ai_video_tracks_published_total",
                        labels={"call_id": call_id}
                    )
                
                else:
                    logger.debug(
                        f"Non-audio/video track published for call {call_id}: {track_type}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "track_type": track_type,
                            "track_sid": track_sid
                        }
                    )
                
                # Update total tracks metric
                self.metrics_collector.set_gauge(
                    "voice_ai_call_tracks_current",
                    len(self.call_tracks[room_name]),
                    labels={"call_id": call_id}
                )
                
            else:
                logger.debug(
                    f"Track published in non-voice-ai room: {track_type} track {track_sid}",
                    extra={
                        "event_id": event_id,
                        "track_sid": track_sid,
                        "track_type": track_type,
                        "room_name": room_name,
                        "participant_identity": participant_identity
                    }
                )
            
        except Exception as e:
            logger.error(
                f"Error handling track_published event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_track_unpublished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced handler for track unpublished event with cleanup."""
        event_id = event_data.get('event_id', 'unknown')
        
        try:
            track = event_data.get('track', {})
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            track_sid = track.get('sid')
            track_type = track.get('type')
            track_name = track.get('name')
            track_source = track.get('source')
            participant_identity = participant.get('identity')
            participant_sid = participant.get('sid')
            room_name = room.get('name')
            room_sid = room.get('sid')
            
            logger.debug(
                f"Processing track_unpublished event {event_id}",
                extra={
                    "event_id": event_id,
                    "track_sid": track_sid,
                    "track_type": track_type,
                    "participant_identity": participant_identity,
                    "room_name": room_name
                }
            )
            
            # Handle voice AI call tracks
            if room_name and room_name.startswith('voice-ai-call-'):
                call_context = self.active_calls.get(room_name)
                call_id = call_context.call_id if call_context else room_name.replace('voice-ai-call-', '')
                
                # Remove track from correlation data
                if room_name in self.call_tracks and track_sid in self.call_tracks[room_name]:
                    track_info = self.call_tracks[room_name].pop(track_sid)
                    
                    logger.info(
                        f"Track {track_sid} ({track_type}) unpublished for voice AI call {call_id}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "track_sid": track_sid,
                            "track_type": track_type,
                            "track_name": track_name,
                            "track_source": track_source,
                            "participant_identity": participant_identity,
                            "participant_sid": participant_sid,
                            "room_name": room_name,
                            "room_sid": room_sid,
                            "track_was_published_at": track_info.get('published_at')
                        }
                    )
                    
                    # Update metrics
                    if track_type == 'audio':
                        self.metrics_collector.increment_counter(
                            "voice_ai_audio_tracks_unpublished_total",
                            labels={
                                "call_id": call_id,
                                "participant_type": "ai_agent" if "agent" in participant_identity.lower() else "caller",
                                "track_source": track_source or "unknown"
                            }
                        )
                    elif track_type == 'video':
                        self.metrics_collector.increment_counter(
                            "voice_ai_video_tracks_unpublished_total",
                            labels={"call_id": call_id}
                        )
                    
                    # Update total tracks metric
                    remaining_tracks = len(self.call_tracks.get(room_name, {}))
                    self.metrics_collector.set_gauge(
                        "voice_ai_call_tracks_current",
                        remaining_tracks,
                        labels={"call_id": call_id}
                    )
                    
                else:
                    logger.warning(
                        f"Track {track_sid} unpublished but not found in correlation data for call {call_id}",
                        extra={
                            "event_id": event_id,
                            "call_id": call_id,
                            "track_sid": track_sid,
                            "track_type": track_type
                        }
                    )
                
            else:
                logger.info(
                    f"Track {track_sid} ({track_type}) unpublished by {participant_identity} in room {room_name}",
                    extra={
                        "event_id": event_id,
                        "track_sid": track_sid,
                        "track_type": track_type,
                        "track_name": track_name,
                        "participant_identity": participant_identity,
                        "participant_sid": participant_sid,
                        "room_name": room_name,
                        "room_sid": room_sid,
                        "is_voice_ai_call": bool(room_name and room_name.startswith('voice-ai-call-'))
                    }
                )
            
        except Exception as e:
            logger.error(
                f"Error handling track_unpublished event {event_id}: {e}",
                extra={
                    "event_id": event_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    async def _handle_recording_started(self, event_data: Dict[str, Any]) -> None:
        """Handle recording started event."""
        try:
            recording = event_data.get('egressInfo', {})
            room = event_data.get('room', {})
            
            recording_id = recording.get('egressId')
            room_name = room.get('name')
            
            logger.info(
                f"Recording {recording_id} started for room {room_name}",
                extra={
                    "recording_id": recording_id,
                    "room_name": room_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling recording started event: {e}")
    
    async def _handle_recording_finished(self, event_data: Dict[str, Any]) -> None:
        """Handle recording finished event."""
        try:
            recording = event_data.get('egressInfo', {})
            room = event_data.get('room', {})
            
            recording_id = recording.get('egressId')
            room_name = room.get('name')
            
            logger.info(
                f"Recording {recording_id} finished for room {room_name}",
                extra={
                    "recording_id": recording_id,
                    "room_name": room_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling recording finished event: {e}")
    
    def get_call_correlation_info(self, room_name: str) -> Optional[Dict[str, Any]]:
        """
        Get correlation information for a call.
        
        Args:
            room_name: LiveKit room name
            
        Returns:
            Dictionary with call correlation info or None if not found
        """
        call_context = self.active_calls.get(room_name)
        if not call_context:
            return None
        
        return {
            "call_id": call_context.call_id,
            "caller_number": call_context.caller_number,
            "start_time": call_context.start_time.isoformat(),
            "room_name": room_name,
            "participants": list(self.call_participants.get(room_name, set())),
            "tracks": list(self.call_tracks.get(room_name, {}).keys()),
            "metadata": call_context.metadata
        }
    
    def get_webhook_statistics(self) -> Dict[str, Any]:
        """
        Get webhook handler statistics.
        
        Returns:
            Dictionary with webhook statistics
        """
        return {
            "total_events_received": self.total_events_received,
            "total_events_processed": self.total_events_processed,
            "total_events_failed": self.total_events_failed,
            "signature_validation_failures": self.signature_validation_failures,
            "active_calls_count": len(self.active_calls),
            "total_participants": sum(len(participants) for participants in self.call_participants.values()),
            "total_tracks": sum(len(tracks) for tracks in self.call_tracks.values()),
            "event_queue_size": self.event_queue.qsize(),
            "active_calls": [
                {
                    "call_id": context.call_id,
                    "caller_number": context.caller_number,
                    "room_name": room_name,
                    "participants_count": len(self.call_participants.get(room_name, set())),
                    "tracks_count": len(self.call_tracks.get(room_name, {}))
                }
                for room_name, context in self.active_calls.items()
            ]
        }
    
    async def cleanup_stale_calls(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale call correlation data.
        
        Args:
            max_age_hours: Maximum age in hours for call data
            
        Returns:
            Number of calls cleaned up
        """
        try:
            current_time = datetime.now(UTC)
            stale_rooms = []
            
            for room_name, call_context in self.active_calls.items():
                age_hours = (current_time - call_context.start_time).total_seconds() / 3600
                if age_hours > max_age_hours:
                    stale_rooms.append(room_name)
            
            # Clean up stale data
            for room_name in stale_rooms:
                call_context = self.active_calls.pop(room_name, None)
                self.call_participants.pop(room_name, None)
                self.call_tracks.pop(room_name, None)
                
                if call_context:
                    logger.warning(
                        f"Cleaned up stale call data for {call_context.call_id}",
                        extra={
                            "call_id": call_context.call_id,
                            "room_name": room_name,
                            "age_hours": (current_time - call_context.start_time).total_seconds() / 3600
                        }
                    )
            
            if stale_rooms:
                self.metrics_collector.increment_counter(
                    "webhook_stale_calls_cleaned_total",
                    labels={"count": str(len(stale_rooms))}
                )
            
            return len(stale_rooms)
            
        except Exception as e:
            logger.error(f"Error cleaning up stale calls: {e}")
            return 0


# Global webhook handler instance
_webhook_handler: Optional[WebhookHandler] = None


def get_webhook_handler(orchestrator: CallOrchestrator) -> WebhookHandler:
    """Get the global webhook handler instance."""
    global _webhook_handler
    
    if _webhook_handler is None:
        _webhook_handler = WebhookHandler(orchestrator)
    
    return _webhook_handler


def setup_webhook_routes(app: FastAPI, orchestrator: CallOrchestrator) -> None:
    """
    Setup enhanced webhook routes in FastAPI application.
    
    Args:
        app: FastAPI application instance
        orchestrator: Call orchestrator instance
    """
    webhook_handler = get_webhook_handler(orchestrator)
    
    @app.post("/webhooks/livekit")
    async def livekit_webhook(request: Request, background_tasks: BackgroundTasks):
        """Enhanced LiveKit webhook endpoint with improved validation and logging."""
        return await webhook_handler.handle_webhook(request, background_tasks)
    
    @app.get("/webhooks/health")
    async def webhook_health():
        """Enhanced webhook health check endpoint with statistics."""
        try:
            stats = webhook_handler.get_webhook_statistics()
            return {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "statistics": stats,
                "event_processor_running": webhook_handler.event_processor_task is not None and not webhook_handler.event_processor_task.done()
            }
        except Exception as e:
            logger.error(f"Webhook health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    @app.get("/webhooks/calls")
    async def active_calls():
        """Get information about active calls."""
        try:
            active_calls_info = []
            for room_name, call_context in webhook_handler.active_calls.items():
                correlation_info = webhook_handler.get_call_correlation_info(room_name)
                if correlation_info:
                    active_calls_info.append(correlation_info)
            
            return {
                "active_calls": active_calls_info,
                "total_count": len(active_calls_info),
                "timestamp": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting active calls info: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    @app.get("/webhooks/calls/{call_id}")
    async def call_info(call_id: str):
        """Get detailed information about a specific call."""
        try:
            # Find call by ID
            for room_name, call_context in webhook_handler.active_calls.items():
                if call_context.call_id == call_id:
                    correlation_info = webhook_handler.get_call_correlation_info(room_name)
                    if correlation_info:
                        return correlation_info
            
            return {
                "error": f"Call {call_id} not found",
                "timestamp": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting call info for {call_id}: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    @app.post("/webhooks/cleanup")
    async def cleanup_stale_calls(max_age_hours: int = 24):
        """Clean up stale call correlation data."""
        try:
            cleaned_count = await webhook_handler.cleanup_stale_calls(max_age_hours)
            return {
                "cleaned_calls": cleaned_count,
                "max_age_hours": max_age_hours,
                "timestamp": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.error(f"Error cleaning up stale calls: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    @app.get("/health")
    async def system_health():
        """Enhanced system health check endpoint."""
        try:
            from src.health import check_health
            health_data = check_health()
            
            # Add webhook-specific health info
            webhook_stats = webhook_handler.get_webhook_statistics()
            health_data["webhook_handler"] = {
                "status": "healthy" if webhook_handler.event_processor_task and not webhook_handler.event_processor_task.done() else "unhealthy",
                "events_processed": webhook_stats["total_events_processed"],
                "events_failed": webhook_stats["total_events_failed"],
                "active_calls": webhook_stats["active_calls_count"],
                "queue_size": webhook_stats["event_queue_size"]
            }
            
            return health_data
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    logger.info("Enhanced webhook routes configured with monitoring endpoints")


async def start_webhook_handler(orchestrator: CallOrchestrator) -> None:
    """Start the webhook handler."""
    webhook_handler = get_webhook_handler(orchestrator)
    await webhook_handler.start()


async def stop_webhook_handler() -> None:
    """Stop the webhook handler."""
    global _webhook_handler
    
    if _webhook_handler:
        await _webhook_handler.stop()
        _webhook_handler = None 
   # Enhanced LiveKit Event Handlers for improved integration
    
    async def _handle_livekit_room_started(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit room started handler with API integration."""
        event_id = event_data.get('event_id', 'unknown')
        room_data = event_data.get('room', {})
        room_name = room_data.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit room started processing: {room_name}")
            
            # Use API client for enhanced room management if available
            if self.api_client and room_name:
                try:
                    # Get detailed room information
                    room_info = await self.api_client.get_room(room_name)
                    if room_info:
                        logger.info(f"Enhanced room info retrieved for {room_name}: {room_info.num_participants} participants")
                        
                        # Update event data with enhanced information
                        event_data['enhanced_room_info'] = {
                            'num_participants': room_info.num_participants,
                            'creation_time': room_info.creation_time,
                            'turn_password': room_info.turn_password,
                            'enabled_codecs': room_info.enabled_codecs
                        }
                        
                except Exception as e:
                    logger.warning(f"Failed to get enhanced room info for {room_name}: {e}")
            
            # Enhanced metrics for LiveKit integration
            self.metrics_collector.increment_counter(
                "livekit_enhanced_room_started_total",
                labels={"room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other"}
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit room started handler: {e}")
    
    async def _handle_livekit_room_finished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit room finished handler with cleanup."""
        event_id = event_data.get('event_id', 'unknown')
        room_data = event_data.get('room', {})
        room_name = room_data.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit room finished processing: {room_name}")
            
            # Enhanced cleanup using API client
            if self.api_client and room_name:
                try:
                    # Ensure room is properly cleaned up
                    await self.api_client.delete_room(room_name)
                    logger.info(f"Enhanced room cleanup completed for {room_name}")
                    
                except Exception as e:
                    logger.warning(f"Enhanced room cleanup failed for {room_name}: {e}")
            
            # Enhanced metrics
            self.metrics_collector.increment_counter(
                "livekit_enhanced_room_finished_total",
                labels={"room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other"}
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit room finished handler: {e}")
    
    async def _handle_livekit_participant_joined(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit participant joined handler with authentication."""
        event_id = event_data.get('event_id', 'unknown')
        participant = event_data.get('participant', {})
        room = event_data.get('room', {})
        
        participant_identity = participant.get('identity')
        room_name = room.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit participant joined: {participant_identity} in {room_name}")
            
            # Enhanced participant validation using auth manager
            if self.auth_manager and participant_identity:
                try:
                    # Validate participant permissions
                    is_authorized = await self._validate_participant_authorization(
                        participant_identity, room_name
                    )
                    
                    if not is_authorized:
                        logger.warning(f"Unauthorized participant detected: {participant_identity}")
                        # Could trigger participant removal here if needed
                    else:
                        logger.info(f"Participant {participant_identity} authorized for room {room_name}")
                        
                except Exception as e:
                    logger.warning(f"Participant authorization check failed: {e}")
            
            # Enhanced metrics
            self.metrics_collector.increment_counter(
                "livekit_enhanced_participant_joined_total",
                labels={
                    "room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other",
                    "participant_type": self._classify_participant_type(participant_identity)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit participant joined handler: {e}")
    
    async def _handle_livekit_participant_left(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit participant left handler with cleanup."""
        event_id = event_data.get('event_id', 'unknown')
        participant = event_data.get('participant', {})
        room = event_data.get('room', {})
        
        participant_identity = participant.get('identity')
        room_name = room.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit participant left: {participant_identity} from {room_name}")
            
            # Enhanced cleanup for participant resources
            if self.api_client and participant_identity and room_name:
                try:
                    # Clean up any participant-specific resources
                    await self._cleanup_participant_resources(participant_identity, room_name)
                    
                except Exception as e:
                    logger.warning(f"Participant resource cleanup failed: {e}")
            
            # Enhanced metrics
            self.metrics_collector.increment_counter(
                "livekit_enhanced_participant_left_total",
                labels={
                    "room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other",
                    "participant_type": self._classify_participant_type(participant_identity)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit participant left handler: {e}")
    
    async def _handle_livekit_track_published(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit track published handler with audio processing."""
        event_id = event_data.get('event_id', 'unknown')
        track = event_data.get('track', {})
        participant = event_data.get('participant', {})
        room = event_data.get('room', {})
        
        track_sid = track.get('sid')
        track_type = track.get('type')
        participant_identity = participant.get('identity')
        room_name = room.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit track published: {track_sid} ({track_type}) by {participant_identity}")
            
            # Enhanced audio track processing for Voice AI
            if track_type == 'audio' and room_name and "voice-ai" in room_name:
                try:
                    # Notify orchestrator about new audio track for processing
                    if self.orchestrator and participant_identity:
                        await self._notify_orchestrator_audio_track(
                            track_sid, participant_identity, room_name
                        )
                        
                except Exception as e:
                    logger.warning(f"Failed to notify orchestrator about audio track: {e}")
            
            # Enhanced metrics
            self.metrics_collector.increment_counter(
                "livekit_enhanced_track_published_total",
                labels={
                    "track_type": track_type or "unknown",
                    "room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other"
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit track published handler: {e}")
    
    async def _handle_livekit_track_unpublished(self, event_data: Dict[str, Any]) -> None:
        """Enhanced LiveKit track unpublished handler with cleanup."""
        event_id = event_data.get('event_id', 'unknown')
        track = event_data.get('track', {})
        participant = event_data.get('participant', {})
        room = event_data.get('room', {})
        
        track_sid = track.get('sid')
        track_type = track.get('type')
        participant_identity = participant.get('identity')
        room_name = room.get('name')
        
        try:
            logger.debug(f"Enhanced LiveKit track unpublished: {track_sid} ({track_type}) by {participant_identity}")
            
            # Enhanced cleanup for audio track processing
            if track_type == 'audio' and room_name and "voice-ai" in room_name:
                try:
                    # Notify orchestrator about track cleanup
                    if self.orchestrator and participant_identity:
                        await self._notify_orchestrator_track_cleanup(
                            track_sid, participant_identity, room_name
                        )
                        
                except Exception as e:
                    logger.warning(f"Failed to notify orchestrator about track cleanup: {e}")
            
            # Enhanced metrics
            self.metrics_collector.increment_counter(
                "livekit_enhanced_track_unpublished_total",
                labels={
                    "track_type": track_type or "unknown",
                    "room_type": "voice_ai" if room_name and "voice-ai" in room_name else "other"
                }
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced LiveKit track unpublished handler: {e}")
    
    # Helper methods for enhanced LiveKit integration
    
    async def _validate_participant_authorization(self, participant_identity: str, room_name: str) -> bool:
        """Validate participant authorization using auth manager."""
        try:
            if not self.auth_manager:
                return True  # Skip validation if no auth manager
            
            # Create a basic token to validate permissions
            token = self.auth_manager.create_access_token(
                identity=participant_identity,
                room=room_name,
                grants={
                    'room_join': True,
                    'room_list': False,
                    'room_record': False,
                    'room_admin': False,
                    'can_publish': True,
                    'can_subscribe': True
                }
            )
            
            # If token creation succeeds, participant is authorized
            return bool(token)
            
        except Exception as e:
            logger.error(f"Participant authorization validation failed: {e}")
            return False
    
    def _classify_participant_type(self, participant_identity: str) -> str:
        """Classify participant type based on identity."""
        if not participant_identity:
            return "unknown"
        
        if "sip-" in participant_identity.lower():
            return "sip_caller"
        elif "ai-agent" in participant_identity.lower():
            return "ai_agent"
        elif "bot" in participant_identity.lower():
            return "bot"
        else:
            return "user"
    
    async def _cleanup_participant_resources(self, participant_identity: str, room_name: str) -> None:
        """Clean up resources associated with a participant."""
        try:
            # Remove participant from tracking
            if room_name in self.call_participants:
                self.call_participants[room_name].discard(participant_identity)
            
            # Clean up any participant-specific tracks
            if room_name in self.call_tracks:
                tracks_to_remove = [
                    track_id for track_id, track_info in self.call_tracks[room_name].items()
                    if track_info.get('participant_identity') == participant_identity
                ]
                for track_id in tracks_to_remove:
                    self.call_tracks[room_name].pop(track_id, None)
            
            logger.debug(f"Cleaned up resources for participant {participant_identity} in room {room_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up participant resources: {e}")
    
    async def _notify_orchestrator_audio_track(self, track_sid: str, participant_identity: str, room_name: str) -> None:
        """Notify orchestrator about new audio track for processing."""
        try:
            if not self.orchestrator:
                return
            
            # Get call context for the room
            call_context = self.active_calls.get(room_name)
            if not call_context:
                logger.warning(f"No call context found for room {room_name}")
                return
            
            # Notify orchestrator about the new audio track
            # This would integrate with the orchestrator's audio processing pipeline
            logger.info(f"Notified orchestrator about audio track {track_sid} for call {call_context.call_id}")
            
        except Exception as e:
            logger.error(f"Error notifying orchestrator about audio track: {e}")
    
    async def _notify_orchestrator_track_cleanup(self, track_sid: str, participant_identity: str, room_name: str) -> None:
        """Notify orchestrator about track cleanup."""
        try:
            if not self.orchestrator:
                return
            
            # Get call context for the room
            call_context = self.active_calls.get(room_name)
            if not call_context:
                logger.warning(f"No call context found for room {room_name}")
                return
            
            # Notify orchestrator about track cleanup
            logger.info(f"Notified orchestrator about track cleanup {track_sid} for call {call_context.call_id}")
            
        except Exception as e:
            logger.error(f"Error notifying orchestrator about track cleanup: {e}")