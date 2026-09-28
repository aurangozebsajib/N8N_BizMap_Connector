
import time, requests
import brain.config as cfg
def _model_for_key(provider, entry):
    c=entry.get("model","").strip()
    if c:
        return c
    if provider=="groq": return cfg.DEFAULT_GROQ_MODEL
    if provider=="gemini": return cfg.DEFAULT_GEMINI_MODEL
    if provider=="nvidia": return cfg.DEFAULT_NVIDIA_MODEL
    if provider=="workers-ai": return cfg.DEFAULT_WORKERS_AI_MODEL
    if provider=="openrouter": return cfg.DEFAULT_OPENROUTER_MODEL
    return ""
def _build(provider, model, prompt, api_key, account_id=""):
    if provider=="groq":
        return "https://api.groq.com/openai/v1/chat/completions", {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}, {"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0.3}
    if provider=="openrouter":
        return "https://openrouter.ai/api/v1/chat/completions", {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}, {"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0.3}
    if provider=="gemini":
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", {"x-goog-api-key":api_key,"Content-Type":"application/json"}, {"contents":[{"parts":[{"text":prompt}]}]}
    if provider=="nvidia":
        return "https://integrate.api.nvidia.com/v1/chat/completions", {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}, {"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0.3}
    if provider=="workers-ai":
        if not account_id:
            return None,None,None
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}", {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}, {"prompt":prompt}
    return None,None,None
def _extract(provider, j):
    try:
        if provider=="gemini":
            c=j.get("candidates",[])
            if c:
                p=c[0].get("content",{}).get("parts",[])
                if p: return p[0].get("text","")
        elif provider=="workers-ai":
            r=j.get("result",{})
            if isinstance(r,dict):
                if "response" in r: return r["response"]
                if "output" in r: return r["output"]
            if isinstance(r,str): return r
            return j.get("response","") or ""
        else:
            ch=j.get("choices",[])
            if ch:
                m=ch[0].get("message",{})
                return m.get("content","") or ch[0].get("text","")
    except:
        pass
    return ""
class LLMPool:
    def __init__(self, keys):
        self.keys=keys
        self.cooldown={}
        self.dead=set()
    def _avail(self,kid):
        if kid in self.dead: return False
        return time.time() >= self.cooldown.get(kid,0)
    def call(self, prompt, preferred_providers=None, max_retries_loop=1):
        if not self.keys:
            raise RuntimeError("No keys")
        if preferred_providers:
            om={p:i for i,p in enumerate(preferred_providers)}
            sk=sorted(self.keys, key=lambda k: om.get(k["provider"],999))
        else:
            sk=list(self.keys)
        last=None
        for loop in range(max_retries_loop+1):
            for ke in sk:
                kid=ke.get("key_id","")
                pv=ke.get("provider","").lower()
                ak=ke.get("api_key_value","")
                aid=ke.get("account_id","")
                model=_model_for_key(pv,ke)
                if not self._avail(kid): continue
                url,h,b=_build(pv,model,prompt,ak,aid)
                if url is None:
                    if pv=="workers-ai" and not aid:
                        print(f"Skipping workers-ai {kid}: missing account_id")
                        self.dead.add(kid)
                    else:
                        print(f"Warning unknown provider {pv} for {kid}, skipping")
                    continue
                try:
                    resp=requests.post(url,headers=h,json=b,timeout=cfg.LLM_TIMEOUT_SEC)
                except requests.exceptions.RequestException as e:
                    print(f"LLM error {pv} {kid}: {type(e).__name__}")
                    last=e
                    continue
                if resp.status_code in (401,403):
                    print(f"LLM auth fail {pv} {kid} {resp.status_code} -> dead for run")
                    self.dead.add(kid); last=f"{pv} {resp.status_code}"; continue
                if resp.status_code in (429,402):
                    print(f"LLM rate {pv} {kid} {resp.status_code} -> cooldown 60s")
                    self.cooldown[kid]=time.time()+60; last=f"{pv} {resp.status_code}"; continue
                if resp.status_code>=400:
                    print(f"LLM error {pv} {kid} status={resp.status_code} -> next key")
                    last=f"{pv} {resp.status_code}"; continue
                try:
                    j=resp.json()
                except:
                    print(f"LLM bad JSON {pv} {kid}"); last="bad json"; continue
                txt=_extract(pv,j)
                if not txt:
                    print(f"LLM empty {pv} {kid}"); last="empty"; continue
                return txt
            if loop<max_retries_loop:
                print(f"All keys failed, waiting 30s before retry loop {loop+1}")
                time.sleep(30)
        raise RuntimeError(f"All LLM keys failed last={last}")
def create_pool():
    from brain.sheets import load_brain_keys
    return LLMPool(load_brain_keys())
