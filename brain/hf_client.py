
import time, os, base64, requests
import brain.config as cfg
HF_ROUTER="https://router.huggingface.co/hf-inference/models"
class HFPool:
    def __init__(self, hf_keys):
        self.keys=hf_keys
        self.cooldown={}
        self.dead=set()
        self.skipped_models=set()
    def _avail(self,kid):
        if kid in self.dead: return False
        return time.time() >= self.cooldown.get(kid,0)
    def call_text_to_image(self, model_id, prompt, save_path):
        return self._call_model(model_id, prompt, save_path, is_video=False, ref_image=None)
    def call_video(self, model_id, prompt, save_path, ref_image_path=None):
        return self._call_model(model_id, prompt, save_path, is_video=True, ref_image=ref_image_path)
    def _call_model(self, model_id, prompt, save_path, is_video, ref_image):
        if model_id in self.skipped_models:
            print(f"Skipping model {model_id} previously marked bad")
            return False, f"skipped {model_id}"
        url=f"{HF_ROUTER}/{model_id}"
        for key_entry in self.keys:
            kid=key_entry["key_id"]
            ak=key_entry["api_key_value"]
            if not self._avail(kid):
                continue
            if model_id in self.skipped_models:
                break
            if ref_image is not None:
                success, msg = self._try_image_to_video_formats(url, ak, kid, model_id, prompt, ref_image, save_path)
                if success:
                    return True, model_id
                else:
                    if "skip_model" in msg:
                        self.skipped_models.add(model_id)
                        print(f"Model {model_id} marked to skip: {msg}")
                        break
                    continue
            else:
                headers={"Authorization": f"Bearer {ak}"}
                body={"inputs": prompt}
                try:
                    resp=requests.post(url, headers=headers, json=body, timeout=cfg.HF_TIMEOUT_SEC)
                except requests.exceptions.RequestException as e:
                    print(f"HF call error model={model_id} key={kid} {type(e).__name__}")
                    continue
                if resp.status_code in (401,403):
                    print(f"HF auth fail {kid} {resp.status_code} -> dead")
                    self.dead.add(kid)
                    continue
                if resp.status_code in (402,429):
                    print(f"HF rate {kid} {resp.status_code} -> cooldown 120s")
                    self.cooldown[kid]=time.time()+120
                    continue
                if resp.status_code==503:
                    try:
                        j=resp.json()
                        est=j.get("estimated_time",20)
                    except:
                        est=20
                    wait=min(est,60)
                    print(f"HF 503 model loading {model_id} wait {wait}s retry")
                    time.sleep(wait)
                    for _ in range(2):
                        try:
                            resp2=requests.post(url, headers=headers, json=body, timeout=cfg.HF_TIMEOUT_SEC)
                        except:
                            break
                        if resp2.status_code==503:
                            try:
                                j2=resp2.json()
                                est2=j2.get("estimated_time",10)
                            except:
                                est2=10
                            time.sleep(min(est2,30))
                            continue
                        else:
                            resp=resp2
                            break
                if resp.status_code in (404,410,400,422):
                    print(f"HF skip model {model_id} status {resp.status_code}")
                    self.skipped_models.add(model_id)
                    break
                if resp.status_code>=500:
                    print(f"HF 5xx {model_id} {resp.status_code} -> next key")
                    continue
                if resp.status_code!=200:
                    print(f"HF error {model_id} status {resp.status_code}")
                    continue
                ctype=resp.headers.get("Content-Type","")
                body_len=len(resp.content)
                if body_len < 5*1024:
                    print(f"HF body too small {body_len} for {model_id}")
                    continue
                if is_video:
                    if not (ctype.startswith("video/") or ctype.startswith("image/")):
                        print(f"HF video task got ctype {ctype} not video/image -> fail")
                        continue
                else:
                    if not ctype.startswith("image/"):
                        print(f"HF image task got ctype {ctype}")
                        continue
                with open(save_path,"wb") as f:
                    f.write(resp.content)
                print(f"HF success {model_id} -> {save_path} ctype {ctype} size {body_len}")
                return True, model_id
        return False, "all keys/models failed"
    def _try_image_to_video_formats(self, url, api_key, kid, model_id, prompt, ref_image_path, save_path):
        headers_a={"Authorization": f"Bearer {api_key}", "Content-Type":"image/png"}
        try:
            with open(ref_image_path,"rb") as f:
                img_bytes=f.read()
        except Exception as e:
            return False, f"ref image read fail {e}"
        url_a = url + f"?prompt={requests.utils.quote(prompt[:500])}"
        try:
            resp=requests.post(url_a, headers=headers_a, data=img_bytes, timeout=cfg.HF_TIMEOUT_SEC)
        except Exception as e:
            print(f"HF img2vid A error {model_id} {kid} {e}")
            resp=None
        if resp is not None:
            if resp.status_code in (401,403):
                print(f"HF A auth fail {kid}"); self.dead.add(kid)
            elif resp.status_code in (402,429):
                print(f"HF A rate {kid}"); self.cooldown[kid]=time.time()+120
            elif resp.status_code==503:
                try:
                    j=resp.json()
                    est=j.get("estimated_time",20)
                except:
                    est=20
                wait=min(est,60)
                print(f"HF A 503 wait {wait}s")
                time.sleep(wait)
                try:
                    resp=requests.post(url_a, headers=headers_a, data=img_bytes, timeout=cfg.HF_TIMEOUT_SEC)
                except:
                    pass
            if resp is not None and resp.status_code==200:
                ctype=resp.headers.get("Content-Type","")
                if len(resp.content)>=5*1024 and (ctype.startswith("video/") or ctype.startswith("image/")):
                    with open(save_path,"wb") as f:
                        f.write(resp.content)
                    print(f"HF A success {model_id}")
                    return True, "A"
            if resp is not None and resp.status_code in (404,410,400,422):
                return False, f"skip_model A {resp.status_code}"
        headers_b={"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
        try:
            b64=base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            return False, f"b64 fail {e}"
        body_b={"inputs": b64, "parameters":{"prompt": prompt}}
        try:
            resp=requests.post(url, headers=headers_b, json=body_b, timeout=cfg.HF_TIMEOUT_SEC)
        except Exception as e:
            print(f"HF img2vid B error {model_id} {kid} {e}")
            return False, "B exception"
        if resp.status_code in (401,403):
            print(f"HF B auth fail {kid}"); self.dead.add(kid); return False, "auth"
        if resp.status_code in (402,429):
            print(f"HF B rate {kid}"); self.cooldown[kid]=time.time()+120; return False, "rate"
        if resp.status_code in (404,410,400,422):
            return False, f"skip_model B {resp.status_code}"
        if resp.status_code!=200:
            print(f"HF B status {resp.status_code} for {model_id}")
            return False, f"B status {resp.status_code}"
        ctype=resp.headers.get("Content-Type","")
        if len(resp.content)<5*1024:
            return False, "B small body"
        if not (ctype.startswith("video/") or ctype.startswith("image/")):
            print(f"HF B wrong ctype {ctype}")
            return False, "B wrong ctype"
        with open(save_path,"wb") as f:
            f.write(resp.content)
        print(f"HF B success {model_id}")
        return True, "B"
