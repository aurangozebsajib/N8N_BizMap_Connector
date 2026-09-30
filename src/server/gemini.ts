import { GoogleGenAI } from '@google/genai';
import { PlanOutput, generatePlan, CharacterDesign, Segment } from './planner.ts';

export async function generateAiPlan(options: {
  rawText: string;
  videoNumber?: number;
  dateStr?: string;
  dialect?: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'auto';
  maxSegments?: number;
  characterMode?: 'per_video' | 'fixed';
}): Promise<PlanOutput> {
  const fallback = generatePlan(options);
  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    return fallback;
  }

  try {
    const ai = new GoogleGenAI({ apiKey });
    const prompt = `You are the video planner and character designer for Bangla BizMap video production.
Here is the script:
${fallback.master_script_bn}

Generate an enriched JSON object with:
1. "character": { "name": string, "description": string (English, max 60 words, clean 2D illustration style), "age_range": string, "gender": string, "clothing": string, "colors": string, "style": string }
2. "segments": array of segments for each chunk with enriched visual_prompt, sound_design (music_mood, sfx array).

Return strict JSON only matching:
{
  "character": {...},
  "visual_prompts": [string],
  "music_moods": [string]
}`;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash-lite',
      contents: prompt,
      config: {
        responseMimeType: 'application/json',
      }
    });

    const text = response.text?.trim();
    if (text) {
      const data = JSON.parse(text);
      if (data.character) {
        fallback.character = {
          ...fallback.character,
          ...data.character
        };
      }
      if (Array.isArray(data.visual_prompts)) {
        fallback.segments.forEach((seg, i) => {
          if (data.visual_prompts[i]) {
            seg.visual_prompt = data.visual_prompts[i];
          }
          if (Array.isArray(data.music_moods) && data.music_moods[i]) {
            seg.sound_design.music_mood = data.music_moods[i];
          }
        });
      }
    }
  } catch (err) {
    console.warn('[Gemini Plan] Generative enrichment skipped or failed, using deterministic brain plan:', err);
  }

  return fallback;
}
