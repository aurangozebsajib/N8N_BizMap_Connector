# N8N BizMap Connector & Bangla AI Video Factory

An AI-driven video planning and marketing automation connector for BizMap, designed to run with n8n, Google Docs/Sheets, and local/cloud video pipelines.

## Features
- **Bangla Dialect Transformation**: Automatic conversion between standard Bengali and regional dialects (`rangpuri`, `barishal`, `old-dhaka`, or `auto`).
- **Story Planner & Segmentation**: Chunks marketing stories into optimal storyboard segments (~20-35 words per segment, 2.5 words/second planned audio duration).
- **Video Type Classification**: Automatically maps segments into `text-animation` (for core lessons, stats, and quotes), `image-to-video` (for main protagonist/character scenes), and `text-to-video` (for environmental scenes).
- **Character Design Engine**: Automatically generates fictional stylized protagonists or hosts (with consistent appearance, age, attire, color palette).
- **Audio TTS Narration Lab**: Splits narration scripts into sentence-bounded TTS chunks (≤ 400 characters) compatible with gTTS/EdgeTTS with browser voice synthesis playback.
- **Storyboard Scene Visualizer**: Live animated previews with Ken Burns camera motion effects, kinetic Bengali typography, and sound design cue tags.
- **N8N & Telegram Dispatcher**: Dispatches `plan.json`, `audio_meta.json`, and `manifest.json` payloads to n8n webhook workflows and Telegram channels.

## Development & Execution

```bash
npm install
npm run dev
```

Runs on port 3000 (`http://0.0.0.0:3000`).

## Environment Variables
See `.env.example`:
- `GEMINI_API_KEY`: Optional API key for Google Gemini generative planning.
- `N8N_WEBHOOK_URL`: Target webhook for n8n workflow triggers.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHANNEL_ID`: Optional credentials for Telegram dispatch.
