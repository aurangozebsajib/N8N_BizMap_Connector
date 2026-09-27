HOW TO UPLOAD TO GITHUB - FOR NON-TECHNICAL OWNER

1. Unzip this file on your computer
2. You will see folder: brain/ and .github/
3. Go to your GitHub repo bangla-factory
4. Click Add file -> Upload files
5. Drag the brain folder and .github folder into GitHub
6. Click Commit

7. In Google Sheets, create these 4 tabs if not exist:
   - API_Keys_Brain (columns: key_id, api_key_value, provider, account_id, status, last_used)
     account_id is REQUIRED only for provider=workers-ai (your Cloudflare Account ID)
   - API_Keys_HF (columns: key_id, api_key_value, status, notes)
   - Model_Routing (columns: task_type, model_id, priority, notes)
   - Video_Outputs (columns: case_id, segment_id, video_type, model_used, character_ref_image, output_artifact, status)

Example rows for Model_Routing:
text-to-image | stabilityai/stable-diffusion-xl-base-1.0 | 1 | fast
text-to-video | damo-vilab/modelscope-text-to-video-synthesis | 1 | 
image-to-video | stabilityai/stable-video-diffusion-img2vid-xt | 1 |
lip-sync | your-lipsync-model-id | 1 |
text-animation | your-text-animation-model-id | 1 |

8. In GitHub repo -> Settings -> Secrets -> Only keep 3 secrets:
   GOOGLE_SERVICE_JSON, GOOGLE_DOC_ID, GOOGLE_SHEET_ID

9. Go to Actions tab -> brain-factory -> Run workflow
