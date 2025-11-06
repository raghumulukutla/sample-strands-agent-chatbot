"""
Amazon Transcribe Streaming Service for Real-time Speech-to-Text
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any
import boto3
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent, TranscriptResultStream
import soundfile as sf
import io

logger = logging.getLogger(__name__)


class TranscriptionEventHandler(TranscriptResultStreamHandler):
    """Handler for processing transcription events"""
    
    def __init__(self, transcript_result_stream: TranscriptResultStream, callback):
        super().__init__(transcript_result_stream)
        self.callback = callback
        self.partial_transcript = ""
        self.final_transcript = ""
    
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        """Process incoming transcript events"""
        results = transcript_event.transcript.results
        
        for result in results:
            if not result.alternatives:
                continue
            
            transcript = result.alternatives[0].transcript
            
            if result.is_partial:
                # Partial result - still being processed
                self.partial_transcript = transcript
                await self.callback({
                    "type": "partial",
                    "text": transcript,
                    "is_final": False
                })
            else:
                # Final result - complete utterance
                self.final_transcript += transcript + " "
                await self.callback({
                    "type": "final",
                    "text": transcript,
                    "is_final": True,
                    "full_text": self.final_transcript.strip()
                })


class TranscriptionService:
    """Service for real-time speech-to-text transcription using Amazon Transcribe"""
    
    def __init__(
        self,
        region_name: str = "us-west-2",
        language_code: str = "en-US",
        sample_rate: int = 16000,
        enable_partial_results: bool = True
    ):
        """
        Initialize transcription service
        
        Args:
            region_name: AWS region for Transcribe service
            language_code: Language code for transcription (e.g., 'en-US', 'es-US')
            sample_rate: Audio sample rate in Hz (8000 or 16000)
            enable_partial_results: Return partial transcriptions in real-time
        """
        self.region_name = region_name
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.enable_partial_results = enable_partial_results
        self.client = None
        
    def _get_client(self) -> TranscribeStreamingClient:
        """Get or create Transcribe Streaming client"""
        if not self.client:
            self.client = TranscribeStreamingClient(region=self.region_name)
        return self.client
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        callback: Optional[callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transcribe audio stream in real-time
        
        Args:
            audio_stream: Async generator yielding audio chunks (PCM format)
            callback: Optional callback for handling transcription events
            
        Yields:
            Transcription events with type, text, and metadata
        """
        try:
            client = self._get_client()
            
            # Create audio stream for Transcribe
            async def audio_generator():
                async for chunk in audio_stream:
                    yield chunk
            
            # Start transcription stream
            stream = await client.start_stream_transcription(
                language_code=self.language_code,
                media_sample_rate_hz=self.sample_rate,
                media_encoding="pcm",
                enable_partial_results_stabilization=self.enable_partial_results,
                partial_results_stability="high"
            )
            
            # Create event handler
            async def event_callback(event):
                if callback:
                    await callback(event)
                yield event
            
            handler = TranscriptionEventHandler(
                stream.output_stream,
                event_callback
            )
            
            # Process audio stream
            await asyncio.gather(
                self._write_audio_chunks(stream.input_stream, audio_generator()),
                handler.handle_events()
            )
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }
    
    async def _write_audio_chunks(self, input_stream, audio_generator):
        """Write audio chunks to the input stream"""
        try:
            async for chunk in audio_generator:
                await input_stream.send_audio_event(audio_chunk=chunk)
            await input_stream.end_stream()
        except Exception as e:
            logger.error(f"Error writing audio chunks: {e}")
    
    async def transcribe_audio_buffer(
        self,
        audio_data: bytes,
        audio_format: str = "wav"
    ) -> str:
        """
        Transcribe complete audio buffer (batch mode)
        
        Args:
            audio_data: Audio data as bytes
            audio_format: Audio format ('wav', 'mp3', 'flac', etc.)
            
        Returns:
            Complete transcription text
        """
        try:
            # Convert audio to PCM if needed
            pcm_data = self._convert_to_pcm(audio_data, audio_format)
            
            # Create async generator from buffer
            async def buffer_generator():
                chunk_size = 1024 * 8  # 8KB chunks
                for i in range(0, len(pcm_data), chunk_size):
                    yield pcm_data[i:i + chunk_size]
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
            
            # Transcribe
            full_transcript = ""
            async for event in self.transcribe_stream(buffer_generator()):
                if event.get("type") == "final":
                    full_transcript = event.get("full_text", "")
            
            return full_transcript
            
        except Exception as e:
            logger.error(f"Buffer transcription error: {e}")
            return ""
    
    def _convert_to_pcm(self, audio_data: bytes, audio_format: str) -> bytes:
        """
        Convert audio data to PCM format
        
        Args:
            audio_data: Input audio bytes
            audio_format: Input audio format
            
        Returns:
            PCM audio bytes
        """
        try:
            # Use soundfile to read audio
            data, samplerate = sf.read(io.BytesIO(audio_data))
            
            # Resample if needed
            if samplerate != self.sample_rate:
                import scipy.signal
                num_samples = int(len(data) * self.sample_rate / samplerate)
                data = scipy.signal.resample(data, num_samples)
            
            # Convert to PCM bytes
            pcm_buffer = io.BytesIO()
            sf.write(pcm_buffer, data, self.sample_rate, format='WAV', subtype='PCM_16')
            pcm_buffer.seek(0)
            
            return pcm_buffer.read()
            
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return audio_data


