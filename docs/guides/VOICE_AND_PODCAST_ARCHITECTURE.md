# Voice and Podcast Features - Technical Architecture

## Overview
This document outlines the architecture for adding voice interaction and podcast summarization features to the Strands Agent Chatbot, leveraging state-of-the-art AWS speech and AI services.

## AWS Speech Services Analysis

### 1. Amazon Transcribe
**Capabilities:**
- Real-time streaming transcription (Amazon Transcribe Streaming)
- Batch transcription for long-form audio
- Support for multiple languages and dialects
- Custom vocabulary and language models
- Speaker diarization (identify multiple speakers)
- Automatic punctuation and formatting
- Medical and call analytics specialized versions

**Use Cases:**
- Real-time voice chat (voice-to-text)
- Podcast transcription (batch processing)
- Multi-speaker conversation analysis

**Latency:** ~500-1000ms for streaming mode

### 2. Amazon Polly
**Capabilities:**
- Neural Text-to-Speech (NTTS) with high-quality voices
- Standard TTS for faster, cost-effective synthesis
- Multiple languages and voices (50+ voices)
- SSML support for fine-grained control
- Speech marks for lip-sync and word highlighting
- Long-form synthesis (up to 200,000 characters per request)
- Newscaster and conversational speaking styles

**Use Cases:**
- Agent voice responses
- Podcast summary audio generation
- Natural voice playback

**Latency:** ~100-300ms for first audio chunk

### 3. Amazon Bedrock Multimodal (Nova Models)
**Capabilities:**
- Amazon Nova Premier: Multimodal understanding (text, image, video, audio)
- Native audio input/output support
- Context-aware audio generation
- Integrated with Claude and other foundation models
- Streaming support for real-time interactions

**Use Cases:**
- Advanced voice understanding with context
- Emotion and tone detection
- Complex audio reasoning tasks

**Status:** Recently announced, check availability in us-west-2

### 4. Amazon Bedrock Converse API with Audio
**Capabilities:**
- Unified API for text and audio conversations
- Seamless multimodal message handling
- Streaming audio responses
- Integration with existing Bedrock models

**Recommended Approach:** Primary choice for voice features

---

## Feature 1: Voice Chat

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Microphone  │───▶│ Audio Buffer │───▶│  WebSocket   │      │
│  │  Recorder    │    │  Management  │    │   Client     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │               │
│  ┌──────────────┐    ┌──────────────┐           │               │
│  │ Audio Player │◀───│ Audio Buffer │◀───────────┘               │
│  └──────────────┘    └──────────────┘                           │
└───────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Voice Router (/voice/stream)                 │  │
│  │  - WebSocket connection management                        │  │
│  │  - Session tracking and authentication                    │  │
│  │  - Audio format validation (PCM, Opus, etc.)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Voice Processing Service                       │  │
│  │  ┌───────────────────┐    ┌──────────────────────┐      │  │
│  │  │ Transcribe Stream │───▶│  Strands Agent       │      │  │
│  │  │   (STT Service)   │    │  Processing          │      │  │
│  │  └───────────────────┘    └──────────────────────┘      │  │
│  │                                     │                      │  │
│  │                                     ▼                      │  │
│  │  ┌───────────────────┐    ┌──────────────────────┐      │  │
│  │  │   Polly/Bedrock   │◀───│  Response Generator  │      │  │
│  │  │   (TTS Service)   │    │                      │      │  │
│  │  └───────────────────┘    └──────────────────────┘      │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Services                             │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │    Transcribe    │  │  Bedrock Claude  │  │    Polly     │ │
│  │    Streaming     │  │   Sonnet 4       │  │    Neural    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Components

#### 1. Backend Services

**Voice Router (`chatbot-app/backend/routers/voice.py`):**
- WebSocket endpoint for bidirectional audio streaming
- Session management integration
- Audio format handling (WebM, PCM, Opus)
- Real-time transcription buffering
- TTS audio streaming

