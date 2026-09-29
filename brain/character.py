
import os, pathlib
def get_character(mode, story_context, llm_pool):
    mode=mode.lower()
    if mode=="fixed":
        ref_path=pathlib.Path(__file__).parent / "assets" / "host_reference.png"
        desc_path=pathlib.Path(__file__).parent / "assets" / "host_description.txt"
        if not ref_path.exists():
            raise RuntimeError("CHARACTER_MODE fixed but brain/assets/host_reference.png missing")
        if not desc_path.exists():
            raise RuntimeError("CHARACTER_MODE fixed but brain/assets/host_description.txt missing")
        desc=desc_path.read_text(encoding="utf-8").strip()[:500]
        print(f"Using fixed character: {desc[:80]}")
        return {"mode":"fixed","description":desc}
    import pathlib as pl
    tmpl_path=pl.Path(__file__).parent / "prompts" / "character_prompt.txt"
    tmpl=tmpl_path.read_text(encoding="utf-8")
    prompt=tmpl.replace("{STORY_CONTEXT}", story_context[:2000])
    try:
        out=llm_pool.call(prompt, preferred_providers=["gemini","groq","openrouter","nvidia","workers-ai"])
        desc=out.strip().replace("\n"," ")[:300]
        if not desc:
            raise ValueError("empty")
        words=desc.split()
        if len(words)>60:
            desc=" ".join(words[:60])
        print(f"Generated character: {desc}")
        return {"mode":"per_video","description":desc}
    except Exception as e:
        print(f"Character LLM failed: {e}, using fallback")
        fallback="A friendly young Bangladeshi adult, 25-30 years, wearing casual modest clothing in warm colors, clean semi-realistic 2D illustration style, plain light background, portrait centered"
        return {"mode":"per_video","description":fallback}
