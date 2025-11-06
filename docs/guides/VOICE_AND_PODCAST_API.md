# Voice and Podcast Features - API Documentation

## Overview

This document provides comprehensive API documentation for the Voice Chat and Podcast Summarization features of the Strands Agent Chatbot.

---

## Voice Chat API

### Base URL
- **Local Development:** `ws://localhost:8000/voice`
- **Production:** `wss://your-domain.com/api/voice`

### WebSocket Endpoints

#### 1. Voice Streaming

**Endpoint:** `GET /voice/stream`

**WebSocket Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/voice/stream?session_id=xxx');
```

**Client → Server Messages:**

```json
// Start recording
{
  "type": "start_recording"
}

// Send audio chunk
{
  "type": "audio",
  "data": "base64_encoded_audio_data"
}

// Stop recording and process
{
  "type": "stop_recording"
}

// Send text message with optional audio response
{
  "type": "text_message",
  "text": "Hello, how are you?",
  "generate_audio": true
}

// Keepalive ping
{
  "type": "ping"
}
```

**Server → Client Messages:**

```json
// Ready message
{
  "type": "ready",
  "session_id": "voice_abc123",
  "message": "Voice chat ready"
}

// Recording started
{
  "type": "recording_started",
  "message": "Recording started"
}

// Partial transcription (real-time)
{
  "type": "transcription",
  "text": "Hello world",
  "is_final": false
}

// Final transcription
{
  "type": "transcription",
  "text": "Hello world, how are you?",
  "is_final": true
}

// Processing indicator
{
  "type": "processing",
  "message": "Thinking..."
}

// Text response
{
  "type": "response_text",
  "text": "I'm doing great, thank you for asking!"
}

// Audio response
{
  "type": "audio_response",
  "audio": "base64_encoded_audio",
  "format": "mp3"
}

// Error
{
  "type": "error",
  "message": "Error description"
}

// Pong (keepalive response)
{
  "type": "pong"
}
```

---

### REST Endpoints

#### 2. Synthesize Speech

**Endpoint:** `POST /voice/synthesize`

**Description:** Convert text to speech (non-streaming)

**Request:**
```json
{
  "text": "Hello, world! This is a test.",
  "voice_id": "Joanna",  // optional
  "use_ssml": false      // optional
}
```

**Response:**
```json
{
  "audio": "base64_encoded_mp3_data",
  "format": "mp3",
  "voice_id": "Joanna"
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from the API!",
    "voice_id": "Matthew"
  }'
```

**Example (JavaScript):**
```javascript
const response = await fetch('/voice/synthesize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Hello, world!',
    voice_id: 'Joanna'
  })
});

const data = await response.json();
const audioBlob = new Blob([
  Uint8Array.from(atob(data.audio), c => c.charCodeAt(0))
], { type: 'audio/mpeg' });
const audioUrl = URL.createObjectURL(audioBlob);
const audio = new Audio(audioUrl);
audio.play();
```

---

#### 3. Synthesize Speech (Streaming)

**Endpoint:** `POST /voice/synthesize/stream`

**Description:** Convert text to speech with streaming audio chunks

**Request:**
```json
{
  "text": "Long text to be converted to speech...",
  "voice_id": "Matthew"  // optional
}
```

**Response:** Server-Sent Events (SSE)

**SSE Events:**
```
data: {"audio": "chunk1_base64", "format": "mp3"}

data: {"audio": "chunk2_base64", "format": "mp3"}

