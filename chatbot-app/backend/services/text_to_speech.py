"""
Amazon Polly Text-to-Speech Service for Natural Voice Synthesis
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any, List
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import io

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """Service for text-to-speech synthesis using Amazon Polly"""
    
    # Popular Neural voices
    NEURAL_VOICES = {
        'en-US': {
            'male': ['Matthew', 'Stephen', 'Kevin'],
            'female': ['Joanna', 'Kendra', 'Kimberly', 'Salli', 'Ruth']
        },
        'en-GB': {
            'male': ['Brian', 'Arthur'],
            'female': ['Amy', 'Emma']
        },
        'es-US': {
            'male': ['Pedro'],
            'female': ['Lupe']
        },
        'fr-FR': {
            'male': ['Mathieu', 'Léon'],
            'female': ['Léa']
        }
    }
    
    def __init__(
        self,
        region_name: str = "us-west-2",
        voice_id: str = "Joanna",
        engine: str = "neural",
        sample_rate: str = "16000",
        output_format: str = "mp3"
    ):
        """
        Initialize text-to-speech service
        
        Args:
            region_name: AWS region for Polly service
            voice_id: Voice ID to use (e.g., 'Joanna', 'Matthew')
            engine: Speech engine ('neural' or 'standard')
            sample_rate: Audio sample rate ('8000', '16000', '22050', '24000')
            output_format: Audio format ('mp3', 'ogg_vorbis', 'pcm')
        """
        self.region_name = region_name
        self.voice_id = voice_id
        self.engine = engine
        self.sample_rate = sample_rate
        self.output_format = output_format
        self.client = boto3.client('polly', region_name=region_name)
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        use_ssml: bool = False
    ) -> bytes:
        """
        Synthesize speech from text
        
        Args:
            text: Text to convert to speech
            voice_id: Override default voice ID
            use_ssml: Whether text contains SSML markup
            
        Returns:
            Audio data as bytes
        """
        try:
            params = {
                'Text': text,
                'OutputFormat': self.output_format,
                'VoiceId': voice_id or self.voice_id,
                'Engine': self.engine,
                'SampleRate': self.sample_rate,
                'TextType': 'ssml' if use_ssml else 'text'
            }
            
            # Run Polly synthesis in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.synthesize_speech(**params)
            )
            
            # Read audio stream
            audio_stream = response.get('AudioStream')
            if audio_stream:
                return audio_stream.read()
            else:
                raise Exception("No audio stream in response")
                
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Polly synthesis error: {e}")
            raise
    
    async def synthesize_speech_streaming(
        self,
        text: str,
        voice_id: Optional[str] = None,
        chunk_size: int = 1024
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize speech with streaming output
        
        Args:
            text: Text to convert to speech
            voice_id: Override default voice ID
            chunk_size: Size of audio chunks to yield
            
        Yields:
            Audio chunks as bytes
        """
        try:
            # Get full audio
            audio_data = await self.synthesize_speech(text, voice_id)
            
            # Stream in chunks
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]
                await asyncio.sleep(0.001)  # Small delay for streaming effect
                
        except Exception as e:
            logger.error(f"Streaming synthesis error: {e}")
            raise
    
    async def synthesize_with_marks(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize speech with speech marks for synchronization
        
        Args:
            text: Text to convert to speech
            voice_id: Override default voice ID
            
        Returns:
            Dictionary with audio data and speech marks
        """
        try:
            # Get audio
            audio_data = await self.synthesize_speech(text, voice_id)
            
            # Get speech marks (word timing information)
            marks_params = {
                'Text': text,
                'OutputFormat': 'json',
                'VoiceId': voice_id or self.voice_id,
                'Engine': self.engine,
                'SpeechMarkTypes': ['word', 'sentence']
            }
            
            loop = asyncio.get_event_loop()
            marks_response = await loop.run_in_executor(
                None,
                lambda: self.client.synthesize_speech(**marks_params)
            )
            
            # Parse speech marks
            marks_data = marks_response.get('AudioStream').read().decode('utf-8')
            marks = [eval(line) for line in marks_data.strip().split('\n')]
            
            return {
                'audio': audio_data,
                'marks': marks,
                'duration_ms': marks[-1]['time'] if marks else 0
            }
            
        except Exception as e:
            logger.error(f"Speech marks synthesis error: {e}")
            raise
    
    def create_ssml(
        self,
        text: str,
        speaking_rate: str = "100%",
        pitch: str = "+0%",
        volume: str = "default",
        pauses: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create SSML markup for enhanced speech control
        
        Args:
            text: Plain text to convert
            speaking_rate: Speaking rate (50%-200%)
            pitch: Pitch adjustment (-33% to +50%)
            volume: Volume level (silent, x-soft, soft, medium, loud, x-loud)
            pauses: List of pause locations {'after_word': 'hello', 'duration': '500ms'}
            
        Returns:
            SSML formatted string
        """
        ssml = f'<speak>'
        
        # Add prosody tags
        ssml += f'<prosody rate="{speaking_rate}" pitch="{pitch}" volume="{volume}">'
        
        # Add text with pauses
        if pauses:
            words = text.split()
            for i, word in enumerate(words):
                ssml += word + ' '
                for pause in pauses:
                    if pause.get('after_word') == word:
                        ssml += f'<break time="{pause.get("duration", "500ms")}"/>'
        else:
            ssml += text
        
        ssml += '</prosody></speak>'
        return ssml
    
    async def get_available_voices(
        self,
        language_code: Optional[str] = None,
        include_neural_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get list of available voices
        
        Args:
            language_code: Filter by language (e.g., 'en-US')
            include_neural_only: Only return neural voices
            
        Returns:
            List of voice information
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.client.describe_voices
            )
            
            voices = response.get('Voices', [])
            
            # Filter by language
            if language_code:
                voices = [v for v in voices if v['LanguageCode'] == language_code]
            
            # Filter by engine
            if include_neural_only:
                voices = [v for v in voices if 'neural' in v.get('SupportedEngines', [])]
            
            return voices
            
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []
    
    @staticmethod
    def get_recommended_voice(
        language_code: str = "en-US",
        gender: str = "female"
    ) -> str:
        """
        Get recommended voice for language and gender
        
        Args:
            language_code: Language code
            gender: 'male' or 'female'
            
        Returns:
            Voice ID
        """
        voices = TextToSpeechService.NEURAL_VOICES.get(language_code, {})
        voice_list = voices.get(gender, [])
        return voice_list[0] if voice_list else "Joanna"


class LongFormSynthesisService:
    """Service for long-form text-to-speech (for podcast summaries)"""
    
    def __init__(self, region_name: str = "us-west-2", output_bucket: Optional[str] = None):
        """
        Initialize long-form synthesis service
        
        Args:
            region_name: AWS region
            output_bucket: S3 bucket for output audio files
        """
        self.region_name = region_name
        self.output_bucket = output_bucket
        self.client = boto3.client('polly', region_name=region_name)
        self.s3_client = boto3.client('s3', region_name=region_name)
    
    async def start_synthesis_task(
        self,
        text: str,
        output_key: str,
        voice_id: str = "Matthew",
        engine: str = "neural",
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Start long-form synthesis task (for texts > 3000 characters)
        
        Args:
            text: Text to synthesize (up to 200,000 characters)
            output_key: S3 key for output file
            voice_id: Voice ID to use
            engine: Speech engine
            output_format: Audio format
            
        Returns:
            Task information
        """
        try:
            if not self.output_bucket:
                raise ValueError("Output bucket not configured for long-form synthesis")
            
            params = {
                'Text': text,
                'OutputFormat': output_format,
                'OutputS3BucketName': self.output_bucket,
                'OutputS3KeyPrefix': output_key,
                'VoiceId': voice_id,
                'Engine': engine,
                'TextType': 'text'
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.start_speech_synthesis_task(**params)
            )
            
            return response['SynthesisTask']
            
        except Exception as e:
            logger.error(f"Failed to start synthesis task: {e}")
            raise
    
    async def get_synthesis_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of synthesis task"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_speech_synthesis_task(TaskId=task_id)
            )
            return response['SynthesisTask']
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            raise
    
    async def wait_for_task_completion(
        self,
        task_id: str,
        poll_interval: int = 2,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Wait for synthesis task to complete"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            task = await self.get_synthesis_task_status(task_id)
            status = task['TaskStatus']
            
            if status == 'completed':
                return task
            elif status == 'failed':
                raise Exception(f"Synthesis task failed: {task.get('TaskStatusReason')}")
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Synthesis task timed out after {timeout}s")
            
            await asyncio.sleep(poll_interval)
    
    async def download_audio_file(self, task: Dict[str, Any], local_path: str) -> str:
        """
        Download synthesized audio file from S3
        
        Args:
            task: Completed synthesis task
            local_path: Local file path to save audio
            
        Returns:
            Local file path
        """
        try:
            output_uri = task.get('OutputUri')
            if not output_uri:
                raise ValueError("No output URI in task")
            
            # Parse S3 URI
            import urllib.parse
            parsed = urllib.parse.urlparse(output_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
            
            # Download from S3
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.download_file(bucket, key, local_path)
            )
            
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download audio file: {e}")
            raise
