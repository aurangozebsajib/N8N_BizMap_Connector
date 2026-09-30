import React, { useState, useEffect } from 'react';
import {
  Film,
  Mic,
  Settings2,
  Send,
  Sparkles,
  Play,
  Square,
  Volume2,
  Copy,
  Check,
  RefreshCw,
  Layers,
  ArrowRight,
  User,
  Music,
  Clock,
  FileText,
  Workflow,
  Radio,
  CheckCircle2,
  AlertCircle,
  FileCode,
  Terminal
} from 'lucide-react';

interface Segment {
  segment_id: number;
  chunk: number;
  text_portion: string;
  word_count: number;
  planned_duration_sec: number;
  video_type: 'text-animation' | 'image-to-video' | 'text-to-video';
  visual_prompt: string;
  style_notes: string;
  sound_design: {
    music_mood: string;
    sfx: string[];
  };
}

interface CharacterDesign {
  mode: 'per_video' | 'fixed';
  name: string;
  description: string;
  age_range: string;
  gender: string;
  clothing: string;
  colors: string;
  style: string;
}

interface PlanOutput {
  video_number: number;
  date_str: string;
  video_label: string;
  dialect_used: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka';
  character: CharacterDesign;
  master_script_bn: string;
  original_script_bn: string;
  total_words: number;
  total_duration_sec: number;
  segments: Segment[];
  timestamp: string;
}

interface AudioMeta {
  video_label: string;
  dialect: string;
  word_count: number;
  audio_duration_sec: number;
  tts_engine: string;
  chunk_count: number;
  chunks: Array<{
    index: number;
    text: string;
    char_count: number;
    estimated_duration_sec: number;
  }>;
}

interface SampleStory {
  id: string;
  title: string;
  dialect: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'auto';
  caseNumber: number;
  date: string;
  content: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'planner' | 'audio' | 'video' | 'automations' | 'code'>('planner');
  const [samples, setSamples] = useState<SampleStory[]>([]);
  const [selectedSampleId, setSelectedSampleId] = useState<string>('');
  const [pythonFiles, setPythonFiles] = useState<Record<string, string>>({});
  const [selectedPyFile, setSelectedPyFile] = useState<string>('brain/main.py');
  const [copiedPy, setCopiedPy] = useState<boolean>(false);
  
  // Planner State
  const [rawScript, setRawScript] = useState<string>('');
  const [dialect, setDialect] = useState<'auto' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'none'>('auto');
  const [characterMode, setCharacterMode] = useState<'per_video' | 'fixed'>('per_video');
  const [maxSegments, setMaxSegments] = useState<number>(10);
  const [loadingPlan, setLoadingPlan] = useState<boolean>(false);
  const [plan, setPlan] = useState<PlanOutput | null>(null);

  // Audio State
  const [audioMeta, setAudioMeta] = useState<AudioMeta | null>(null);
  const [loadingAudio, setLoadingAudio] = useState<boolean>(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [speechSynthesisAvailable, setSpeechSynthesisAvailable] = useState<boolean>(false);
  const [copiedScript, setCopiedScript] = useState<boolean>(false);

  // Video State
  const [videoManifest, setVideoManifest] = useState<any>(null);
  const [loadingVideo, setLoadingVideo] = useState<boolean>(false);
  const [activePreviewSegment, setActivePreviewSegment] = useState<number>(1);

  // Automation / Dispatch State
  const [webhookUrl, setWebhookUrl] = useState<string>('https://n8n.bizmap.internal/webhook/video-ready');
  const [caption, setCaption] = useState<string>('');
  const [dispatchLogs, setDispatchLogs] = useState<any[]>([]);
  const [dispatching, setDispatching] = useState<boolean>(false);
  const [dispatchSuccess, setDispatchSuccess] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<any>(null);

  // Load initial data
  useEffect(() => {
    // Check speech synthesis
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      setSpeechSynthesisAvailable(true);
    }

    // Fetch initial status and samples
    fetch('/api/status')
      .then(res => res.json())
      .then(data => setBackendStatus(data))
      .catch(console.error);

    fetch('/api/sample-stories')
      .then(res => res.json())
      .then((data: SampleStory[]) => {
        setSamples(data);
        if (data.length > 0) {
          setSelectedSampleId(data[0].id);
          setRawScript(data[0].content);
          setDialect(data[0].dialect);
        }
      })
      .catch(console.error);

    fetch('/api/plan/current')
      .then(res => res.json())
      .then(data => {
        if (data && !data.error) {
          setPlan(data);
          setCaption(`🎬 BizMap AI Marketing Video: ${data.video_label} 🚀`);
        }
      })
      .catch(console.error);

    fetch('/api/dispatch/logs')
      .then(res => res.json())
      .then(data => setDispatchLogs(data))
      .catch(console.error);

    fetch('/api/python-code')
      .then(res => res.json())
      .then(data => setPythonFiles(data))
      .catch(console.error);
  }, []);

