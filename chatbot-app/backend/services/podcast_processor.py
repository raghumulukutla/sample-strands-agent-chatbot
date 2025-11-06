"""
Podcast Processing Service - Complete pipeline for podcast analysis and summarization
"""
import asyncio
import logging
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from services.transcription import BatchTranscriptionService
from services.text_to_speech import LongFormSynthesisService, TextToSpeechService
from agent import ChatbotAgent

logger = logging.getLogger(__name__)


class PodcastJob:
    """Represents a podcast processing job"""
    
    STATUS_UPLOADED = "uploaded"
    STATUS_TRANSCRIBING = "transcribing"
    STATUS_ANALYZING = "analyzing"
    STATUS_GENERATING_AUDIO = "generating_audio"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    
    def __init__(self, job_id: str, title: str, audio_path: str):
        self.job_id = job_id
        self.title = title
        self.audio_path = audio_path
        self.status = self.STATUS_UPLOADED
        self.progress = 0
        self.created_at = datetime.utcnow().isoformat()
        self.completed_at = None
        self.error = None
        
        # Results
        self.transcription = None
        self.analysis = None
        self.audio_summary_path = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "has_transcription": self.transcription is not None,
            "has_analysis": self.analysis is not None,
            "has_audio_summary": self.audio_summary_path is not None
        }


