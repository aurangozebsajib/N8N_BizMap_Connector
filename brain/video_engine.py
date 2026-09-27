import requests, os, base64

def generate_segment(hf_pool, routing, segment, ref_image_path, character_desc):
    vtype = segment["video_type"]
    models = routing.get(vtype, [])
    if not models:
        print(f"No models for {vtype} in Model_Routing")
        return None, None, "failed-no-model-available"

    visual = segment.get("visual_prompt","") + f" Style: {character_desc} {segment.get('style_notes','')}"
    needs_image = vtype in ["image-to-video", "lip-sync"]

    # Pre-check for image consistency requirement
    if needs_image:
        if not ref_image_path or not os.path.exists(ref_image_path):
            print(f"[ERROR] Segment {segment['segment_id']} type={vtype} requires reference image but not found: {ref_image_path}")
            return None, None, "failed-no-model-available"

    for model_row in models:
        model_id = model_row["model_id"]
        for _ in range(len(hf_pool.keys)):
            kobj = hf_pool.next()
            url = f"https://api-inference.huggingface.co/models/{model_id}"

            if needs_image:
                # MUST include image - try 2 formats, never text-only
                print(f"Segment {segment['segment_id']} | {kobj['key_id']} | {model_id} | {vtype} | image_included=True | Attempting format A (raw bytes)")
                # Load image bytes once
                try:
                    with open(ref_image_path, "rb") as f:
                        img_bytes = f.read()
                    b64_img = base64.b64encode(img_bytes).decode('utf-8')
                except Exception as e:
                    print(f"[ERROR] Could not read ref image {ref_image_path}: {e}")
                    continue

                success = False
                last_error = ""
                
                # Format A: raw image bytes as body, Content-Type: image/png, prompt as query param
                try:
                    headers_a = {
                        "Authorization": f"Bearer {kobj['api_key_value']}",
                        "Content-Type": "image/png"
                    }
                    r = requests.post(url, headers=headers_a, data=img_bytes, params={"prompt": visual}, timeout=240)
                    if r.status_code == 200:
                        ext = ".mp4"
                        ctype = r.headers.get("Content-Type","")
                        if "image" in ctype:
                            ext = ".png"
                        out_path = f"output/segment_{segment['segment_id']}{ext}"
                        os.makedirs("output", exist_ok=True)
                        with open(out_path, "wb") as out:
                            out.write(r.content)
                        print(f"Segment {segment['segment_id']} SUCCESS with format A | image_included=True | model={model_id} | key={kobj['key_id']}")
                        return out_path, model_id, "success"
                    else:
                        last_error = f"Format A failed {r.status_code}: {r.text[:300]}"
                        print(last_error)
                except Exception as e:
                    last_error = f"Format A exception: {e}"
                    print(last_error)

                # Format B: JSON body {"inputs": "<base64-encoded image>", "parameters": {"prompt": visual_prompt}}
                print(f"Segment {segment['segment_id']} | {kobj['key_id']} | {model_id} | {vtype} | image_included=True | Attempting format B (base64 JSON)")
                try:
                    headers_b = {
                        "Authorization": f"Bearer {kobj['api_key_value']}",
                        "Content-Type": "application/json"
                    }
                    payload_b = {
                        "inputs": b64_img,
                        "parameters": {"prompt": visual}
                    }
                    r = requests.post(url, headers=headers_b, json=payload_b, timeout=240)
                    if r.status_code == 200:
                        ext = ".mp4"
                        ctype = r.headers.get("Content-Type","")
                        if "image" in ctype:
                            ext = ".png"
                        out_path = f"output/segment_{segment['segment_id']}{ext}"
                        os.makedirs("output", exist_ok=True)
                        with open(out_path, "wb") as out:
                            out.write(r.content)
                        print(f"Segment {segment['segment_id']} SUCCESS with format B | image_included=True | model={model_id} | key={kobj['key_id']}")
                        return out_path, model_id, "success"
                    else:
                        print(f"Format B failed {r.status_code}: {r.text[:300]}")
                except Exception as e:
                    print(f"Format B exception: {e}")

                # Both formats failed for this key+model -> move to next key
                print(f"Segment {segment['segment_id']} | {kobj['key_id']} | {model_id} | FAILED both image formats | image_included=True | moving to next key/model")
                continue

            else:
                # text-to-video and text-animation: text only is OK
                try:
                    print(f"Segment {segment['segment_id']} | {kobj['key_id']} | {model_id} | {vtype} | image_included=False")
                    headers = {"Authorization": f"Bearer {kobj['api_key_value']}"}
                    r = requests.post(url, headers=headers, json={"inputs": visual}, timeout=240)
                    if r.status_code == 200:
                        ext = ".mp4"
                        ctype = r.headers.get("Content-Type","")
                        if "image" in ctype:
                            ext = ".png"
                        out_path = f"output/segment_{segment['segment_id']}{ext}"
                        os.makedirs("output", exist_ok=True)
                        with open(out_path, "wb") as out:
                            out.write(r.content)
                        return out_path, model_id, "success"
                    else:
                        print(f"Model failed {r.status_code}: {r.text[:300]}")
                except Exception as e:
                    print(f"Failed: {e}")
                    continue

    # If we reach here, every model_id + every key failed
    print(f"Segment {segment['segment_id']} FINAL FAILURE: all models/keys failed | status=failed-no-model-available")
    return None, None, "failed-no-model-available"
