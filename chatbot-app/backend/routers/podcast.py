"""
Podcast Router - Endpoints for podcast upload, transcription, and summarization
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
import logging
import os
import shutil
from typing import Optional, Dict, Any

from services.podcast_processor import get_podcast_processor, PodcastProcessor
from config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/podcast", tags=["podcast"])

# Podcast storage directory
PODCAST_DIR = os.path.join(Config.OUTPUT_DIR, "podcasts")
os.makedirs(PODCAST_DIR, exist_ok=True)

# Supported audio formats
SUPPORTED_FORMATS = [
    "audio/mpeg",  # MP3
    "audio/wav",   # WAV
    "audio/mp4",   # M4A
    "audio/x-m4a", # M4A alternative
    "audio/flac",  # FLAC
    "audio/ogg",   # OGG
]


@router.post("/upload")
async def upload_podcast(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Upload podcast file for processing
    
    Args:
        file: Audio file (MP3, WAV, M4A, FLAC, OGG)
        title: Podcast title
        description: Optional description
        x_session_id: Session ID for tracking
    
    Returns:
        {
            "job_id": "podcast_xxxxx",
            "status": "uploaded",
            "message": "Podcast uploaded successfully"
        }
    """
    try:
        # Validate file type
        if file.content_type not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file.content_type}. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Validate file size (max 500MB)
        max_size = 500 * 1024 * 1024  # 500MB
        file_size = 0
        
        # Save file
        import uuid
        file_id = uuid.uuid4().hex[:12]
        file_extension = os.path.splitext(file.filename)[1] or ".mp3"
        filename = f"podcast_{file_id}{file_extension}"
        file_path = os.path.join(PODCAST_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):  # 8KB chunks
                file_size += len(chunk)
                if file_size > max_size:
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Maximum size is 500MB"
                    )
                buffer.write(chunk)
        
        logger.info(f"Podcast uploaded: {filename} ({file_size} bytes)")
        
        # Create processing job
        processor = get_podcast_processor()
        job_id = await processor.create_job(
            audio_path=file_path,
            title=title,
            description=description
        )
        
        return {
            "job_id": job_id,
            "status": "uploaded",
            "message": "Podcast uploaded successfully. Processing started.",
            "file_size": file_size,
            "filename": filename
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Podcast upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/status")
async def get_podcast_status(job_id: str):
    """
    Get podcast processing status
    
    Returns:
        {
            "job_id": "podcast_xxxxx",
            "status": "transcribing" | "analyzing" | "generating_audio" | "completed" | "failed",
            "progress": 45,  // 0-100
            "created_at": "2025-11-06T12:00:00",
            "error": null
        }
    """
    try:
        processor = get_podcast_processor()
        status = processor.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/results")
async def get_podcast_results(job_id: str):
    """
    Get complete podcast processing results
    
    Returns full analysis including:
    - Transcription (full text + segments)
    - Analysis (summaries, topics, takeaways)
    - Audio summary path
    """
    try:
        processor = get_podcast_processor()
        results = processor.get_job_results(job_id)
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail="Job not found or not completed yet"
            )
        
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Results retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/audio-summary")
async def get_audio_summary(job_id: str):
    """
    Download audio summary file
    
    Returns MP3 audio file
    """
    try:
        processor = get_podcast_processor()
        results = processor.get_job_results(job_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Job not found or not completed")
        
        audio_path = results.get("audio_summary_path")
        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="Audio summary not available")
        
        return FileResponse(
            path=audio_path,
            media_type="audio/mpeg",
            filename=f"{job_id}_summary.mp3"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/transcription")
async def get_transcription(job_id: str, format: str = "json"):
    """
    Get podcast transcription
    
    Query params:
    - format: 'json' (default) or 'text'
    
    Returns transcription in requested format
    """
    try:
        processor = get_podcast_processor()
        results = processor.get_job_results(job_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Job not found or not completed")
        
        transcription = results.get("transcription")
        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not available")
        
        if format == "text":
            # Return plain text
            return JSONResponse(
                content={"text": transcription.get("full_text", "")},
                media_type="application/json"
            )
        else:
            # Return full JSON
            return transcription
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/regenerate-audio")
async def regenerate_audio_summary(
    job_id: str,
    request: Dict[str, Any]
):
    """
    Regenerate audio summary with different voice
    
    Request body:
    {
        "voice_id": "Matthew" | "Joanna" | ...
    }
    """
    try:
        processor = get_podcast_processor()
        results = processor.get_job_results(job_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Job not found or not completed")
        
        voice_id = request.get("voice_id", "Matthew")
        
        # Get analysis
        analysis = results.get("analysis")
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not available")
        
        # Regenerate audio with new voice
        from services.text_to_speech import TextToSpeechService
        tts_service = TextToSpeechService(voice_id=voice_id)
        
        script = processor._create_summary_script(results.get("title", ""), analysis)
        audio_data = await tts_service.synthesize_speech(script)
        
        # Save new audio
        audio_filename = f"{job_id}_summary_{voice_id}.mp3"
        audio_path = os.path.join(PODCAST_DIR, audio_filename)
        
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        
        return {
            "message": "Audio summary regenerated",
            "voice_id": voice_id,
            "audio_url": f"/api/podcast/{job_id}/audio-summary"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio regeneration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_podcast_job(job_id: str):
    """
    Delete podcast job and associated files
    """
    try:
        processor = get_podcast_processor()
        job_status = processor.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Delete associated files
        # (Implementation depends on file storage strategy)
        
        # Remove from processor
        if job_id in processor.jobs:
            del processor.jobs[job_id]
        
        return {
            "message": "Podcast job deleted successfully",
            "job_id": job_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/list")
async def list_podcast_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """
    List podcast jobs with optional filtering
    
    Query params:
    - status: Filter by status (optional)
    - limit: Number of results (default: 20)
    - offset: Pagination offset (default: 0)
    """
    try:
        processor = get_podcast_processor()
        
        # Get all jobs
        all_jobs = [job.to_dict() for job in processor.jobs.values()]
        
        # Filter by status
        if status:
            all_jobs = [j for j in all_jobs if j["status"] == status]
        
        # Sort by creation time (newest first)
        all_jobs.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Paginate
        paginated_jobs = all_jobs[offset:offset + limit]
        
        return {
            "jobs": paginated_jobs,
            "total": len(all_jobs),
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"List jobs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_podcast_config():
    """
    Get podcast processing configuration
    """
    return {
        "supported_formats": SUPPORTED_FORMATS,
        "max_file_size_mb": 500,
        "output_directory": PODCAST_DIR,
        "features": {
            "transcription": True,
            "speaker_diarization": True,
            "analysis": True,
            "audio_summary": True,
            "qa_generation": True
        }
    }
