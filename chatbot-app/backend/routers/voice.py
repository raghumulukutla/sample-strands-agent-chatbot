"""
Voice Router - WebSocket endpoints for real-time voice chat
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import Response
import logging
import asyncio
import json
from typing import Optional, Dict, Any
import base64

from services.transcription import TranscriptionService
from services.text_to_speech import TextToSpeechService
from session.global_session_registry import global_session_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Initialize services
transcription_service = TranscriptionService(
    region_name="us-west-2",
    language_code="en-US",
    sample_rate=16000,
    enable_partial_results=True
)

tts_service = TextToSpeechService(
    region_name="us-west-2",
    voice_id="Joanna",
    engine="neural",
    output_format="mp3"
)


class VoiceSession:
    """Manages a voice chat session with transcription and TTS"""
    
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.transcription_buffer = []
        self.is_recording = False
        self.agent = None
        self.session_manager = None
    
    async def initialize_agent(self):
        """Initialize or get existing agent for this session"""
        _, self.session_manager, self.agent = global_session_registry.get_or_create_session(
            self.session_id
        )
    
    async def handle_audio_chunk(self, audio_data: bytes):
        """Process incoming audio chunk"""
        try:
            # Buffer audio for transcription
            self.transcription_buffer.append(audio_data)
            
            # Send to transcription service
            # (In production, you'd use streaming transcription)
            
        except Exception as e:
            logger.error(f"Error handling audio chunk: {e}")
            await self.send_error(str(e))
    
    async def process_transcription(self, transcription: str, is_final: bool):
        """Process transcription and generate response"""
        try:
            # Send transcription to client
            await self.websocket.send_json({
                "type": "transcription",
                "text": transcription,
                "is_final": is_final
            })
            
            if is_final and self.agent:
                # Send to agent for processing
                await self.websocket.send_json({
                    "type": "processing",
                    "message": "Thinking..."
                })
                
                # Get agent response
                response_text = await self.agent.invoke_async(transcription)
                
                # Send text response
                await self.websocket.send_json({
                    "type": "response_text",
                    "text": str(response_text)
                })
                
                # Generate and send audio response
                audio_data = await tts_service.synthesize_speech(str(response_text))
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                await self.websocket.send_json({
                    "type": "audio_response",
                    "audio": audio_base64,
                    "format": "mp3"
                })
                
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")
            await self.send_error(str(e))
    
    async def send_error(self, error_message: str):
        """Send error message to client"""
        await self.websocket.send_json({
            "type": "error",
            "message": error_message
        })


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket, session_id: Optional[str] = None):
    """
    WebSocket endpoint for real-time voice chat
    
    Client sends: {"type": "audio", "data": base64_audio_chunk}
    Client sends: {"type": "start_recording"}
    Client sends: {"type": "stop_recording"}
    
    Server sends: {"type": "transcription", "text": "...", "is_final": bool}
    Server sends: {"type": "response_text", "text": "..."}
    Server sends: {"type": "audio_response", "audio": base64_audio, "format": "mp3"}
    """
    await websocket.accept()
    
    # Generate session ID if not provided
    if not session_id:
        import uuid
        session_id = f"voice_{uuid.uuid4().hex[:8]}"
    
    voice_session = VoiceSession(websocket, session_id)
    
    try:
        # Initialize agent
        await voice_session.initialize_agent()
        
        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "session_id": session_id,
            "message": "Voice chat ready"
        })
        
        # Main message loop
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "audio":
                # Receive audio chunk
                audio_base64 = message.get("data")
                if audio_base64:
                    audio_bytes = base64.b64decode(audio_base64)
                    await voice_session.handle_audio_chunk(audio_bytes)
            
            elif message_type == "start_recording":
                voice_session.is_recording = True
                voice_session.transcription_buffer = []
                await websocket.send_json({
                    "type": "recording_started",
                    "message": "Recording started"
                })
            
            elif message_type == "stop_recording":
                voice_session.is_recording = False
                
                # Process buffered audio
                if voice_session.transcription_buffer:
                    # Combine audio chunks
                    full_audio = b''.join(voice_session.transcription_buffer)
                    
                    # Transcribe
                    transcription = await transcription_service.transcribe_audio_buffer(
                        full_audio,
                        audio_format="wav"
                    )
                    
                    # Process transcription
                    await voice_session.process_transcription(transcription, is_final=True)
                    
                    # Clear buffer
                    voice_session.transcription_buffer = []
            
            elif message_type == "text_message":
                # Handle text message directly (fallback to text chat)
                text = message.get("text")
                if text and voice_session.agent:
                    response_text = await voice_session.agent.invoke_async(text)
                    
                    await websocket.send_json({
                        "type": "response_text",
                        "text": str(response_text)
                    })
                    
                    # Optionally generate audio
                    if message.get("generate_audio", True):
                        audio_data = await tts_service.synthesize_speech(str(response_text))
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        
                        await websocket.send_json({
                            "type": "audio_response",
                            "audio": audio_base64,
                            "format": "mp3"
                        })
            
            elif message_type == "ping":
                # Keepalive
                await websocket.send_json({"type": "pong"})
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Voice session {session_id} disconnected")
    except Exception as e:
        logger.error(f"Voice session error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@router.post("/synthesize")
async def synthesize_speech(
    request: Dict[str, Any],
    x_session_id: Optional[str] = Header(None)
):
    """
    Synthesize speech from text (REST endpoint)
    
    Request body:
    {
        "text": "Hello, world!",
        "voice_id": "Joanna",  // optional
        "use_ssml": false      // optional
    }
    
    Returns audio as base64 encoded data
    """
    try:
        text = request.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        voice_id = request.get("voice_id")
        use_ssml = request.get("use_ssml", False)
        
        # Synthesize speech
        audio_data = await tts_service.synthesize_speech(
            text,
            voice_id=voice_id,
            use_ssml=use_ssml
        )
        
        # Return audio as base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "audio": audio_base64,
            "format": "mp3",
            "voice_id": voice_id or tts_service.voice_id
        }
    
    except Exception as e:
        logger.error(f"Speech synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize/stream")
async def synthesize_speech_streaming(
    request: Dict[str, Any],
    x_session_id: Optional[str] = Header(None)
):
    """
    Synthesize speech with streaming audio chunks
    
    Returns Server-Sent Events with audio chunks
    """
    try:
        text = request.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        voice_id = request.get("voice_id")
        
        async def audio_stream_generator():
            """Generate SSE audio chunks"""
            try:
                async for audio_chunk in tts_service.synthesize_speech_streaming(text, voice_id):
                    audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                    yield f"data: {json.dumps({'audio': audio_base64, 'format': 'mp3'})}\n\n"
                
                # Send completion event
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            audio_stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    
    except Exception as e:
        logger.error(f"Speech synthesis streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def get_available_voices(
    language_code: Optional[str] = None,
    neural_only: bool = True
):
    """
    Get list of available voices
    
    Query params:
    - language_code: Filter by language (e.g., 'en-US')
    - neural_only: Only return neural voices (default: true)
    """
    try:
        voices = await tts_service.get_available_voices(
            language_code=language_code,
            include_neural_only=neural_only
        )
        
        return {
            "voices": voices,
            "count": len(voices)
        }
    
    except Exception as e:
        logger.error(f"Error getting voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_voice_config():
    """
    Get current voice configuration
    """
    return {
        "transcription": {
            "language_code": transcription_service.language_code,
            "sample_rate": transcription_service.sample_rate,
            "partial_results": transcription_service.enable_partial_results
        },
        "tts": {
            "voice_id": tts_service.voice_id,
            "engine": tts_service.engine,
            "output_format": tts_service.output_format,
            "sample_rate": tts_service.sample_rate
        },
        "recommended_voices": {
            "en-US": {
                "male": TextToSpeechService.get_recommended_voice("en-US", "male"),
                "female": TextToSpeechService.get_recommended_voice("en-US", "female")
            }
        }
    }


@router.post("/config")
async def update_voice_config(request: Dict[str, Any]):
    """
    Update voice configuration
    
    Request body:
    {
        "voice_id": "Matthew",
        "language_code": "en-US"
    }
    """
    try:
        global transcription_service, tts_service
        
        if "voice_id" in request:
            tts_service.voice_id = request["voice_id"]
        
        if "language_code" in request:
            transcription_service.language_code = request["language_code"]
        
        return {
            "message": "Configuration updated",
            "config": await get_voice_config()
        }
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
