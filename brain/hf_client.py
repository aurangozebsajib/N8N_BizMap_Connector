import time
import os
import base64
import brain.config as cfg

try:
    import requests
except ImportError:
    requests = None

HF_ROUTERS = [
    "https://router.huggingface.co/hf-inference/models",
    "https://api-inference.huggingface.co/models"
]

class HFPool:
    def __init__(self, hf_keys):
        self.keys = hf_keys or []
        self.cooldown = {}
        self.dead = set()
        self.skipped_models = set()
        print(f"HFPool initialized with {len(self.keys)} API keys.")

    def _avail(self, kid):
        if kid in self.dead:
            return False
        return time.time() >= self.cooldown.get(kid, 0)

    def call_text_to_image(self, model_id, prompt, save_path):
        return self._call_model(model_id, prompt, save_path, is_video=False, ref_image_path=None)

    def call_video(self, model_id, prompt, save_path, ref_image_path=None):
        return self._call_model(model_id, prompt, save_path, is_video=True, ref_image_path=ref_image_path)

    def _call_model(self, model_id, prompt, save_path, is_video=True, ref_image_path=None):
        if model_id in self.skipped_models:
            print(f"Skipping model {model_id} previously marked bad.")
            return False, f"skipped_{model_id}"

        if not self.keys:
            print("No HF keys available in pool.")
            return False, "no_keys_in_pool"

        if requests is None:
            print("requests library not available for HF API calls.")
            return False, "no_requests_library"

        for router_base in HF_ROUTERS:
            url = f"{router_base}/{model_id}"

            for key_entry in self.keys:
                kid = key_entry["key_id"]
                ak = key_entry["api_key_value"]

                if not self._avail(kid):
                    continue

                headers = {"Authorization": f"Bearer {ak}"}

                # IMAGE-TO-VIDEO Task
                if is_video and ref_image_path and os.path.exists(ref_image_path):
                    success, msg = self._try_img2vid(url, ak, kid, model_id, prompt, ref_image_path, save_path)
                    if success:
                        return True, model_id
                    continue

                # TEXT-TO-IMAGE or TEXT-TO-VIDEO Task
                body = {"inputs": prompt}
                try:
                    resp = requests.post(url, headers=headers, json=body, timeout=cfg.HF_TIMEOUT_SEC)
                except requests.exceptions.RequestException as e:
                    print(f"HF request error model={model_id} key={kid}: {e}")
                    continue

                # Handle Status Codes
                if resp.status_code in (401, 403):
                    print(f"❌ HF Auth fail key={kid} status={resp.status_code} -> marking dead")
                    self.dead.add(kid)
                    continue

                if resp.status_code in (402, 429):
                    print(f"⚠️ HF Rate limit key={kid} -> cooldown 120s")
                    self.cooldown[kid] = time.time() + 120
                    continue

                if resp.status_code == 503:
                    # Model is loading
                    wait_time = 20
                    try:
                        j = resp.json()
                        wait_time = int(min(j.get("estimated_time", 20), 45))
                    except Exception:
                        pass
                    print(f"⏳ HF Model {model_id} loading. Waiting {wait_time}s and retrying...")
                    time.sleep(wait_time)
                    try:
                        resp = requests.post(url, headers=headers, json=body, timeout=cfg.HF_TIMEOUT_SEC)
                    except Exception:
                        continue

                if resp.status_code in (404, 410, 422):
                    print(f"⚠️ HF skip model {model_id} status {resp.status_code}")
                    self.skipped_models.add(model_id)
                    break

                if resp.status_code != 200:
                    print(f"HF error model={model_id} status={resp.status_code}: {resp.text[:100]}")
                    continue

                content = resp.content
                body_len = len(content)

                # Validate response size (real videos or images are at least 5KB)
                if body_len < 3 * 1024:
                    print(f"⚠️ HF body too small ({body_len} bytes) for {model_id}. Likely empty or corrupt.")
                    continue

                ctype = resp.headers.get("Content-Type", "")
                if is_video and not (ctype.startswith("video/") or ctype.startswith("image/") or "octet-stream" in ctype):
                    print(f"⚠️ HF task got non-media Content-Type: {ctype}")
                    continue

                # Save valid bytes
                with open(save_path, "wb") as f:
                    f.write(content)

                print(f"✅ HF success {model_id} -> {save_path} ({body_len} bytes, type={ctype})")
                return True, model_id

        return False, "all_hf_keys_or_models_failed"

    def _try_img2vid(self, url, api_key, kid, model_id, prompt, ref_image_path, save_path):
        """
        Attempts image-to-video using binary image upload (Format A) or JSON base64 (Format B)
        """
        try:
            with open(ref_image_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            return False, f"ref_read_error_{e}"

        # Format A: Binary upload with URL prompt parameter
        headers_a = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "image/png"
        }
        url_a = url + f"?prompt={prompt[:400]}"
        try:
            resp = requests.post(url_a, headers=headers_a, data=img_bytes, timeout=cfg.HF_TIMEOUT_SEC)
            if resp.status_code == 200 and len(resp.content) >= 5 * 1024:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"✅ HF img2vid Format A success: {model_id} ({len(resp.content)} bytes)")
                return True, "format_A_success"
        except Exception:
            pass

        # Format B: JSON base64 body
        headers_b = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        body_b = {
            "inputs": b64_img,
            "parameters": {"prompt": prompt}
        }
        try:
            resp = requests.post(url, headers=headers_b, json=body_b, timeout=cfg.HF_TIMEOUT_SEC)
            if resp.status_code == 200 and len(resp.content) >= 5 * 1024:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"✅ HF img2vid Format B success: {model_id} ({len(resp.content)} bytes)")
                return True, "format_B_success"
        except Exception:
            pass

        return False, "img2vid_both_formats_failed"
