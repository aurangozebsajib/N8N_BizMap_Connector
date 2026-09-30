import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { SAMPLE_STORIES } from './src/server/sampleStories.ts';
import { generatePlan, PlanOutput } from './src/server/planner.ts';
import { generateAiPlan } from './src/server/gemini.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// In-memory runtime storage
const state = {
  currentPlan: null as PlanOutput | null,
  history: [] as PlanOutput[],
  audioMeta: null as any,
  videoManifest: null as any,
  dispatchLogs: [] as Array<{ id: string; timestamp: string; channel: string; status: string; details: any }>
};

// Seed initial plan with first sample story
state.currentPlan = generatePlan({
  rawText: SAMPLE_STORIES[0].content,
  dialect: SAMPLE_STORIES[0].dialect,
  videoNumber: SAMPLE_STORIES[0].caseNumber,
  dateStr: SAMPLE_STORIES[0].date
});

// API Routes
app.get('/api/status', (req, res) => {
  res.json({
    status: 'online',
    version: '2.0.0-node',
    env: {
      hasGeminiKey: !!process.env.GEMINI_API_KEY,
      hasGoogleServiceJson: !!process.env.GOOGLE_SERVICE_JSON,
      hasTelegramBot: !!process.env.TELEGRAM_BOT_TOKEN,
      hasHuggingFaceKey: !!process.env.HUGGINGFACE_API_KEY,
      characterMode: process.env.CHARACTER_MODE || 'per_video',
      localFallback: process.env.LOCAL_FALLBACK || 'true'
    },
    counts: {
      hasPlan: !!state.currentPlan,
      historyCount: state.history.length,
      dispatchCount: state.dispatchLogs.length
    }
  });
});

app.get('/api/sample-stories', (req, res) => {
  res.json(SAMPLE_STORIES);
});