data: {"type": "complete"}
```

**Example (JavaScript):**
```javascript
const eventSource = new EventSource('/voice/synthesize/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Hello, world!', voice_id: 'Joanna' })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'complete') {
    eventSource.close();
  } else if (data.audio) {
    // Play audio chunk
    playAudioChunk(data.audio);
  }
};
```

---

#### 4. Get Available Voices

**Endpoint:** `GET /voice/voices`

**Query Parameters:**
- `language_code` (optional): Filter by language (e.g., `en-US`)
- `neural_only` (optional): Only neural voices (default: `true`)

**Response:**
```json
{
  "voices": [
    {
      "Id": "Joanna",
      "Name": "Joanna",
      "LanguageCode": "en-US",
      "Gender": "Female",
      "SupportedEngines": ["standard", "neural"]
    },
    {
      "Id": "Matthew",
      "Name": "Matthew",
      "LanguageCode": "en-US",
      "Gender": "Male",
      "SupportedEngines": ["standard", "neural"]
    }
  ],
  "count": 2
}
```

**Example:**
```bash
curl "http://localhost:8000/voice/voices?language_code=en-US&neural_only=true"
```

---

#### 5. Get Voice Configuration

**Endpoint:** `GET /voice/config`

**Response:**
```json
{
  "transcription": {
    "language_code": "en-US",
    "sample_rate": 16000,
    "partial_results": true
  },
  "tts": {
    "voice_id": "Joanna",
    "engine": "neural",
    "output_format": "mp3",
    "sample_rate": "16000"
  },
  "recommended_voices": {
    "en-US": {
      "male": "Matthew",
      "female": "Joanna"
    }
  }
}
```

---

#### 6. Update Voice Configuration

**Endpoint:** `POST /voice/config`

**Request:**
```json
{
  "voice_id": "Matthew",
  "language_code": "en-US"
}
```

**Response:**
```json
{
  "message": "Configuration updated",
  "config": {
    // Updated configuration object
  }
}
```

---

## Podcast Summarization API

### Base URL
- **Local Development:** `http://localhost:8000/podcast`
- **Production:** `https://your-domain.com/api/podcast`

---

### Endpoints

#### 1. Upload Podcast

**Endpoint:** `POST /podcast/upload`

**Content-Type:** `multipart/form-data`

**Form Fields:**
- `file` (required): Audio file (MP3, WAV, M4A, FLAC, OGG)
- `title` (required): Podcast title
- `description` (optional): Podcast description

**Headers:**
- `X-Session-ID` (optional): Session identifier

**Response:**
```json
{
  "job_id": "podcast_abc123",
  "status": "uploaded",
  "message": "Podcast uploaded successfully. Processing started.",
  "file_size": 15728640,
  "filename": "podcast_abc123.mp3"
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/podcast/upload \
  -F "file=@my_podcast.mp3" \
  -F "title=Episode 42: AI and the Future" \
  -F "description=Discussion about AI trends"
```

**Example (JavaScript):**
```javascript
const formData = new FormData();
formData.append('file', audioFile);
formData.append('title', 'My Podcast Episode');
formData.append('description', 'Episode description');

const response = await fetch('/podcast/upload', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('Job ID:', result.job_id);
```

**Constraints:**
- Maximum file size: 500MB
- Supported formats: MP3, WAV, M4A, FLAC, OGG

---

#### 2. Get Podcast Processing Status

**Endpoint:** `GET /podcast/{job_id}/status`

**Response:**
```json
{
  "job_id": "podcast_abc123",
  "title": "Episode 42: AI and the Future",
  "status": "analyzing",
  "progress": 65,
  "created_at": "2025-11-06T12:00:00",
  "completed_at": null,
  "error": null,
  "has_transcription": true,
  "has_analysis": false,
  "has_audio_summary": false
}
```

**Status Values:**
- `uploaded`: File uploaded, waiting to start
- `transcribing`: Audio being transcribed
- `analyzing`: Content being analyzed
- `generating_audio`: Creating audio summary
- `completed`: Processing complete
- `failed`: Processing failed

**Example:**
```bash
curl http://localhost:8000/podcast/podcast_abc123/status
```

**Polling Example (JavaScript):**
```javascript
async function pollStatus(jobId) {
  const response = await fetch(`/podcast/${jobId}/status`);
  const status = await response.json();
  
  if (status.status === 'completed') {
    // Fetch results
    fetchResults(jobId);
  } else if (status.status === 'failed') {
    console.error('Processing failed:', status.error);
  } else {
    // Continue polling
    setTimeout(() => pollStatus(jobId), 5000);
  }
}
```

---

#### 3. Get Podcast Results

**Endpoint:** `GET /podcast/{job_id}/results`

