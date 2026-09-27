import re, requests, json

def extract_case(doc_text, target_index=0):
    cases = re.split(r'(Case\s*\d+)', doc_text, flags=re.I)
    full_cases = []
    for i in range(1, len(cases), 2):
        header = cases[i].strip()
        body = cases[i+1].strip() if i+1 < len(cases) else ""
        full_cases.append(f"{header}\n{body}")
    if not full_cases:
        return "Case 1", doc_text[:4000]
    chosen = full_cases[target_index % len(full_cases)]
    m = re.search(r'Case\s*\d+', chosen, re.I)
    case_id = m.group(0) if m else f"Case {target_index+1}"
    return case_id, chosen

# --- Provider-specific request functions ---

def _call_groq(key, prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role":"user","content": prompt_text}],
        "temperature": 0.7
    }
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _call_openrouter(key, prompt_text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role":"user","content": prompt_text}],
        "temperature": 0.7
    }
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _call_gemini(key, prompt_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    data = r.json()
    # response["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise Exception(f"Gemini parse error: {data} - {e}")

def _call_nvidia(key, prompt_text):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    # Use small free NIM model - llama 3.1 8b
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [{"role":"user","content": prompt_text}],
        "temperature": 0.7,
        "max_tokens": 2048
    }
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _call_workers_ai(kobj, prompt_text):
    # Needs account_id column from sheet
    account_id = str(kobj.get("account_id","") or "").strip()
    if not account_id:
        print(f"Skipping {kobj.get('key_id')} - workers-ai provider but account_id column missing/empty")
        return None, True  # True = skip signal
    key = kobj["api_key_value"]
    # Use a default free model if not specified - llama
    model = "@cf/meta/llama-3.1-8b-instruct"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"prompt": prompt_text}
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    data = r.json()
    # Cloudflare response is in result.response or result
    if "result" in data:
        res = data["result"]
        if isinstance(res, dict):
            return res.get("response") or res.get("result") or str(res), False
        return str(res), False
    return str(data), False

def call_brain_llm_with_pool(pool, prompt_text):
    for _ in range(len(pool.keys)):
        kobj = pool.next()
        key = kobj["api_key_value"]
        provider = str(kobj.get("provider","")).strip().lower()
        key_id = kobj.get("key_id","unknown")

        print(f"Trying {key_id} ({provider})...")

        try:
            if provider == "groq":
                result = _call_groq(key, prompt_text)
                return result
            elif provider == "openrouter":
                result = _call_openrouter(key, prompt_text)
                return result
            elif provider == "gemini":
                result = _call_gemini(key, prompt_text)
                return result
            elif provider == "nvidia":
                result = _call_nvidia(key, prompt_text)
                return result
            elif provider in ("workers-ai", "workers_ai", "cloudflare", "workers"):
                result, was_skip = _call_workers_ai(kobj, prompt_text)
                if was_skip:
                    continue
                return result
            else:
                print(f"Unknown provider '{provider}' for key {key_id}, skipping")
                continue
        except Exception as e:
            print(f"Failed {key_id} ({provider}): {e}")
            continue

    raise Exception("All BRAIN keys failed - no provider succeeded")
