from text_engine import call_brain_llm_with_pool
import requests, os

def design_character(pool, case_text, character_prompt_template):
    prompt = character_prompt_template.replace("{CASE_TEXT}", case_text)
    desc = call_brain_llm_with_pool(pool, prompt)
    return desc.strip()

def generate_reference_image(hf_pool, routing, character_desc):
    models = routing.get("text-to-image", [])
    if not models:
        raise Exception("No text-to-image models in Model_Routing tab")
    for model_row in models:
        model_id = model_row["model_id"]
        for _ in range(len(hf_pool.keys)):
            kobj = hf_pool.next()
            print(f"Trying HF {kobj['key_id']} with model {model_id}")
            try:
                url = f"https://api-inference.huggingface.co/models/{model_id}"
                headers = {"Authorization": f"Bearer {kobj['api_key_value']}"}
                r = requests.post(url, headers=headers, json={"inputs": character_desc}, timeout=180)
                if r.status_code == 200:
                    os.makedirs("output", exist_ok=True)
                    path = "output/character_ref.png"
                    with open(path, "wb") as f:
                        f.write(r.content)
                    return path, model_id, kobj['key_id']
                else:
                    print(f"HF error {r.status_code}: {r.text[:300]}")
            except Exception as e:
                print(f"HF failed: {e}")
                continue
    raise Exception("All HF fallbacks failed for reference image")