**Response:**
```json
{
  "job_id": "podcast_abc123",
  "title": "Episode 42: AI and the Future",
  "status": "completed",
  "transcription": {
    "full_text": "Welcome to our podcast...",
    "segments": [
      {
        "speaker": "Speaker 1",
        "start_time": 0.0,
        "end_time": 15.5,
        "text": "Welcome to our podcast!"
      }
    ]
  },
  "analysis": {
    "quick_summary": "This episode discusses...",
    "detailed_summary": "In this comprehensive discussion...",
    "key_topics": [
      "Artificial Intelligence",
      "Machine Learning",
      "Future Trends"
    ],
    "main_takeaways": [
      "AI is transforming industries",
      "Ethical considerations are crucial"
    ],
    "duration_seconds": 3600,
    "speaker_count": 2
  },
  "audio_summary_path": "/output/podcasts/podcast_abc123_summary.mp3",
  "created_at": "2025-11-06T12:00:00",
  "completed_at": "2025-11-06T12:15:00"
}
```

**Example:**
```bash
curl http://localhost:8000/podcast/podcast_abc123/results
```

---

#### 4. Get Audio Summary

**Endpoint:** `GET /podcast/{job_id}/audio-summary`

**Response:** MP3 audio file

**Example:**
```bash
curl http://localhost:8000/podcast/podcast_abc123/audio-summary -o summary.mp3
```

**Example (JavaScript):**
```javascript
const audio = new Audio(`/podcast/${jobId}/audio-summary`);
audio.play();
```

---

#### 5. Get Transcription

**Endpoint:** `GET /podcast/{job_id}/transcription`

**Query Parameters:**
- `format` (optional): `json` (default) or `text`

**Response (JSON format):**
```json
{
  "full_text": "Complete transcription...",
  "segments": [...]
}
```

**Response (text format):**
```json
{
  "text": "Complete transcription as plain text..."
}
```

**Example:**
```bash
# Get full JSON
curl http://localhost:8000/podcast/podcast_abc123/transcription

# Get plain text only
curl "http://localhost:8000/podcast/podcast_abc123/transcription?format=text"
```

---

#### 6. Regenerate Audio Summary

**Endpoint:** `POST /podcast/{job_id}/regenerate-audio`

**Request:**
```json
{
  "voice_id": "Matthew"
}
```

**Response:**
```json
{
  "message": "Audio summary regenerated",
  "voice_id": "Matthew",
  "audio_url": "/api/podcast/podcast_abc123/audio-summary"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/podcast/podcast_abc123/regenerate-audio \
  -H "Content-Type: application/json" \
  -d '{"voice_id": "Joanna"}'
```

---

#### 7. List Podcast Jobs

**Endpoint:** `GET /podcast/jobs/list`

**Query Parameters:**
- `status` (optional): Filter by status
- `limit` (optional): Number of results (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "podcast_abc123",
      "title": "Episode 42",
      "status": "completed",
      "progress": 100,
      "created_at": "2025-11-06T12:00:00",
      "completed_at": "2025-11-06T12:15:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Example:**
```bash
# Get all completed jobs
curl "http://localhost:8000/podcast/jobs/list?status=completed"

# Paginate results
curl "http://localhost:8000/podcast/jobs/list?limit=10&offset=20"
```

---

#### 8. Delete Podcast Job

**Endpoint:** `DELETE /podcast/{job_id}`

**Response:**
```json
{
  "message": "Podcast job deleted successfully",
  "job_id": "podcast_abc123"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/podcast/podcast_abc123
```

---

#### 9. Get Podcast Configuration

**Endpoint:** `GET /podcast/config`

**Response:**
```json
{
  "supported_formats": [
    "audio/mpeg",
    "audio/wav",
    "audio/mp4",
    "audio/flac",
    "audio/ogg"
  ],
  "max_file_size_mb": 500,
  "output_directory": "output/podcasts",
  "features": {
    "transcription": true,
    "speaker_diarization": true,
    "analysis": true,
    "audio_summary": true,
    "qa_generation": true
  }
}
```

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "detail": "Error message description"
}
```

**Common HTTP Status Codes:**
- `400 Bad Request`: Invalid input or request format
- `404 Not Found`: Resource not found (job, file, etc.)
- `500 Internal Server Error`: Server-side error

**Example Error:**
```json
{
  "detail": "Unsupported file format: audio/x-wav. Supported: audio/mpeg, audio/wav, ..."
}
```

---

## Integration Examples

### Complete Voice Chat Flow

```javascript
class VoiceChat {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.ws = null;
    this.mediaRecorder = null;
  }

  async connect() {
    this.ws = new WebSocket(
      `ws://localhost:8000/voice/stream?session_id=${this.sessionId}`
    );

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };

    await new Promise((resolve) => {
      this.ws.onopen = resolve;
    });
  }

  async startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRecorder = new MediaRecorder(stream);

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        // Convert to base64 and send
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64Audio = reader.result.split(',')[1];
          this.ws.send(JSON.stringify({
            type: 'audio',
            data: base64Audio
          }));
        };
        reader.readAsDataURL(event.data);
      }
    };

    this.ws.send(JSON.stringify({ type: 'start_recording' }));
    this.mediaRecorder.start(100); // 100ms chunks
  }

  stopRecording() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.ws.send(JSON.stringify({ type: 'stop_recording' }));
    }
  }

  handleMessage(data) {
    switch (data.type) {
      case 'transcription':
        console.log('Transcription:', data.text);
        if (data.is_final) {
          console.log('Final transcription:', data.text);
        }
        break;

      case 'audio_response':
        this.playAudio(data.audio);
        break;

      case 'error':
        console.error('Error:', data.message);
        break;
    }
  }

  playAudio(base64Audio) {
    const audioBlob = new Blob([
      Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0))
    ], { type: 'audio/mpeg' });
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.play();
  }
}