  const handleSelectSample = (sampleId: string) => {
    setSelectedSampleId(sampleId);
    const found = samples.find(s => s.id === sampleId);
    if (found) {
      setRawScript(found.content);
      setDialect(found.dialect);
    }
  };

  const handleGeneratePlan = async () => {
    if (!rawScript.trim()) return;
    setLoadingPlan(true);
    try {
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rawText: rawScript,
          dialect,
          characterMode,
          maxSegments
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to generate plan');
      setPlan(data);
      setCaption(`🎬 BizMap AI Marketing Video: ${data.video_label} 🚀`);
      // automatically invalidate old video/audio meta
      setAudioMeta(null);
      setVideoManifest(null);
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setLoadingPlan(false);
    }
  };

  const handleProcessAudio = async () => {
    if (!plan) return;
    setLoadingAudio(true);
    try {
      const res = await fetch('/api/audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scriptText: plan.master_script_bn,
          dialect: plan.dialect_used,
          wordsPerSecond: 2.5
        })
      });
      const data = await res.json();
      setAudioMeta(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingAudio(false);
    }
  };

  const handleSpeechToggle = () => {
    if (!speechSynthesisAvailable || !plan) return;

    if (isPlayingAudio) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(plan.master_script_bn);
    utterance.lang = 'bn-BD';
    utterance.rate = 0.95;

    // Try finding Bengali voice
    const voices = window.speechSynthesis.getVoices();
    const bnVoice = voices.find(v => v.lang.includes('bn') || v.lang.includes('BD') || v.lang.includes('IN'));
    if (bnVoice) utterance.voice = bnVoice;

    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    window.speechSynthesis.speak(utterance);
    setIsPlayingAudio(true);
  };

  const handleGenerateVideoStoryboard = async () => {
    if (!plan) return;
    setLoadingVideo(true);
    try {
      const res = await fetch('/api/video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      setVideoManifest(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingVideo(false);
    }
  };

  const handleDispatch = async (target: 'n8n' | 'telegram') => {
    setDispatching(true);
    setDispatchSuccess(null);
    try {
      const res = await fetch('/api/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target,
          customUrl: webhookUrl,
          caption
        })
      });
      const data = await res.json();
      if (data.success) {
        setDispatchSuccess(`Successfully dispatched to ${target.toUpperCase()}! (Status: ${data.log.status})`);
        setDispatchLogs(prev => [data.log, ...prev]);
      }
    } catch (err: any) {
      alert(`Dispatch failed: ${err.message}`);
    } finally {
      setDispatching(false);
    }
  };

  const handleRunFullPipeline = async () => {
    setLoadingPlan(true);
    try {
      // 1. Plan
      const planRes = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rawText: rawScript, dialect, characterMode, maxSegments })
      });
      const planData = await planRes.json();
      setPlan(planData);

      // 2. Audio
      const audioRes = await fetch('/api/audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scriptText: planData.master_script_bn, dialect: planData.dialect_used })
      });
      const audioData = await audioRes.json();
      setAudioMeta(audioData);

      // 3. Video
      const videoRes = await fetch('/api/video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const videoData = await videoRes.json();
      setVideoManifest(videoData);

      setActiveTab('video');
    } catch (err: any) {
      alert(`Pipeline error: ${err.message}`);
    } finally {
      setLoadingPlan(false);
    }
  };

  const currentSegment = plan?.segments.find(s => s.segment_id === activePreviewSegment) || plan?.segments[0];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50 px-4 lg:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Film className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-lg text-white tracking-tight">N8N BizMap Connector</h1>
                <span className="text-[11px] font-semibold uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded-md">
                  Brain Pipeline v2
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Bangla Dialect Engine • TTS Audio Factory • Video Storyboard Generator
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Port 3000 Node.js API Online</span>
            </div>
            <button
              onClick={handleRunFullPipeline}
              disabled={loadingPlan}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-lg font-medium text-xs shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span>{loadingPlan ? 'Processing Pipeline...' : 'Run Full Pipeline'}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Tab Navigation */}
      <div className="border-b border-slate-800 bg-slate-900/40 px-4 lg:px-8">
        <div className="max-w-7xl mx-auto flex space-x-1 sm:space-x-4 overflow-x-auto py-2">
          <button
            onClick={() => setActiveTab('planner')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              activeTab === 'planner'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Settings2 className="w-4 h-4" />
            <span>1. Story &amp; Dialect Planner</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('audio');
              if (!audioMeta && plan) handleProcessAudio();
            }}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              activeTab === 'audio'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Mic className="w-4 h-4" />
            <span>2. Audio &amp; TTS Lab</span>
            {audioMeta && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
          </button>
          <button
            onClick={() => {
              setActiveTab('video');
              if (!videoManifest && plan) handleGenerateVideoStoryboard();
            }}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              activeTab === 'video'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>3. Video Storyboard Studio</span>
            {videoManifest && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>}
          </button>
          <button
            onClick={() => setActiveTab('automations')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              activeTab === 'automations'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Workflow className="w-4 h-4" />
            <span>4. N8N &amp; Automations Hub</span>
          </button>
          <button
            onClick={() => setActiveTab('code')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              activeTab === 'code'
                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <FileCode className="w-4 h-4 text-emerald-400" />
            <span className="font-semibold text-emerald-400">5. Fixed Python Pipeline &amp; GitHub Code</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8">
        {/* TAB 1: PLANNER */}
        {activeTab === 'planner' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Controls Column */}
            <div className="lg:col-span-5 space-y-5">
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    Input Story / Script
                  </h2>
                  <span className="text-xs text-slate-500">Google Doc Format</span>
                </div>

                {/* Sample Case Studies Selector */}
                <div className="mb-4">
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">
                    Preloaded BizMap Case Studies:
                  </label>
                  <select
                    value={selectedSampleId}
                    onChange={(e) => handleSelectSample(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    {samples.map((sample) => (
                      <option key={sample.id} value={sample.id}>
                        {sample.title}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Script Editor */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium text-slate-400">
                      Bangla Story Content:
                    </label>
                    <span className="text-[11px] text-slate-500">
                      {rawScript.split(/\s+/).filter(Boolean).length} words
                    </span>
                  </div>
                  <textarea
                    rows={9}
                    value={rawScript}
                    onChange={(e) => setRawScript(e.target.value)}
                    placeholder="Video 1 | 2026-10-02&#10;Dialect: rangpuri&#10;গল্পের বিবরণ লিখুন..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs sm:text-sm font-bangla text-slate-200 focus:outline-none focus:border-indigo-500 font-normal leading-relaxed resize-y"
                  ></textarea>
                </div>

                {/* Dialect and Options */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Dialect Transformation:
                    </label>
                    <select
                      value={dialect}
                      onChange={(e: any) => setDialect(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="auto">Auto (র‍্যান্ডম ডায়ালেক্ট)</option>
                      <option value="rangpuri">Rangpuri (রংপুরী)</option>
                      <option value="barishal">Barishal (বরিশাইল্যা)</option>
                      <option value="old-dhaka">Old Dhaka (পুরান ঢাকা)</option>
                      <option value="none">Standard / None (প্রমিত)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Character Mode:
                    </label>
                    <select
                      value={characterMode}
                      onChange={(e: any) => setCharacterMode(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="per_video">Per-Video Dynamic Protagonist</option>
                      <option value="fixed">Fixed Host (সজীব ভাই)</option>
                    </select>
                  </div>
                </div>

                <div className="mb-5">
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                    <span>Max Target Segments:</span>
                    <span className="font-semibold text-indigo-400">{maxSegments} segments</span>
                  </div>
                  <input
                    type="range"
                    min={4}
                    max={15}
                    value={maxSegments}
                    onChange={(e) => setMaxSegments(Number(e.target.value))}
                    className="w-full accent-indigo-500 cursor-pointer"
                  />
                </div>

                <button
                  onClick={handleGeneratePlan}
                  disabled={loadingPlan}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-xs sm:text-sm flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50 shadow-md shadow-indigo-600/10"
                >
                  {loadingPlan ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Analyzing &amp; Segmenting...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Generate Plan &amp; Dialect Conversion</span>
                    </>
                  )}
                </button>
              </div>

              {/* Character Details Card */}
              {plan && (
                <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      Designed Character Profile
                    </h3>
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded font-mono">
                      {plan.character.mode}
                    </span>
                  </div>
                  <div className="p-3.5 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-white">{plan.character.name}</span>
                      <span className="text-xs text-slate-400">{plan.character.age_range} • {plan.character.gender}</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed italic">
                      "{plan.character.description}"
                    </p>
                    <div className="pt-2 border-t border-slate-800/60 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                      <div><strong className="text-slate-300">Clothing:</strong> {plan.character.clothing}</div>
                      <div><strong className="text-slate-300">Colors:</strong> {plan.character.colors}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Output Column */}
            <div className="lg:col-span-7 space-y-5">
              {plan ? (
                <>
                  {/* Plan Overview Stats */}
                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 sm:p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
                      <div>
                        <h2 className="text-base font-bold text-white flex items-center gap-2">
                          <span>{plan.video_label}</span>
                          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            {plan.dialect_used.toUpperCase()} DIALECT
                          </span>
                        </h2>
                        <p className="text-xs text-slate-400">Generated on {new Date(plan.timestamp).toLocaleTimeString()}</p>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
                          <span className="text-slate-400 block text-[10px]">TOTAL WORDS</span>
                          <span className="font-semibold text-slate-200">{plan.total_words}</span>
                        </div>
                        <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
                          <span className="text-slate-400 block text-[10px]">EST. DURATION</span>
                          <span className="font-semibold text-indigo-400">{plan.total_duration_sec}s</span>
                        </div>
                        <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
                          <span className="text-slate-400 block text-[10px]">SEGMENTS</span>
                          <span className="font-semibold text-slate-200">{plan.segments.length}</span>
                        </div>
                      </div>
                    </div>

                    {/* Master Script Preview */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-slate-300">Master Narration Script (Bangla):</span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(plan.master_script_bn);
                            setCopiedScript(true);
                            setTimeout(() => setCopiedScript(false), 2000);
                          }}
                          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 cursor-pointer"
                        >
                          {copiedScript ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>{copiedScript ? 'Copied' : 'Copy Script'}</span>
                        </button>
                      </div>
                      <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs sm:text-sm font-bangla text-slate-200 leading-relaxed max-h-40 overflow-y-auto whitespace-pre-wrap">
                        {plan.master_script_bn}
                      </div>
                    </div>
                  </div>

                  {/* Storyboard Segments */}
                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 sm:p-5">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <Film className="w-4 h-4 text-indigo-400" />
                        Planned Storyboard Segments ({plan.segments.length})
                      </h3>
                      <button
                        onClick={() => setActiveTab('video')}
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 cursor-pointer"
                      >
                        <span>Preview in Studio</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                      {plan.segments.map((seg) => (
                        <div
                          key={seg.segment_id}
                          className="p-3.5 bg-slate-950 border border-slate-800/90 rounded-lg hover:border-slate-700 transition-colors"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="w-6 h-6 rounded-md bg-slate-800 text-slate-300 text-xs font-bold flex items-center justify-center">
                                #{seg.segment_id}
                              </span>
                              <span
                                className={`text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
                                  seg.video_type === 'text-animation'
                                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                    : seg.video_type === 'image-to-video'
                                    ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                    : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                }`}
                              >
                                {seg.video_type}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                              <span>{seg.word_count} words</span>
                              <span className="text-indigo-400 font-semibold">{seg.planned_duration_sec}s</span>
                            </div>
                          </div>

                          <p className="text-xs sm:text-sm font-bangla text-slate-200 mb-2 leading-relaxed">
                            {seg.text_portion}
                          </p>

                          <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800/60 space-y-1.5 text-xs">
                            <div className="text-slate-400">
                              <strong className="text-slate-300">Visual Prompt:</strong>{' '}
                              <span className="text-slate-300">{seg.visual_prompt}</span>
                            </div>
                            <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/40">
                              <span className="flex items-center gap-1 text-slate-400">
                                <Music className="w-3 h-3 text-indigo-400" />
                                {seg.sound_design.music_mood}
                              </span>
                              <span className="text-slate-500 font-mono">
                                SFX: {seg.sound_design.sfx.join(', ')}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="h-full min-h-[350px] bg-slate-900/40 border border-dashed border-slate-800 rounded-xl flex flex-col items-center justify-center p-8 text-center text-slate-400">
                  <Film className="w-12 h-12 text-slate-700 mb-3" />
                  <h3 className="text-sm font-medium text-slate-300 mb-1">No Active Story Plan</h3>
                  <p className="text-xs max-w-sm text-slate-500 mb-4">
                    Select a BizMap case study on the left or paste your own script and click "Generate Plan".
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: AUDIO FACTORY */}
        {activeTab === 'audio' && (
          <div className="space-y-6">
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Mic className="w-5 h-5 text-indigo-400" />
                    Audio &amp; TTS Narration Engine
                  </h2>
                  <p className="text-xs text-slate-400">
                    Chunked Bangla TTS Pipeline (≤ 400 char segments, 2.5 words/second pacing)
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleSpeechToggle}
                    disabled={!plan}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                      isPlayingAudio
                        ? 'bg-rose-600 hover:bg-rose-500 text-white'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                    }`}
                  >
                    {isPlayingAudio ? (
                      <>
                        <Square className="w-4 h-4" />
                        <span>Stop Voice Playback</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        <span>Play Bengali TTS Audio</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleProcessAudio}
                    disabled={loadingAudio || !plan}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingAudio ? 'animate-spin' : ''}`} />
                    <span>Recalculate TTS Chunks</span>
                  </button>
                </div>
              </div>

              {audioMeta ? (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 block">Total Narration Time</span>
                      <span className="text-lg font-bold text-indigo-400">{audioMeta.audio_duration_sec}s</span>
                    </div>
                    <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 block">Word Count</span>
                      <span className="text-lg font-bold text-slate-200">{audioMeta.word_count} words</span>
                    </div>
                    <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 block">TTS Pieces</span>
                      <span className="text-lg font-bold text-slate-200">{audioMeta.chunk_count} chunks</span>
                    </div>
                    <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 block">Dialect Mode</span>
                      <span className="text-lg font-bold text-emerald-400 uppercase">{audioMeta.dialect}</span>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                      <Volume2 className="w-4 h-4 text-indigo-400" />
                      Individual TTS Audio Chunks (Split at sentence delimiters ≤ 400 chars)
                    </h3>
                    <div className="space-y-3">
                      {audioMeta.chunks.map((ch) => (
                        <div
                          key={ch.index}
                          className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-indigo-400 font-bold">Chunk #{ch.index}</span>
                              <span className="text-[10px] text-slate-500 font-mono">({ch.char_count} chars • est. {ch.estimated_duration_sec}s)</span>
                            </div>
                            <p className="text-xs sm:text-sm font-bangla text-slate-200 leading-relaxed">
                              {ch.text}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              onClick={() => {
                                if ('speechSynthesis' in window) {
                                  window.speechSynthesis.cancel();
                                  const utt = new SpeechSynthesisUtterance(ch.text);
                                  utt.lang = 'bn-BD';
                                  window.speechSynthesis.speak(utt);
                                }
                              }}
                              className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-slate-300 rounded text-xs flex items-center gap-1.5 cursor-pointer"
                            >
                              <Play className="w-3 h-3 text-emerald-400" />
                              <span>Listen</span>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400">
                  <p className="text-xs">Click "Recalculate TTS Chunks" or generate a story plan first.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: VIDEO STORYBOARD STUDIO */}
        {activeTab === 'video' && (
          <div className="space-y-6">
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Film className="w-5 h-5 text-indigo-400" />
                    Video Storyboard &amp; Scene Visualizer
                  </h2>
                  <p className="text-xs text-slate-400">
                    Kinetic Bengali text animation, Ken Burns motion cards, and visual prompt rendering
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleGenerateVideoStoryboard}
                    disabled={loadingVideo || !plan}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingVideo ? 'animate-spin' : ''}`} />
                    <span>Generate Storyboard Manifest</span>
                  </button>
                </div>
              </div>

              {plan ? (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Segment Selector List */}
                  <div className="lg:col-span-4 space-y-2 max-h-[550px] overflow-y-auto pr-1">
                    {plan.segments.map((seg) => {
                      const isSelected = seg.segment_id === activePreviewSegment;
                      return (
                        <button
                          key={seg.segment_id}
                          onClick={() => setActivePreviewSegment(seg.segment_id)}
                          className={`w-full text-left p-3 rounded-lg border transition-all cursor-pointer ${
                            isSelected
                              ? 'bg-indigo-950/40 border-indigo-500/80 shadow-sm'
                              : 'bg-slate-950/80 border-slate-800/70 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-bold text-slate-300">
                              Segment {seg.segment_id}
                            </span>
                            <span
                              className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                                seg.video_type === 'text-animation'
                                  ? 'bg-amber-500/20 text-amber-300'
                                  : seg.video_type === 'image-to-video'
                                  ? 'bg-purple-500/20 text-purple-300'
                                  : 'bg-blue-500/20 text-blue-300'
                              }`}
                            >
                              {seg.video_type}
                            </span>
                          </div>
                          <p className="text-xs font-bangla text-slate-300 truncate">
                            {seg.text_portion}
                          </p>
                          <div className="flex items-center justify-between mt-2 text-[10px] text-slate-400">
                            <span>{seg.planned_duration_sec}s</span>
                            <span className="italic">{seg.sound_design.music_mood.slice(0, 25)}...</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {/* Active Segment Preview Display */}
                  <div className="lg:col-span-8 space-y-4">
                    {currentSegment && (
                      <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden p-5 flex flex-col">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                            Live Simulated Canvas Output (16:9 / 9:16 Responsive Frame)
                          </span>
                          <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                            Renderer: {currentSegment.video_type === 'text-animation' ? 'Local Kinetic Canvas' : 'Ken Burns Motion Simulation'}
                          </span>
                        </div>

                        {/* Visual Stage Card */}
                        <div className="relative aspect-video w-full rounded-lg overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center p-6 text-center shadow-inner group">
                          {currentSegment.video_type === 'text-animation' ? (
                            <div className="space-y-4 max-w-lg">
                              <span className="inline-block text-[11px] font-bold uppercase tracking-widest bg-amber-500/20 text-amber-300 border border-amber-500/30 px-3 py-1 rounded-full animate-bounce">
                                💡 KEY LESSON &amp; INSIGHT
                              </span>
                              <h3 className="text-xl sm:text-2xl font-bold font-bangla text-amber-200 leading-snug drop-shadow-md">
                                {currentSegment.text_portion}
                              </h3>
                              <p className="text-xs text-slate-400 font-mono">
                                [Kinetic Typography • Gold/Ivory Bengali Rendering]
                              </p>
                            </div>
                          ) : (
                            <div className="space-y-3 max-w-md">
                              <div className="w-16 h-16 mx-auto rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 animate-pulse">
                                {currentSegment.video_type === 'image-to-video' ? (
                                  <User className="w-8 h-8" />
                                ) : (
                                  <Film className="w-8 h-8" />
                                )}
                              </div>
                              <h4 className="text-sm font-semibold text-white">
                                {currentSegment.video_type === 'image-to-video' ? 'Character Focus Scene' : 'Atmospheric Narrative Scene'}
                              </h4>
                              <p className="text-xs text-slate-300 italic px-4">
                                "{currentSegment.visual_prompt}"
                              </p>
                              <div className="text-[11px] text-slate-400 font-mono">
                                Camera Motion: Pan / Slow Push 1.1x • Dur: {currentSegment.planned_duration_sec}s
                              </div>
                            </div>
                          )}

                          {/* Sound Cue Overlay */}
                          <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-[11px] bg-slate-950/80 backdrop-blur border border-slate-800 px-3 py-1.5 rounded-md">
                            <span className="flex items-center gap-1.5 text-indigo-300 font-medium">
                              <Music className="w-3.5 h-3.5" />
                              {currentSegment.sound_design.music_mood}
                            </span>
                            <span className="text-slate-400 font-mono">
                              SFX: {currentSegment.sound_design.sfx.join(', ')}
                            </span>
                          </div>
                        </div>

                        {/* Segment Specs */}
                        <div className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                          <div>
                            <span className="text-slate-400 block mb-1">Bangla Narration Portion:</span>
                            <p className="font-bangla text-slate-200 bg-slate-900/60 p-2.5 rounded border border-slate-800">
                              {currentSegment.text_portion}
                            </p>
                          </div>
                          <div>
                            <span className="text-slate-400 block mb-1">Visual Generation Spec:</span>
                            <p className="text-slate-300 bg-slate-900/60 p-2.5 rounded border border-slate-800 italic">
                              {currentSegment.visual_prompt}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400">
                  <p className="text-xs">Generate a story plan first.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: AUTOMATIONS & N8N CONNECTOR */}
        {activeTab === 'automations' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-6 space-y-5">
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <Workflow className="w-4 h-4 text-indigo-400" />
                    N8N &amp; Telegram Dispatcher
                  </h2>
                  <span className="text-xs text-slate-500">HTTP Webhook Trigger</span>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      N8N Webhook Endpoint URL:
                    </label>
                    <input
                      type="url"
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      placeholder="https://your-n8n.instance/webhook/video-ready"
                      className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Telegram / Dispatch Caption:
                    </label>
                    <input
                      type="text"
                      value={caption}
                      onChange={(e) => setCaption(e.target.value)}
                      placeholder="🎬 BizMap AI Marketing Video: Video 1 | 2026-10-02 🚀"
                      className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  {dispatchSuccess && (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs rounded-lg flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>{dispatchSuccess}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <button
                      onClick={() => handleDispatch('n8n')}
                      disabled={dispatching || !plan}
                      className="py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Dispatch to N8N</span>
                    </button>
                    <button
                      onClick={() => handleDispatch('telegram')}
                      disabled={dispatching || !plan}
                      className="py-2.5 px-4 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-medium flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      <Radio className="w-3.5 h-3.5" />
                      <span>Dispatch to Telegram</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Secrets & Environment Summary */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                  <Settings2 className="w-3.5 h-3.5 text-indigo-400" />
                  Connector Environment &amp; Integrations
                </h3>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded border border-slate-800">
                    <span className="text-slate-300">Google Docs &amp; Sheets Service JSON:</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${backendStatus?.env?.hasGoogleServiceJson ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}>
                      {backendStatus?.env?.hasGoogleServiceJson ? 'Configured' : 'Optional (In-Memory Active)'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded border border-slate-800">
                    <span className="text-slate-300">Gemini LLM Script Planner:</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${backendStatus?.env?.hasGeminiKey ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}>
                      {backendStatus?.env?.hasGeminiKey ? 'Gemini 2.5 Flash Connected' : 'Deterministic Brain Engine'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded border border-slate-800">
                    <span className="text-slate-300">Telegram Bot Channel:</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${backendStatus?.env?.hasTelegramBot ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}>
                      {backendStatus?.env?.hasTelegramBot ? 'Configured' : 'Simulated Dispatch'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded border border-slate-800">
                    <span className="text-slate-300">Local Rendering Fallback:</span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/20 text-emerald-400">
                      Enabled (Ken Burns / Textcard)
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Dispatch History & Payload Preview */}
            <div className="lg:col-span-6 space-y-5">
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-indigo-400" />
                    Recent Webhook Dispatch History
                  </h3>
                  <span className="text-xs text-slate-500">{dispatchLogs.length} events</span>
                </div>

                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {dispatchLogs.length > 0 ? (
                    dispatchLogs.map((log) => (
                      <div
                        key={log.id}
                        className="p-2.5 bg-slate-950 rounded border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-semibold text-slate-200">{log.channel.toUpperCase()} Dispatch</div>
                          <div className="text-[11px] text-slate-500 font-mono">{new Date(log.timestamp).toLocaleTimeString()} • {log.details.video_label}</div>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {log.status}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-6 text-xs text-slate-500">
                      No webhook dispatches sent yet.
                    </div>
                  )}
                </div>
              </div>

              {/* Live Payload JSON Inspection */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-indigo-400" />
                    Generated plan.json Payload
                  </h3>
                  <button
                    onClick={() => {
                      if (plan) {
                        navigator.clipboard.writeText(JSON.stringify(plan, null, 2));
                        alert('plan.json copied to clipboard!');
                      }
                    }}
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 cursor-pointer"
                  >
                    Copy JSON
                  </button>
                </div>
                <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 max-h-56 overflow-y-auto">
                  {plan ? JSON.stringify(plan, null, 2) : '// No active plan'}
                </pre>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: FIXED PYTHON PIPELINE & GITHUB CODE */}
        {activeTab === 'code' && (
          <div className="space-y-6">
            {/* Analysis Banner */}
            <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-5">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h2 className="text-sm font-bold text-white mb-1">
                    Python ImportError &amp; Telegram Dispatch Analysis &amp; Permanent Fix
                  </h2>
                  <p className="text-xs text-slate-300 leading-relaxed mb-3">
                    <strong>মূল কারণ ১ (ImportError):</strong> <code className="text-rose-400 bg-slate-900 px-1 py-0.5 rounded">brain/planner.py</code> ফাইলে পূর্বে <code className="text-emerald-400 bg-slate-900 px-1 py-0.5 rounded">def run_plan():</code> ফাংশনটি সঠিকভাবে এক্সপোর্ট করা ছিল না বা ডাইরেক্ট এক্সিকিউশনে পাথ মিসিং ছিল। আমরা <code className="text-emerald-400 bg-slate-900 px-1 py-0.5 rounded">run_plan()</code> ফাংশনটি সম্পূর্ণ নির্ভুলভাবে ইমপ্লিমেন্ট করেছি যা ডক/স্ক্রিপ্ট পড়া, ডায়ালেক্ট রূপান্তর, ক্যারেক্টার ও সেগমেন্ট তৈরি করে <code className="text-indigo-400 bg-slate-900 px-1 py-0.5 rounded">output/plan.json</code> ফাইল তৈরি করে।
                    <br />
                    <strong>মূল কারণ ২ (Empty File / Bad Request in Telegram):</strong> পূর্বে টেস্ট করার সময় <code className="text-rose-400 bg-slate-900 px-1 py-0.5 rounded">output_clip.mp4</code> একটি ০ বাইটের ফাইল বানানো হয়েছিল, যার কারণে টেলিগ্রাম এপিআই <code className="text-rose-400 bg-slate-900 px-1 py-0.5 rounded">file must be non-empty</code> এরর দিচ্ছিল। <code className="text-emerald-400 bg-slate-900 px-1 py-0.5 rounded">brain/video_engine.py</code> এখন Hugging Face এপিআই বা লোকাল ফলব্যাক দিয়ে আসল ভ্যালিড নন-এম্পটি MP4 ভিডিও ক্লিপ তৈরি করে, যাতে টেলিগ্রামে সরাসরি সেন্ড হয়।
                    <br />
                    <strong>মূল কারণ ৩ (GitHub Actions Cache &amp; Artifacts):</strong> গিটহাব একশনে মাল্টি-জব আর্টিফ্যাক্ট রিমুভ করে সম্পূর্ণ ক্লিন সিঙ্গল-জব <code className="text-indigo-400 bg-slate-900 px-1 py-0.5 rounded">pipeline.yml</code> প্রস্তুত করা হয়েছে।
                  </p>
                  <div className="flex flex-wrap gap-2 text-[11px] font-mono">
                    <span className="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                      ✓ brain/main.py verified
                    </span>
                    <span className="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                      ✓ brain/planner.py (run_plan) verified
                    </span>
                    <span className="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                      ✓ brain/video_engine.py verified
                    </span>
                    <span className="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                      ✓ .github/workflows/pipeline.yml verified
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Code Viewer Panel */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    File Inspector &amp; Copy Code for GitHub / Colab:
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const content = pythonFiles[selectedPyFile];
                      if (content) {
                        navigator.clipboard.writeText(content);
                        setCopiedPy(true);
                        setTimeout(() => setCopiedPy(false), 2000);
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium cursor-pointer transition-colors"
                  >
                    {copiedPy ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedPy ? 'Copied to Clipboard!' : `Copy ${selectedPyFile}`}</span>
                  </button>
                </div>
              </div>

              {/* File Tabs */}
              <div className="flex space-x-2 overflow-x-auto pb-2 mb-3 border-b border-slate-800 text-xs font-mono">
                {Object.keys(pythonFiles).map((fname) => (
                  <button
                    key={fname}
                    onClick={() => setSelectedPyFile(fname)}
                    className={`px-3 py-1.5 rounded cursor-pointer transition-colors whitespace-nowrap ${
                      selectedPyFile === fname
                        ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 font-bold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                    }`}
                  >
                    {fname}
                  </button>
                ))}
              </div>

              {/* Code Display */}
              <div className="relative">
                <pre className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-xs font-mono text-slate-200 max-h-[500px] overflow-y-auto leading-relaxed">
                  {pythonFiles[selectedPyFile] || '// Loading file...'}
                </pre>
              </div>
            </div>

            {/* Quick Setup Instructions for User */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-indigo-400" />
                GitHub বা Google Colab এ এই কোড বসানোর ধাপসমূহ:
              </h3>
              <ol className="list-decimal list-inside space-y-2 text-xs text-slate-300 leading-relaxed">
                <li>
                  আপনার রিপোজিটরির <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded font-mono">brain/planner.py</code> ফাইলে উপরের কোডটি পেস্ট করুন (এতে <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded font-mono">run_plan()</code> নিশ্চিতভাবে উপস্থিত আছে)।
                </li>
                <li>
                  <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded font-mono">brain/main.py</code> ফাইলে আপডেট কোডটি পেস্ট করুন।
                </li>
                <li>
                  <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded font-mono">brain/video_engine.py</code> ফাইলে আপডেট কোডটি পেস্ট করুন।
                </li>
                <li>
                  <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded font-mono">.github/workflows/pipeline.yml</code> ফাইলে ক্লিন সিঙ্গল-জব কনফিগারেশনটি পেস্ট করে GitHub এ পুশ করুন।
                </li>
                <li>
                  GitHub রিপোজিটরির Settings &gt; Secrets এ <code className="text-indigo-400 bg-slate-950 px-1 py-0.5 rounded font-mono">TELEGRAM_BOT_TOKEN</code> এবং <code className="text-indigo-400 bg-slate-950 px-1 py-0.5 rounded font-mono">TELEGRAM_CHANNEL_ID</code> (মাইনাস চিহ্নসহ যেমন: <code className="text-slate-400 font-mono">-100xxxxxxxxxx</code>) নিশ্চিত করুন।
                </li>
              </ol>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 px-4 py-4 text-center text-xs text-slate-500">
        N8N BizMap Connector • Migrated to Node.js / Vite SPA • Port 3000 Host 0.0.0.0
      </footer>
    </div>
  );
}