class PodcastProcessor:
    """Processes podcasts: transcription → analysis → audio summary"""
    
    def __init__(
        self,
        transcription_service: Optional[BatchTranscriptionService] = None,
        tts_service: Optional[TextToSpeechService] = None,
        output_dir: str = "output/podcasts"
    ):
        """
        Initialize podcast processor
        
        Args:
            transcription_service: Batch transcription service
            tts_service: Text-to-speech service
            output_dir: Directory for output files
        """
        self.transcription_service = transcription_service or BatchTranscriptionService()
        self.tts_service = tts_service or TextToSpeechService()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Job tracking
        self.jobs: Dict[str, PodcastJob] = {}
    
    async def create_job(
        self,
        audio_path: str,
        title: str,
        description: Optional[str] = None
    ) -> str:
        """
        Create a new podcast processing job
        
        Args:
            audio_path: Path to audio file
            title: Podcast title
            description: Optional description
            
        Returns:
            Job ID
        """
        job_id = f"podcast_{uuid.uuid4().hex[:12]}"
        job = PodcastJob(job_id, title, audio_path)
        self.jobs[job_id] = job
        
        # Start processing in background
        asyncio.create_task(self._process_podcast(job_id))
        
        return job_id
    
    async def _process_podcast(self, job_id: str):
        """Process podcast through complete pipeline"""
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            # Step 1: Transcription
            logger.info(f"Starting transcription for {job_id}")
            job.status = PodcastJob.STATUS_TRANSCRIBING
            job.progress = 10
            
            transcription_result = await self._transcribe_podcast(job)
            job.transcription = transcription_result
            job.progress = 40
            
            # Step 2: Analysis
            logger.info(f"Starting analysis for {job_id}")
            job.status = PodcastJob.STATUS_ANALYZING
            job.progress = 50
            
            analysis_result = await self._analyze_podcast(job, transcription_result)
            job.analysis = analysis_result
            job.progress = 80
            
            # Step 3: Audio Summary Generation
            logger.info(f"Generating audio summary for {job_id}")
            job.status = PodcastJob.STATUS_GENERATING_AUDIO
            job.progress = 85
            
            audio_path = await self._generate_audio_summary(job, analysis_result)
            job.audio_summary_path = audio_path
            job.progress = 100
            
            # Complete
            job.status = PodcastJob.STATUS_COMPLETED
            job.completed_at = datetime.utcnow().isoformat()
            
            logger.info(f"Podcast processing completed for {job_id}")
            
        except Exception as e:
            logger.error(f"Podcast processing failed for {job_id}: {e}")
            job.status = PodcastJob.STATUS_FAILED
            job.error = str(e)
    
    async def _transcribe_podcast(self, job: PodcastJob) -> Dict[str, Any]:
        """Transcribe podcast audio"""
        try:
            # Upload to S3 if needed (for now, use local file)
            # In production, upload to S3 first
            audio_uri = f"file://{os.path.abspath(job.audio_path)}"
            
            # For demo, create mock transcription
            # In production, use:
            # job_name = f"transcribe_{job.job_id}"
            # transcribe_job = await self.transcription_service.start_transcription_job(
            #     job_name=job_name,
            #     audio_uri=audio_uri,
            #     enable_speaker_diarization=True
            # )
            # await self.transcription_service.wait_for_job_completion(job_name)
            # result = await self.transcription_service.get_transcription_result(job_name)
            
            # Mock result for demo
            result = {
                "full_text": "This is a sample transcription. In production, this would contain the full podcast transcript.",
                "segments": [
                    {
                        "speaker": "Speaker 1",
                        "start_time": 0.0,
                        "end_time": 15.0,
                        "text": "Welcome to our podcast!"
                    }
                ]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def _analyze_podcast(
        self,
        job: PodcastJob,
        transcription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze podcast content and generate summaries"""
        try:
            full_text = transcription.get("full_text", "")
            segments = transcription.get("segments", [])
            
            # Create analysis prompt
            analysis_prompt = self._create_analysis_prompt(full_text, segments)
            
            # Use a temporary agent for analysis
            # In production, integrate with existing session manager
            from session.global_session_registry import global_session_registry
            session_id = f"podcast_analysis_{job.job_id}"
            _, session_manager, agent = global_session_registry.get_or_create_session(session_id)
            
            # Get analysis from agent
            response = await agent.invoke_async(analysis_prompt)
            
            # Parse response (assuming structured output)
            analysis = self._parse_analysis_response(str(response), transcription)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
    
    def _create_analysis_prompt(self, full_text: str, segments: List[Dict]) -> str:
        """Create analysis prompt for agent"""
        return f"""Analyze the following podcast transcript and provide:

1. A quick summary (2-3 sentences)
2. A detailed summary (5-10 sentences)
3. Key topics and themes (list of 5-10 topics)
4. Important quotes (3-5 notable quotes with context)
5. Main takeaways (3-5 key points)

Podcast Transcript:
{full_text[:5000]}  # Limit to avoid token limits

Please format your response as a structured analysis."""
    
    def _parse_analysis_response(
        self,
        response_text: str,
        transcription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse agent response into structured analysis"""
        # Simple parsing - in production, use structured output or JSON mode
        return {
            "quick_summary": self._extract_section(response_text, "quick summary"),
            "detailed_summary": self._extract_section(response_text, "detailed summary"),
            "key_topics": self._extract_list_items(response_text),
            "main_takeaways": self._extract_list_items(response_text),
            "full_analysis": response_text,
            "duration_seconds": self._calculate_duration(transcription),
            "speaker_count": len(set(s.get("speaker") for s in transcription.get("segments", [])))
        }
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract section from analysis text"""
        # Simple extraction - improve in production
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if section_name.lower() in line.lower():
                # Get next few lines
                section_lines = []
                for j in range(i+1, min(i+6, len(lines))):
                    if lines[j].strip():
                        section_lines.append(lines[j].strip())
                    else:
                        break
                return " ".join(section_lines)
        return text[:200]  # Fallback
    
    def _extract_list_items(self, text: str) -> List[str]:
        """Extract list items from text"""
        items = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*") or line.startswith("•"):
                items.append(line.lstrip("-*• ").strip())
        return items[:10]  # Limit items
    
    def _calculate_duration(self, transcription: Dict[str, Any]) -> float:
        """Calculate podcast duration from transcription"""
        segments = transcription.get("segments", [])
        if not segments:
            return 0.0
        return max(s.get("end_time", 0) for s in segments)
    
    async def _generate_audio_summary(
        self,
        job: PodcastJob,
        analysis: Dict[str, Any]
    ) -> str:
        """Generate audio summary of podcast"""
        try:
            # Create narration script
            script = self._create_summary_script(job.title, analysis)
            
            # Generate audio
            audio_filename = f"{job.job_id}_summary.mp3"
            audio_path = os.path.join(self.output_dir, audio_filename)
            
            audio_data = await self.tts_service.synthesize_speech(
                text=script,
                voice_id="Matthew",  # Use male voice for summaries
                use_ssml=False
            )
            
            # Save audio file
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            
            logger.info(f"Audio summary saved to {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Audio summary generation failed: {e}")
            raise
    
    def _create_summary_script(self, title: str, analysis: Dict[str, Any]) -> str:
        """Create narration script for audio summary"""
        script = f"""Welcome to the AI-generated summary of {title}.

Here's a quick overview: {analysis.get('quick_summary', 'Summary not available.')}

The main takeaways from this episode are:
"""
        
        for i, takeaway in enumerate(analysis.get('main_takeaways', [])[:5], 1):
            script += f"\n{i}. {takeaway}"
        
        script += "\n\nFor more details, please refer to the full transcript and analysis. Thank you for listening!"
        
        return script
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None
    
    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get complete job results"""
        job = self.jobs.get(job_id)
        if not job or job.status != PodcastJob.STATUS_COMPLETED:
            return None
        
        return {
            "job_id": job.job_id,
            "title": job.title,
            "status": job.status,
            "transcription": job.transcription,
            "analysis": job.analysis,
            "audio_summary_path": job.audio_summary_path,
            "created_at": job.created_at,
            "completed_at": job.completed_at
        }


# Global processor instance
_podcast_processor = None


def get_podcast_processor() -> PodcastProcessor:
    """Get or create global podcast processor"""
    global _podcast_processor
    if _podcast_processor is None:
        _podcast_processor = PodcastProcessor()
    return _podcast_processor