**Transcription Service (`chatbot-app/backend/services/transcription.py`):**
- Amazon Transcribe Streaming client
- Real-time audio chunk processing
- Partial and final transcription handling
- Language detection
- Speaker diarization support

**Text-to-Speech Service (`chatbot-app/backend/services/text_to_speech.py`):**
- Amazon Polly Neural TTS client
- Voice selection (default: Joanna or Matthew)
- SSML processing for natural speech
- Audio format conversion (MP3/PCM)
- Streaming audio generation

#### 2. Frontend Components

**Voice Button Component (`src/components/VoiceButton.tsx`):**
```typescript
interface VoiceButtonProps {
  onTranscriptionComplete: (text: string) => void;
  onAudioResponse: (audioBlob: Blob) => void;
  isEnabled: boolean;
}
```

**Voice Recorder Hook (`src/hooks/useVoiceRecorder.ts`):**
- MediaRecorder API integration
- Audio permission handling
- Real-time audio streaming via WebSocket
- Voice activity detection (VAD)
- Recording state management

**Audio Player Component (`src/components/AudioPlayer.tsx`):**
- Audio playback controls
- Waveform visualization
- Speed control
- Download option

### Data Flow

1. **User initiates voice input:**
   - Frontend requests microphone permission
   - User presses "Push to Talk" or "Toggle Voice" button
   - Audio recording starts via MediaRecorder API

2. **Real-time audio streaming:**
   - Audio chunks (100-500ms) sent via WebSocket
   - Backend forwards to Transcribe Streaming API
   - Partial transcriptions returned to frontend
   - Real-time text display updates

3. **Agent processing:**
   - Final transcription sent to Strands Agent
   - Agent processes with existing tools and MCP servers
   - Response generated using Claude Sonnet 4

4. **Voice response:**
   - Agent response text sent to Polly/Bedrock TTS
   - Audio chunks streamed back to frontend
   - Audio player automatically plays response
   - Text response displayed simultaneously

### Configuration Options

**Voice Settings (model_config.json extension):**
```json
{
  "voice": {
    "enabled": true,
    "stt": {
      "service": "transcribe", // or "bedrock"
      "language_code": "en-US",
      "enable_speaker_diarization": false,
      "vocabulary_name": null
    },
    "tts": {
      "service": "polly", // or "bedrock"
      "voice_id": "Joanna", // Polly Neural voice
      "engine": "neural",
      "speaking_rate": "100%",
      "pitch": "+0%"
    },
    "streaming": {
      "chunk_size_ms": 200,
      "enable_vad": true,
      "silence_duration_ms": 1500
    }
  }
}
```

---

