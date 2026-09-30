export interface Segment {
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

export interface CharacterDesign {
  mode: 'per_video' | 'fixed';
  name: string;
  description: string;
  age_range: string;
  gender: string;
  clothing: string;
  colors: string;
  style: string;
}

export interface PlanOutput {
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

const LESSON_STARTS = ['প্রথম শিক্ষা', 'দ্বিতীয় শিক্ষা', 'তৃতীয় শিক্ষা', 'সারকথা'];
const BANGLA_DIGITS_MAP: Record<string, string> = {
  '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
  '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
};

export function convertBanglaDigits(text: string): string {
  return text.replace(/[০-৯]/g, (ch) => BANGLA_DIGITS_MAP[ch] || ch);
}

export function applyDialectTransformation(
  text: string,
  targetDialect: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'auto'
): { transformed: string; dialectUsed: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' } {
  let chosenDialect = targetDialect;
  if (chosenDialect === 'auto') {
    const dialects: ('rangpuri' | 'barishal' | 'old-dhaka')[] = ['rangpuri', 'barishal', 'old-dhaka'];
    chosenDialect = dialects[Math.floor(Math.random() * dialects.length)];
  }

  if (chosenDialect === 'none') {
    return { transformed: text, dialectUsed: 'none' };
  }

  // Preserve lines starting with lessons in standard Bengali
  const lines = text.split('\n');
  const transformedLines = lines.map(line => {
    const isLesson = LESSON_STARTS.some(ls => line.trim().startsWith(ls));
    if (isLesson) return line;

    let res = line;
    if (chosenDialect === 'rangpuri') {
      res = res
        .replace(/\bআমি\b/g, 'মুই')
        .replace(/\bআমার\b/g, 'হামার')
        .replace(/\bআমরা\b/g, 'হামরা')
        .replace(/\bকোথায়\b/g, 'কোটেই')
        .replace(/\bগিয়েছিলাম\b/g, 'গেসিনু')
        .replace(/\bখাচ্ছ\b/g, 'খাইসু');
    } else if (chosenDialect === 'barishal') {
      res = res
        .replace(/\bযাব\b/g, 'যামু')
        .replace(/\bখাব\b/g, 'খামু')
        .replace(/\bকরব\b/g, 'করমু')
        .replace(/\bবলেছি\b/g, 'কইছি')
        .replace(/\bকেন\b/g, 'ক্যান')
        .replace(/\bহবে\b/g, 'হইবো');
    } else if (chosenDialect === 'old-dhaka') {
      res = res
        .replace(/\bএটা\b/g, 'এইডা')
        .replace(/\bসেটা\b/g, 'হেইডা')
        .replace(/\bসে\b/g, 'হেয়')
        .replace(/\bএকটু\b/g, 'ইট্টু')
        .replace(/\bহয়েছে\b/g, 'হইছে')
        .replace(/\bযাচ্ছি\b/g, 'যাইতাছি');
    }
    return res;
  });

  return { transformed: transformedLines.join('\n'), dialectUsed: chosenDialect };
}

export function splitIntoChunks(script: string, maxSegments: number = 10): string[] {
  const paragraphs = script.split('\n').map(p => p.trim()).filter(Boolean);
  const sentences: string[] = [];
  const sepRegex = /([।\?\!\.]+)/;

  for (const para of paragraphs) {
    const isLesson = LESSON_STARTS.some(ls => para.startsWith(ls));
    if (isLesson) {
      sentences.push(para);
      continue;
    }
    const parts = para.split(sepRegex);
    for (let i = 0; i < parts.length; i += 2) {
      const s = parts[i].trim();
      const delim = parts[i + 1] ? parts[i + 1].trim() : '';
      if (s) {
        sentences.push(s + (delim ? delim + ' ' : ' '));
      }
    }
  }

  const chunks: string[] = [];
  let curChunk = '';
  let curWords = 0;
  const MAX_SEGMENT_WORDS = 35;
  const MIN_SEGMENT_WORDS = 18;
  const AVG_WORDS_PER_SEGMENT = 28;

  const countWords = (t: string) => t.trim().split(/\s+/).filter(Boolean).length;

  for (const sent of sentences) {
    const isLesson = LESSON_STARTS.some(ls => sent.trim().startsWith(ls));
    if (isLesson) {
      if (curChunk) {
        chunks.push(curChunk.trim());
        curChunk = '';
        curWords = 0;
      }
      chunks.push(sent.trim());
      continue;
    }

    const w = countWords(sent);
    if (curWords + w <= MAX_SEGMENT_WORDS) {
      curChunk = curChunk ? `${curChunk} ${sent}`.trim() : sent.trim();
      curWords += w;
    } else {
      if (curChunk) chunks.push(curChunk.trim());
      curChunk = sent.trim();
      curWords = w;
    }
  }

  if (curChunk) chunks.push(curChunk.trim());

  const totalWords = countWords(script);
  let desired = Math.round(totalWords / AVG_WORDS_PER_SEGMENT);
  desired = Math.max(3, Math.min(desired, maxSegments));

  // Merge if too many
  while (chunks.length > desired && chunks.length > 2) {
    let minIdx = 0;
    let minLen = 99999;
    for (let i = 0; i < chunks.length - 1; i++) {
      const isL1 = LESSON_STARTS.some(ls => chunks[i].startsWith(ls));
      const isL2 = LESSON_STARTS.some(ls => chunks[i + 1].startsWith(ls));
      if (isL1 || isL2) continue; // avoid merging lesson lines
      const len = countWords(chunks[i]) + countWords(chunks[i + 1]);
      if (len < minLen) {
        minLen = len;
        minIdx = i;
      }
    }
    if (minLen === 99999) break;
    chunks[minIdx] = `${chunks[minIdx]} ${chunks[minIdx + 1]}`;
    chunks.splice(minIdx + 1, 1);
  }

  return chunks.filter(c => c.trim().length > 0);
}

export function generateCharacter(scriptContext: string, mode: 'per_video' | 'fixed' = 'per_video'): CharacterDesign {
  const isRural = /তাঁতি|নদী|মাছ|চাষ|গ্রাম|হাট/.test(scriptContext);
  const isFood = /মসলা|খাবার|রেস্তোরাঁ|দই|মিষ্টি/.test(scriptContext);

  if (mode === 'fixed') {
    return {
      mode: 'fixed',
      name: 'সজীব ভাই (BizMap Host)',
      description: 'A 28-year-old approachable Bangladeshi narrator and digital growth strategist with modern spectacles, navy cotton kurta, welcoming warm expression, plain soft studio backdrop.',
      age_range: '26-30 years',
      gender: 'Male',
      clothing: 'Navy blue contemporary tailored kurta with mandarin collar',
      colors: 'Deep navy, warm ochre, ivory cream',
      style: 'Clean semi-realistic 2D illustration, soft studio key light'
    };
  }

  if (isRural) {
    return {
      mode: 'per_video',
      name: 'রফিক মিয়া (Master Craftsman)',
      description: 'A 45-year-old resilient Bangladeshi artisan with weathered hands, genuine gentle smile, traditional grey panjabi with folded sleeves, clean neutral minimalist workshop background.',
      age_range: '42-48 years',
      gender: 'Male',
      clothing: 'Earthy grey woven panjabi, traditional cotton gamcha on shoulder',
      colors: 'Earthy grey, terracotta amber, slate grey',
      style: 'Clean semi-realistic 2D illustration, warm ambient morning light'
    };
  }

  if (isFood) {
    return {
      mode: 'per_video',
      name: 'কাওসার ভাই (Heritage Merchant)',
      description: 'A 50-year-old heritage merchant with a dignified neat beard, warm friendly eyes, white embroidered punjabi, soft bokeh background with traditional spice jars.',
      age_range: '48-52 years',
      gender: 'Male',
      clothing: 'Crisp white embroidered punjabi, waistcoat',
      colors: 'Ivory white, turmeric saffron, cardamom green',
      style: 'Clean semi-realistic 2D illustration, warm ambient lighting'
    };
  }

  return {
    mode: 'per_video',
    name: 'তারেক রহমান (Modern Entrepreneur)',
    description: 'A 29-year-old energetic Bengali entrepreneur in a teal shirt with smartphone, confident posture, clean clean background with subtle shipping packages.',
    age_range: '27-32 years',
    gender: 'Male',
    clothing: 'Teal smart-casual linen shirt, digital watch',
    colors: 'Teal blue, warm copper, clean pearl white',
    style: 'Clean semi-realistic 2D illustration, modern rim lighting'
  };
}

export function buildSegments(
  chunks: string[],
  character: CharacterDesign
): Segment[] {
  const WORDS_PER_SECOND = 2.5;

  return chunks.map((chunk, index) => {
    const chunkNum = index + 1;
    const words = chunk.split(/\s+/).filter(Boolean).length;
    const duration = Math.max(3.0, Number((words / WORDS_PER_SECOND).toFixed(1)));

    const isLesson = LESSON_STARTS.some(ls => chunk.startsWith(ls));
    const isFirstChunk = index === 0;

    let videoType: 'text-animation' | 'image-to-video' | 'text-to-video';
    let visualPrompt = '';
    let soundDesign = { music_mood: 'Warm inspirational acoustic Bengali folk instrumental', sfx: ['ambient hum'] };

    if (isLesson) {
      videoType = 'text-animation';
      visualPrompt = `Kinetic typography on rich dark gradient slate backdrop, bold golden and ivory Bengali lettering highlighting the core business lesson, clean motion layout.`;
      soundDesign = {
        music_mood: 'Uplifting crescendo with acoustic guitar and subtle chime',
        sfx: ['gentle metallic bell chime', 'soft whoosh transition']
      };
    } else if (isFirstChunk || index === 1) {
      videoType = 'image-to-video';
      visualPrompt = `${character.description}. Medium portrait shot, looking confidently into camera, subtle breathing motion, clean lighting.`;
      soundDesign = {
        music_mood: 'Inspiring and steady acoustic rhythm, dotara and light percussion',
        sfx: ['ambient village breeze', 'soft page turn']
      };
    } else {
      videoType = 'text-to-video';
      visualPrompt = `Vibrant South Asian commerce setting, artisan products neatly displayed, customers engaging, colorful atmospheric marketplace, dynamic camera track forward.`;
      soundDesign = {
        music_mood: 'Energetic entrepreneurial rhythm with tabla and melodic acoustic flute',
        sfx: ['distant bustling market chatter', 'packaging rustle']
      };
    }

    return {
      segment_id: chunkNum,
      chunk: chunkNum,
      text_portion: chunk,
      word_count: words,
      planned_duration_sec: duration,
      video_type: videoType,
      visual_prompt: visualPrompt,
      style_notes: 'clean semi-realistic 2D illustration, soft lighting, warm colors, consistent character',
      sound_design: soundDesign
    };
  });
}

export function generatePlan(options: {
  rawText: string;
  videoNumber?: number;
  dateStr?: string;
  dialect?: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'auto';
  maxSegments?: number;
  characterMode?: 'per_video' | 'fixed';
}): PlanOutput {
  const { rawText, dialect = 'auto', maxSegments = 10, characterMode = 'per_video' } = options;

  // 1. Parse header if present: Video X | YYYY-MM-DD
  const lines = rawText.split('\n');
  let extractedNum = options.videoNumber || 1;
  let extractedDate = options.dateStr || new Date().toISOString().slice(0, 10);
  let detectedDialect: 'none' | 'rangpuri' | 'barishal' | 'old-dhaka' | 'auto' = dialect;
  const contentLines: string[] = [];

  for (const line of lines) {
    const convertedLine = convertBanglaDigits(line.trim());
    const headerMatch = convertedLine.match(/^Video\s*(\d+)\s*[|:\-–—,]\s*(\d{4})-(\d{1,2})-(\d{1,2})/i);
    if (headerMatch) {
      extractedNum = parseInt(headerMatch[1], 10);
      const y = headerMatch[2];
      const m = headerMatch[3].padStart(2, '0');
      const d = headerMatch[4].padStart(2, '0');
      extractedDate = `${y}-${m}-${d}`;
      continue;
    }

    const dialectMatch = line.trim().match(/^Dialect\s*:\s*(\S+)/i);
    if (dialectMatch) {
      const d = dialectMatch[1].toLowerCase();
      if (['none', 'rangpuri', 'barishal', 'old-dhaka', 'auto'].includes(d)) {
        detectedDialect = d as any;
      }
      continue;
    }

    contentLines.push(line);
  }

  const cleanBody = contentLines.join('\n').trim();

  // 2. Dialect transformation
  const { transformed, dialectUsed } = applyDialectTransformation(cleanBody, detectedDialect);

  // 3. Split into chunks
  const chunks = splitIntoChunks(transformed, maxSegments);

  // 4. Character design
  const character = generateCharacter(transformed, characterMode);

  // 5. Segments
  const segments = buildSegments(chunks, character);

  const totalWords = segments.reduce((acc, s) => acc + s.word_count, 0);
  const totalDuration = Number(segments.reduce((acc, s) => acc + s.planned_duration_sec, 0).toFixed(1));

  return {
    video_number: extractedNum,
    date_str: extractedDate,
    video_label: `Video ${extractedNum} | ${extractedDate}`,
    dialect_used: dialectUsed,
    character,
    master_script_bn: transformed,
    original_script_bn: cleanBody,
    total_words: totalWords,
    total_duration_sec: totalDuration,
    segments,
    timestamp: new Date().toISOString()
  };
}
