"""
Webhook handlers for LiveKit SIP integration.

This module provides webhook endpoints for handling LiveKit events,
including call start, call end, participant events, and audio track events.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.livekit_integration import get_livekit_integration, LiveKitEventType
from src.orchestrator import CallContext, CallOrchestrator
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handler for LiveKit webhook events."""
    
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
        
        # Event processing queue
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_processor_task: Optional[asyncio.Task] = None
        
        logger.info("Webhook handler initialized")
    
    async def start(self) -> None:
        """Start the webhook handler."""
        try:
            # Get LiveKit integration
            self.livekit_integration = await get_livekit_integration()
            
            # Start event processor
            self.event_processor_task = asyncio.create_task(self._process_events())
            
            logger.info("Webhook handler started")
            
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
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature from LiveKit.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook header
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.settings.secret_key:
                logger.warning("No secret key configured for webhook verification")
                return True  # Skip verification if no secret key
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.settings.secret_key.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def handle_webhook(
        self, 
        request: Request, 
        background_tasks: BackgroundTasks
    ) -> JSONResponse:
        """
        Handle incoming webhook from LiveKit.
        
        Args:
            request: FastAPI request object
            background_tasks: Background tasks for async processing
            
        Returns:
            JSON response
        """
        try:
            # Get raw payload
            payload = await request.body()
            
            # Verify signature if provided
            signature = request.headers.get('x-livekit-signature')
            if signature and not self.verify_webhook_signature(payload, signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
            
            # Parse JSON payload
            try:
                event_data = json.loads(payload.decode())
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in webhook payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Add timestamp
            event_data['received_at'] = datetime.now(UTC).isoformat()
            
            # Queue event for processing
            await self.event_queue.put(event_data)
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "webhook_events_received_total",
                labels={"event_type": event_data.get('event', 'unknown')}
            )
            
            logger.debug(
                f"Queued webhook event: {event_data.get('event')}",
                extra={"event_data": event_data}
            )
            
            return JSONResponse(
                status_code=200,
                content={"status": "received", "timestamp": event_data['received_at']}
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            self.metrics_collector.increment_counter("webhook_errors_total")
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
        Process a single webhook event.
        
        Args:
            event_data: Event data from webhook
        """
        try:
            event_type = event_data.get('event')
            
            if event_type == LiveKitEventType.ROOM_STARTED.value:
                await self._handle_room_started(event_data)
            elif event_type == LiveKitEventType.ROOM_FINISHED.value:
                await self._handle_room_finished(event_data)
            elif event_type == LiveKitEventType.PARTICIPANT_JOINED.value:
                await self._handle_participant_joined(event_data)
            elif event_type == LiveKitEventType.PARTICIPANT_LEFT.value:
                await self._handle_participant_left(event_data)
            elif event_type == LiveKitEventType.TRACK_PUBLISHED.value:
                await self._handle_track_published(event_data)
            elif event_type == LiveKitEventType.TRACK_UNPUBLISHED.value:
                await self._handle_track_unpublished(event_data)
            elif event_type == LiveKitEventType.RECORDING_STARTED.value:
                await self._handle_recording_started(event_data)
            elif event_type == LiveKitEventType.RECORDING_FINISHED.value:
                await self._handle_recording_finished(event_data)
            else:
                logger.warning(f"Unknown event type: {event_type}")
            
            # Forward to LiveKit integration
            if self.livekit_integration:
                await self.livekit_integration.handle_webhook_event(event_data)
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "webhook_events_processed_total",
                labels={"event_type": event_type or "unknown"}
            )
            
        except Exception as e:
            logger.error(f"Error processing event {event_data.get('event')}: {e}")
            raise
    
    async def _handle_room_started(self, event_data: Dict[str, Any]) -> None:
        """Handle room started event."""
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return  # Not our call
            
            # Extract call ID from room name
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Parse metadata
            metadata_str = room_data.get('metadata', '{}')
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}
            
            # Create call context
            call_context = CallContext(
                call_id=call_id,
                caller_number=metadata.get('caller_number', 'unknown'),
                start_time=datetime.now(UTC),
                livekit_room=room_name,
                metadata=metadata
            )
            
            # Notify orchestrator
            await self.orchestrator.handle_call_start(call_context)
            
            logger.info(
                f"Room started for call {call_id}",
                extra={"call_id": call_id, "room_name": room_name}
            )
            
        except Exception as e:
            logger.error(f"Error handling room started event: {e}")
    
    async def _handle_room_finished(self, event_data: Dict[str, Any]) -> None:
        """Handle room finished event."""
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return  # Not our call
            
            # Extract call ID from room name
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Parse metadata
            metadata_str = room_data.get('metadata', '{}')
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}
            
            # Create call context
            call_context = CallContext(
                call_id=call_id,
                caller_number=metadata.get('caller_number', 'unknown'),
                start_time=datetime.now(UTC),  # Will be updated by orchestrator
                livekit_room=room_name,
                metadata=metadata
            )
            
            # Notify orchestrator
            await self.orchestrator.handle_call_end(call_context)
            
            # Notify LiveKit integration
            if self.livekit_integration:
                await self.livekit_integration.handle_call_end(call_context)
            
            logger.info(
                f"Room finished for call {call_id}",
                extra={"call_id": call_id, "room_name": room_name}
            )
            
        except Exception as e:
            logger.error(f"Error handling room finished event: {e}")
    
    async def _handle_participant_joined(self, event_data: Dict[str, Any]) -> None:
        """Handle participant joined event."""
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            participant_identity = participant.get('identity')
            room_name = room.get('name')
            
            logger.info(
                f"Participant {participant_identity} joined room {room_name}",
                extra={
                    "participant_identity": participant_identity,
                    "room_name": room_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling participant joined event: {e}")
    
    async def _handle_participant_left(self, event_data: Dict[str, Any]) -> None:
        """Handle participant left event."""
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            participant_identity = participant.get('identity')
            room_name = room.get('name')
            
            logger.info(
                f"Participant {participant_identity} left room {room_name}",
                extra={
                    "participant_identity": participant_identity,
                    "room_name": room_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling participant left event: {e}")
    
    async def _handle_track_published(self, event_data: Dict[str, Any]) -> None:
        """Handle track published event."""
        try:
            track = event_data.get('track', {})
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            track_sid = track.get('sid')
            track_type = track.get('type')
            participant_identity = participant.get('identity')
            room_name = room.get('name')
            
            # Handle audio track for voice AI calls
            if (track_type == 'audio' and 
                room_name and room_name.startswith('voice-ai-call-')):
                
                call_id = room_name.replace('voice-ai-call-', '')
                
                logger.info(
                    f"Audio track published for call {call_id}",
                    extra={
                        "call_id": call_id,
                        "track_sid": track_sid,
                        "participant_identity": participant_identity
                    }
                )
                
                # TODO: Start audio processing for this track
                # This would involve subscribing to the audio stream
                # and feeding it to the orchestrator
            
        except Exception as e:
            logger.error(f"Error handling track published event: {e}")
    
    async def _handle_track_unpublished(self, event_data: Dict[str, Any]) -> None:
        """Handle track unpublished event."""
        try:
            track = event_data.get('track', {})
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            track_sid = track.get('sid')
            track_type = track.get('type')
            participant_identity = participant.get('identity')
            room_name = room.get('name')
            
            logger.info(
                f"Track {track_sid} ({track_type}) unpublished by {participant_identity} in room {room_name}",
                extra={
                    "track_sid": track_sid,
                    "track_type": track_type,
                    "participant_identity": participant_identity,
                    "room_name": room_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling track unpublished event: {e}")
    
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
    Setup webhook routes in FastAPI application.
    
    Args:
        app: FastAPI application instance
        orchestrator: Call orchestrator instance
    """
    webhook_handler = get_webhook_handler(orchestrator)
    
    @app.post("/webhooks/livekit")
    async def livekit_webhook(request: Request, background_tasks: BackgroundTasks):
        """LiveKit webhook endpoint."""
        return await webhook_handler.handle_webhook(request, background_tasks)
    
    @app.get("/webhooks/health")
    async def webhook_health():
        """Webhook health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}
    
    logger.info("Webhook routes configured")


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