## Feature 2: Podcast Summarization

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Podcast    │───▶│  Progress    │───▶│   Results    │      │
│  │   Upload     │    │  Tracker     │    │   Display    │      │
│  │   (Drag/Drop)│    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │               │
│  ┌──────────────────────────────────────────────┼─────────────┐│
│  │          Results Panel                        │             ││
│  │  - Original Audio Player                      │             ││
│  │  - Transcription Text                         │             ││
│  │  - AI-Generated Summary (Text)                │             ││
│  │  - Summary Audio Player                       │             ││
│  │  - Key Topics & Timestamps                    │             ││
│  │  - Speaker Identification                     │             ││
│  │  - Download Options (JSON/PDF/Audio)          │             ││
│  └───────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Podcast Router (/podcast/*)                    │  │
│  │  - POST /podcast/upload                                   │  │
│  │  - GET  /podcast/{id}/status                              │  │
│  │  - GET  /podcast/{id}/results                             │  │
│  │  - POST /podcast/{id}/regenerate-audio                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Podcast Processing Pipeline                      │  │
│  │                                                            │  │
│  │  1. Upload & Storage                                      │  │
│  │     - S3 or local file storage                            │  │
│  │     - Audio format validation                             │  │
│  │     - Job creation and tracking                           │  │
│  │                                                            │  │
│  │  2. Transcription (Amazon Transcribe)                     │  │
│  │     - Batch transcription job                             │  │
│  │     - Speaker diarization                                 │  │
│  │     - Timestamp extraction                                │  │
│  │     - JSON output with metadata                           │  │
│  │                                                            │  │
│  │  3. Analysis & Summarization (Strands Agent)              │  │
│  │     - Podcast Analyzer Tool/Agent                         │  │
│  │     - Key topic extraction                                │  │
│  │     - Multi-level summaries:                              │  │
│  │       * Quick summary (1-2 paragraphs)                    │  │
│  │       * Detailed summary (5-10 paragraphs)                │  │
│  │       * Timestamped segments                              │  │
│  │     - Q&A generation                                      │  │
│  │     - Action items extraction                             │  │
│  │                                                            │  │
│  │  4. Audio Summary Generation (Polly/Bedrock)              │  │
│  │     - Natural voice synthesis                             │  │
│  │     - Podcast-style narration                             │  │
│  │     - Background music (optional)                         │  │
│  │                                                            │  │
│  │  5. Results Compilation                                   │  │
│  │     - JSON output with all data                           │  │
│  │     - PDF export generation                               │  │
│  │     - Audio file storage                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Services                             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Transcribe  │  │   Bedrock    │  │       Polly          │ │
│  │   (Batch)    │  │ Claude Sonnet│  │  (Long-form Audio)   │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  S3 Storage  │  │  Parameter   │                            │
│  │   (Optional) │  │    Store     │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Components

#### 1. Backend Services

**Podcast Router (`chatbot-app/backend/routers/podcast.py`):**
```python
@router.post("/upload")
async def upload_podcast(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    x_session_id: str = Header(...)
)

@router.get("/{podcast_id}/status")
async def get_podcast_status(podcast_id: str)

@router.get("/{podcast_id}/results")
async def get_podcast_results(podcast_id: str)

@router.post("/{podcast_id}/regenerate-audio")
async def regenerate_audio_summary(podcast_id: str, voice_id: str)
```

**Podcast Processing Service (`chatbot-app/backend/services/podcast_processor.py`):**
- Async job queue for long-running tasks
- Status tracking (UPLOADED → TRANSCRIBING → ANALYZING → GENERATING_AUDIO → COMPLETED)
- Error handling and retry logic
- Progress callbacks

**Podcast Analyzer Tool (`chatbot-app/backend/custom_tools/podcast_analyzer.py`):**
```python
@tool(
    name="podcast_analyzer",
    description="Analyze podcast transcription and generate summaries, key topics, and insights"
)
def analyze_podcast_content(
    transcription: str,
    speaker_labels: List[Dict],
    timestamps: List[Dict],
    analysis_depth: str = "detailed"
) -> Dict[str, Any]:
    """
    Uses Claude Sonnet 4 via Strands Agent to:
    - Generate multi-level summaries
    - Extract key topics and themes
    - Identify important quotes
    - Create Q&A pairs
    - Extract action items
    - Generate chapter markers
    """
    pass
```

#### 2. Frontend Components

**Podcast Upload Component (`src/components/PodcastUpload.tsx`):**
```typescript
interface PodcastUploadProps {
  onUploadComplete: (podcastId: string) => void;
  acceptedFormats: string[]; // ['audio/mp3', 'audio/wav', 'audio/m4a']
  maxSizeMB: number;
}
```

**Podcast Results Component (`src/components/PodcastResults.tsx`):**
- Tabbed interface (Summary / Transcript / Insights)
- Audio players for original and summary
- Timeline visualization with chapters
- Export options (PDF, JSON, TXT)

**Podcast Status Tracker (`src/components/PodcastStatusTracker.tsx`):**
- Real-time progress updates via polling
- Step-by-step status visualization
- Estimated time remaining
- Cancel option

### Data Flow

1. **Podcast Upload:**
   - User drags/drops or selects audio file
   - Frontend validates file (format, size)
   - POST to /podcast/upload with metadata
   - Backend creates job ID and starts processing

2. **Transcription Phase:**
   - Audio file sent to Amazon Transcribe (batch)
   - Speaker diarization enabled
   - Transcribe job monitored for completion
   - Transcription JSON retrieved and parsed

3. **Analysis Phase:**
   - Transcription text sent to Podcast Analyzer Tool
   - Strands Agent processes with Claude Sonnet 4
   - Multiple analysis passes:
     - First pass: Overall structure and topics
     - Second pass: Detailed summary generation
     - Third pass: Q&A and insights extraction

4. **Audio Summary Generation:**
   - Summary text formatted for speech
   - SSML markup for natural pauses and emphasis
   - Sent to Amazon Polly with newscaster style
   - Audio chunks saved to file
   - MP3 file generated and stored

5. **Results Delivery:**
   - Frontend polls status endpoint
   - When completed, fetch results from /podcast/{id}/results
   - Display comprehensive results panel

### Podcast Analysis Output Structure

```json
{
  "podcast_id": "uuid",
  "metadata": {
    "title": "Example Podcast Episode",
    "duration_seconds": 3600,
    "upload_date": "2025-11-06T12:00:00Z",
    "speakers": ["Speaker 1", "Speaker 2"]
  },
  "transcription": {
    "full_text": "...",
    "segments": [
      {
        "speaker": "Speaker 1",
        "start_time": 0.0,
        "end_time": 15.5,
        "text": "Welcome to our podcast..."
      }
    ]
  },
  "summaries": {
    "quick": "1-2 paragraph overview",
    "detailed": "5-10 paragraph comprehensive summary",
    "executive": "Business-focused summary with key takeaways"
  },
  "key_topics": [
    {
      "topic": "AI in Healthcare",
      "relevance_score": 0.95,
      "timestamp": "00:15:30",
      "summary": "Discussion about AI applications..."
    }
  ],
  "chapters": [
    {
      "title": "Introduction",
      "start_time": "00:00:00",
      "end_time": "00:05:00",
      "summary": "..."
    }
  ],
  "highlights": [
    {
      "quote": "Important statement...",
      "speaker": "Speaker 1",
      "timestamp": "00:23:45",
      "context": "..."
    }
  ],
  "qa_pairs": [
    {
      "question": "What was discussed about AI?",
      "answer": "The speakers covered..."
    }
  ],
  "action_items": [
    "Research mentioned study",
    "Follow up with guest"
  ],
  "audio_summary": {
    "url": "/api/podcasts/uuid/audio-summary.mp3",
    "duration_seconds": 180,
    "voice_id": "Joanna"
  }
}
```

### Configuration Options

**Podcast Settings (model_config.json extension):**
```json
{
  "podcast": {
    "enabled": true,
    "transcription": {
      "service": "transcribe",
      "enable_speaker_diarization": true,
      "max_speakers": 10,
      "language_code": "en-US",
      "custom_vocabulary": null
    },
    "analysis": {
      "enable_qa_generation": true,
      "enable_action_items": true,
      "enable_chapter_detection": true,
      "summary_lengths": ["quick", "detailed", "executive"],
      "max_topics": 10
    },
    "audio_summary": {
      "generate_audio": true,
      "voice_id": "Matthew",
      "speaking_style": "newscaster",
      "max_duration_seconds": 300,
      "include_music": false
    },
    "storage": {
      "keep_original_audio": true,
      "keep_transcription": true,
      "retention_days": 30
    }
  }
}
```

---

## Implementation Priority

### Phase 1: Voice Chat (High Priority)
1. ✅ Basic voice recording and WebSocket setup
2. ✅ Amazon Transcribe Streaming integration
3. ✅ Amazon Polly TTS integration
4. ✅ Frontend voice UI components
5. ✅ Real-time streaming and buffering
6. ⚠️  Voice settings configuration

### Phase 2: Podcast Features (Medium Priority)
1. ✅ File upload and storage
2. ✅ Amazon Transcribe batch processing
3. ✅ Podcast analyzer tool development
4. ✅ Multi-level summary generation
5. ✅ Audio summary generation with Polly
6. ✅ Results display UI
7. ⚠️  Export functionality (PDF, JSON)

### Phase 3: Advanced Features (Future)
1. Emotion detection in voice
2. Multi-language support
3. Custom voice training (Polly Brand Voices)
4. Podcast search and indexing
5. Collaborative annotations
6. Background music mixing for summaries

---

## Cost Estimation

### Voice Chat (per 1000 interactions, avg 2 min conversation)
- **Transcribe Streaming:** $0.0240/min × 2min × 1000 = $48
- **Polly Neural TTS:** $0.016/1M chars × 500 chars × 1000 = $8
- **Bedrock Claude:** Existing usage + ~10% increase
- **Total:** ~$60-70 per 1000 conversations

### Podcast Processing (per 1-hour podcast)
- **Transcribe Batch:** $0.024/min × 60min = $1.44
- **Bedrock Claude (Analysis):** ~$0.50-1.00 (token-based)
- **Polly Long-form:** $0.016/1M chars × 5000 chars = $0.08
- **Total:** ~$2-3 per hour of podcast

---

## Security Considerations

1. **Audio Data Privacy:**
   - Encrypt audio in transit (WSS, HTTPS)
   - Temporary storage with automatic cleanup
   - No persistent audio storage without consent

2. **Rate Limiting:**
   - Limit voice recording duration (5 min max)
   - Podcast file size limits (500MB max)
   - Per-session request throttling

3. **Access Control:**
   - Session-based authentication
   - API key validation for AWS services
   - CORS configuration for voice endpoints

4. **Compliance:**
   - GDPR-compliant data retention
   - User consent for voice recording
   - Clear privacy policy updates

---

## Testing Strategy

### Voice Chat Testing
1. **Unit Tests:**
   - Audio format validation
   - WebSocket connection handling
   - Transcription accuracy

2. **Integration Tests:**
   - End-to-end voice conversation flow
   - Session management with voice
   - Tool execution with voice input

3. **Performance Tests:**
   - Latency measurement (target: <2s total)
   - Concurrent voice sessions
   - Audio buffer management

### Podcast Testing
1. **Unit Tests:**
   - File upload validation
   - Transcription job creation
   - Summary generation logic

2. **Integration Tests:**
   - Complete podcast processing pipeline
   - Error handling and retries
   - Multi-speaker detection accuracy

3. **User Acceptance Tests:**
   - Summary quality evaluation
   - Audio summary naturalness
   - UI/UX feedback

---

## Dependencies

### Python Packages (requirements.txt additions)
```
# Audio Processing
pydub>=0.25.1
boto3>=1.40.1  # Already present, ensure latest
amazon-transcribe>=0.6.0

# WebSocket Support
websockets>=11.0
python-multipart>=0.0.6  # Already present

# Audio Format Handling
soundfile>=0.12.1
librosa>=0.10.0  # Optional: for advanced audio analysis
```

### Frontend Packages (package.json additions)
```json
{
  "dependencies": {
    "recordrtc": "^5.6.2",
    "wavesurfer.js": "^7.0.0",
    "lamejs": "^1.2.1"
  }
}
```

### AWS Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "transcribe:StartStreamTranscription",
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob",
        "transcribe:ListTranscriptionJobs"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech",
        "polly:StartSpeechSynthesisTask",
        "polly:GetSpeechSynthesisTask"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::podcast-storage-bucket/*"
    }
  ]
}
```

---

## Next Steps

1. Review and approve architecture
2. Set up AWS service permissions
3. Begin Phase 1 implementation (Voice Chat)
4. Create feature branch: `feature/voice-and-podcast`
5. Implement backend services
6. Build frontend components
7. Integration testing
8. Documentation and deployment

---

## References

- [Amazon Transcribe Documentation](https://docs.aws.amazon.com/transcribe/)
- [Amazon Polly Documentation](https://docs.aws.amazon.com/polly/)
- [Amazon Bedrock Multimodal](https://docs.aws.amazon.com/bedrock/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Strands Agents Framework](https://github.com/aws-samples/strands-agents)