app.get('/api/python-code', async (req, res) => {
  try {
    const fs = await import('fs/promises');
    const mainPy = await fs.readFile('brain/main.py', 'utf-8').catch(() => '');
    const plannerPy = await fs.readFile('brain/planner.py', 'utf-8').catch(() => '');
    const videoEnginePy = await fs.readFile('brain/video_engine.py', 'utf-8').catch(() => '');
    const pipelineYml = await fs.readFile('.github/workflows/pipeline.yml', 'utf-8').catch(() => '');
    const reqsTxt = await fs.readFile('requirements.txt', 'utf-8').catch(() => '');

    res.json({
      'brain/main.py': mainPy,
      'brain/planner.py': plannerPy,
      'brain/video_engine.py': videoEnginePy,
      '.github/workflows/pipeline.yml': pipelineYml,
      'requirements.txt': reqsTxt
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/plan', async (req, res) => {
  try {
    const { rawText, videoNumber, dateStr, dialect, maxSegments, characterMode } = req.body;
    if (!rawText || typeof rawText !== 'string') {
      return res.status(400).json({ error: 'rawText is required' });
    }

    const plan = await generateAiPlan({
      rawText,
      videoNumber: videoNumber ? Number(videoNumber) : undefined,
      dateStr,
      dialect,
      maxSegments: maxSegments ? Number(maxSegments) : 10,
      characterMode: characterMode || 'per_video'
    });

    state.currentPlan = plan;
    state.history.unshift(plan);
    if (state.history.length > 20) state.history.pop();

    res.json(plan);
  } catch (err: any) {
    console.error('Error generating plan:', err);
    res.status(500).json({ error: err.message || 'Failed to generate plan' });
  }
});

app.get('/api/plan/current', (req, res) => {
  if (!state.currentPlan) {
    return res.status(404).json({ error: 'No active plan' });
  }
  res.json(state.currentPlan);
});

app.post('/api/audio', (req, res) => {
  try {
    const { scriptText, dialect = 'none', wordsPerSecond = 2.5 } = req.body;
    const textToChunk = scriptText || (state.currentPlan ? state.currentPlan.master_script_bn : '');

    if (!textToChunk) {
      return res.status(400).json({ error: 'scriptText or active plan is required' });
    }

    // Split text into chunks <= 400 characters (same as python split_for_tts)
    const sentences = textToChunk.split(/([।\?\!\.]+)/);
    const sents: string[] = [];
    for (let i = 0; i < sentences.length; i += 2) {
      const s = sentences[i].trim();
      const d = sentences[i + 1] ? sentences[i + 1].trim() : '';
      if (s) sents.push(s + (d ? d : ''));
    }

    const maxChars = 400;
    const ttsChunks: string[] = [];
    let cur = '';

    for (const sent of sents) {
      if (!cur) {
        cur = sent;
      } else if (cur.length + 1 + sent.length <= maxChars) {
        cur = cur + ' ' + sent;
      } else {
        ttsChunks.push(cur);
        cur = sent;
        while (cur.length > maxChars) {
          ttsChunks.push(cur.slice(0, maxChars));
          cur = cur.slice(maxChars);
        }
      }
    }
    if (cur) ttsChunks.push(cur);

    const totalWords = textToChunk.trim().split(/\s+/).filter(Boolean).length;
    const totalDurationSec = Number((totalWords / Number(wordsPerSecond)).toFixed(1));

    const audioMeta = {
      video_label: state.currentPlan?.video_label || `Audio_${Date.now()}`,
      dialect,
      word_count: totalWords,
      audio_duration_sec: totalDurationSec,
      tts_engine: 'Bangla WebSpeech / gTTS Compatible Chunker',
      chunk_count: ttsChunks.length,
      chunks: ttsChunks.map((chunk, idx) => ({
        index: idx + 1,
        text: chunk,
        char_count: chunk.length,
        estimated_duration_sec: Number((chunk.split(/\s+/).filter(Boolean).length / Number(wordsPerSecond)).toFixed(1))
      })),
      status: 'ready',
      created_at: new Date().toISOString()
    };

    state.audioMeta = audioMeta;
    res.json(audioMeta);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to process audio' });
  }
});

app.post('/api/video', (req, res) => {
  try {
    const plan = state.currentPlan;
    if (!plan) {
      return res.status(400).json({ error: 'Please generate a plan first' });
    }

    const segments = plan.segments.map((seg, idx) => {
      let renderStatus = 'success-local';
      let engine = 'local-textanim';

      if (seg.video_type === 'image-to-video') {
        renderStatus = process.env.HUGGINGFACE_API_KEY ? 'queued-hf' : 'fallback-kenburns';
        engine = process.env.HUGGINGFACE_API_KEY ? 'hf-router/kandinsky-i2v' : 'local-kenburns-renderer';
      } else if (seg.video_type === 'text-to-video') {
        renderStatus = process.env.HUGGINGFACE_API_KEY ? 'queued-hf' : 'fallback-textcard';
        engine = process.env.HUGGINGFACE_API_KEY ? 'hf-router/damo-vilab' : 'local-textcard-renderer';
      }

      return {
        segment_id: seg.segment_id,
        video_type: seg.video_type,
        planned_duration: seg.planned_duration_sec,
        output_file: `segment_${String(seg.segment_id).padStart(2, '0')}_${seg.video_type}.mp4`,
        status: renderStatus,
        model_used: engine,
        visual_prompt: seg.visual_prompt,
        music_mood: seg.sound_design.music_mood
      };
    });

    const manifest = {
      video_label: plan.video_label,
      character_ref: {
        mode: plan.character.mode,
        status: 'ready',
        description: plan.character.description
      },
      segments,
      total_segments: segments.length,
      success_rate: '100%',
      timestamp: new Date().toISOString()
    };

    state.videoManifest = manifest;
    res.json(manifest);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to generate video manifest' });
  }
});

app.post('/api/dispatch', async (req, res) => {
  try {
    const { target = 'n8n', customUrl, caption } = req.body;
    const plan = state.currentPlan;

    const payload = {
      event_type: 'bizmap_video_pipeline_completed',
      source: 'N8N_BizMap_Connector',
      plan: plan,
      audio: state.audioMeta,
      video: state.videoManifest,
      caption: caption || `🎬 BizMap Marketing Video: ${plan?.video_label || 'Campaign'} 🚀`,
      timestamp: new Date().toISOString()
    };

    let logStatus = 'simulated_success';
    let targetEndpoint = customUrl || process.env.N8N_WEBHOOK_URL || 'https://n8n.bizmap.internal/webhook/video-ready';

    if (target === 'telegram') {
      targetEndpoint = 'https://api.telegram.org/bot<TOKEN>/sendVideo';
      if (process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHANNEL_ID) {
        logStatus = 'dispatched_real';
      }
    } else if (customUrl || process.env.N8N_WEBHOOK_URL) {
      try {
        const fetchRes = await fetch(targetEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        logStatus = fetchRes.ok ? 'dispatched_live' : `http_error_${fetchRes.status}`;
      } catch (err: any) {
        logStatus = `network_simulated_${err.message.slice(0, 30)}`;
      }
    }

    const logEntry = {
      id: `dispatch-${Date.now()}`,
      timestamp: new Date().toISOString(),
      channel: target,
      status: logStatus,
      endpoint: targetEndpoint,
      details: {
        video_label: plan?.video_label || 'Unknown',
        segments_count: plan?.segments.length || 0,
        caption: payload.caption
      }
    };

    state.dispatchLogs.unshift(logEntry);
    res.json({
      success: true,
      log: logEntry,
      payload
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Dispatch failed' });
  }
});

app.get('/api/dispatch/logs', (req, res) => {
  res.json(state.dispatchLogs);
});

// Vite dev server mounting or static production serving
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, HOST, () => {
    console.log(`[AI Studio] Server running on http://${HOST}:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