// Usage
const voiceChat = new VoiceChat('my-session-id');
await voiceChat.connect();
voiceChat.startRecording();
// ... speak ...
voiceChat.stopRecording();
```

---

### Complete Podcast Processing Flow

```javascript
class PodcastProcessor {
  async uploadPodcast(file, title, description) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('description', description);

    const response = await fetch('/podcast/upload', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();
    return result.job_id;
  }

  async waitForCompletion(jobId) {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        const response = await fetch(`/podcast/${jobId}/status`);
        const status = await response.json();

        console.log(`Progress: ${status.progress}% - ${status.status}`);

        if (status.status === 'completed') {
          resolve(jobId);
        } else if (status.status === 'failed') {
          reject(new Error(status.error));
        } else {
          setTimeout(poll, 5000); // Poll every 5 seconds
        }
      };
      poll();
    });
  }

  async getResults(jobId) {
    const response = await fetch(`/podcast/${jobId}/results`);
    return await response.json();
  }

  async playAudioSummary(jobId) {
    const audio = new Audio(`/podcast/${jobId}/audio-summary`);
    audio.play();
  }
}

// Usage
const processor = new PodcastProcessor();

// Upload
const jobId = await processor.uploadPodcast(
  audioFile,
  'My Podcast Episode',
  'Episode description'
);

console.log('Upload started, job ID:', jobId);

// Wait for completion
await processor.waitForCompletion(jobId);

// Get results
const results = await processor.getResults(jobId);
console.log('Summary:', results.analysis.quick_summary);
console.log('Topics:', results.analysis.key_topics);

// Play audio summary
await processor.playAudioSummary(jobId);
```

---

## Rate Limits and Quotas

- **Voice WebSocket Connections:** Max 10 concurrent per session
- **Podcast Upload:** Max 500MB per file
- **Podcast Processing:** Max 5 concurrent jobs per session
- **API Rate Limit:** 100 requests per minute per IP

---

## Best Practices

### Voice Chat
1. **Handle connection drops gracefully** - Implement reconnection logic
2. **Buffer audio appropriately** - Use 100-500ms chunks
3. **Provide visual feedback** - Show recording/processing indicators
4. **Handle permissions** - Request microphone access with proper UI
5. **Test latency** - Monitor round-trip times and optimize

### Podcast Processing
1. **Validate files client-side** - Check format and size before upload
2. **Implement progress tracking** - Poll status regularly
3. **Cache results** - Store transcriptions locally if needed
4. **Handle failures gracefully** - Provide retry mechanisms
5. **Optimize for long files** - Show estimated completion times

---

## Support

For issues or questions:
- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Review [VOICE_AND_PODCAST_ARCHITECTURE.md](./VOICE_AND_PODCAST_ARCHITECTURE.md)
- Contact support or open an issue

---

## Version History

- **v1.0.0** (2025-11-06): Initial release
  - Voice chat with WebSocket support
  - Podcast transcription and analysis
  - Audio summary generation
  - REST API endpoints