class BatchTranscriptionService:
    """Service for batch transcription using Amazon Transcribe (for podcasts)"""
    
    def __init__(self, region_name: str = "us-west-2"):
        """
        Initialize batch transcription service
        
        Args:
            region_name: AWS region for Transcribe service
        """
        self.region_name = region_name
        self.client = boto3.client('transcribe', region_name=region_name)
        self.s3_client = boto3.client('s3', region_name=region_name)
    
    async def start_transcription_job(
        self,
        job_name: str,
        audio_uri: str,
        language_code: str = "en-US",
        output_bucket: Optional[str] = None,
        enable_speaker_diarization: bool = True,
        max_speaker_labels: int = 10
    ) -> Dict[str, Any]:
        """
        Start a batch transcription job
        
        Args:
            job_name: Unique job name
            audio_uri: S3 URI of audio file (s3://bucket/key)
            language_code: Language code
            output_bucket: S3 bucket for output (optional)
            enable_speaker_diarization: Identify different speakers
            max_speaker_labels: Maximum number of speakers
            
        Returns:
            Job information
        """
        try:
            params = {
                'TranscriptionJobName': job_name,
                'LanguageCode': language_code,
                'Media': {'MediaFileUri': audio_uri},
                'MediaFormat': self._detect_audio_format(audio_uri),
                'Settings': {}
            }
            
            # Add speaker diarization
            if enable_speaker_diarization:
                params['Settings']['ShowSpeakerLabels'] = True
                params['Settings']['MaxSpeakerLabels'] = max_speaker_labels
            
            # Add output location
            if output_bucket:
                params['OutputBucketName'] = output_bucket
            
            response = self.client.start_transcription_job(**params)
            return response['TranscriptionJob']
            
        except Exception as e:
            logger.error(f"Failed to start transcription job: {e}")
            raise
    
    async def get_transcription_job_status(self, job_name: str) -> Dict[str, Any]:
        """
        Get status of transcription job
        
        Args:
            job_name: Transcription job name
            
        Returns:
            Job status information
        """
        try:
            response = self.client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            return response['TranscriptionJob']
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            raise
    
    async def wait_for_job_completion(
        self,
        job_name: str,
        poll_interval: int = 5,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        Wait for transcription job to complete
        
        Args:
            job_name: Job name to monitor
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds
            
        Returns:
            Completed job information
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            job = await self.get_transcription_job_status(job_name)
            status = job['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                return job
            elif status == 'FAILED':
                raise Exception(f"Transcription job failed: {job.get('FailureReason')}")
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Transcription job timed out after {timeout}s")
            
            await asyncio.sleep(poll_interval)
    
    async def get_transcription_result(self, job_name: str) -> Dict[str, Any]:
        """
        Get transcription result
        
        Args:
            job_name: Job name
            
        Returns:
            Transcription result with text and metadata
        """
        try:
            job = await self.get_transcription_job_status(job_name)
            
            if job['TranscriptionJobStatus'] != 'COMPLETED':
                raise Exception(f"Job not completed: {job['TranscriptionJobStatus']}")
            
            # Download transcript JSON from S3
            transcript_uri = job['Transcript']['TranscriptFileUri']
            
            # Parse S3 URI and download
            import urllib.request
            with urllib.request.urlopen(transcript_uri) as response:
                transcript_data = response.read()
            
            import json
            transcript_json = json.loads(transcript_data)
            
            return self._parse_transcript(transcript_json)
            
        except Exception as e:
            logger.error(f"Failed to get transcription result: {e}")
            raise
    
    def _parse_transcript(self, transcript_json: Dict) -> Dict[str, Any]:
        """Parse Transcribe transcript JSON"""
        results = transcript_json.get('results', {})
        
        # Extract full transcript
        transcripts = results.get('transcripts', [])
        full_text = transcripts[0]['transcript'] if transcripts else ""
        
        # Extract segments with speaker labels and timestamps
        items = results.get('items', [])
        speaker_labels = results.get('speaker_labels', {})
        segments = speaker_labels.get('segments', [])
        
        parsed_segments = []
        for segment in segments:
            parsed_segments.append({
                'speaker': segment.get('speaker_label', 'Unknown'),
                'start_time': float(segment.get('start_time', 0)),
                'end_time': float(segment.get('end_time', 0)),
                'text': segment.get('transcript', '')
            })
        
        return {
            'full_text': full_text,
            'segments': parsed_segments,
            'items': items,
            'speaker_labels': speaker_labels
        }
    
    def _detect_audio_format(self, uri: str) -> str:
        """Detect audio format from URI"""
        uri_lower = uri.lower()
        if uri_lower.endswith('.mp3'):
            return 'mp3'
        elif uri_lower.endswith('.wav'):
            return 'wav'
        elif uri_lower.endswith('.flac'):
            return 'flac'
        elif uri_lower.endswith('.m4a') or uri_lower.endswith('.mp4'):
            return 'mp4'
        elif uri_lower.endswith('.ogg'):
            return 'ogg'
        else:
            return 'mp3'  # Default
