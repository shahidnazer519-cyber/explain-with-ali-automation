import os
import shutil
import requests
import subprocess
import json
import time
import random
from datetime import datetime
from google import genai
from google.genai import types

# 🔐 Environment Variables (Secrets)
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY")  # e.g., "username/repo"
BRANCH = "main"

VIDEO_DIR = "videos"
ARCHIVE_DIR = "archive"
LOGO_PATH = "logo.png"
HISTORY_FILE = "history.json"

# Ensure directories exist
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ==========================================
# 1. Load Upload History (With Crash Protection)
# ==========================================
history_data = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                history_data = json.loads(content)
    except Exception as e:
        print(f"⚠️ History file read error ({e}). Resetting to clean []...")
        history_data = []

uploaded_files = [item["original_filename"] for item in history_data if isinstance(item, dict) and "original_filename" in item]

# ==========================================
# 2. Scan for MP4 video files (Case-Insensitive)
# ==========================================
videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4") and not f.startswith("processed_")]

if not videos:
    print("⚠️ Koi raw video file nahi mili 'videos/' folder mein! Process stopping.")
    exit(0)

# ==========================================
# 3. Find the first video NOT in history
# ==========================================
video_file = None
for v in sorted(videos):
    if v not in uploaded_files:
        video_file = v
        break

if not video_file:
    print("⏸️ 'videos/' folder ki sari files pehle hi upload ho chuki hain (History checked). No new video to upload!")
    exit(0)

raw_video_path = os.path.join(VIDEO_DIR, video_file)
processed_video_file = f"processed_{video_file}"
processed_video_path = os.path.join(VIDEO_DIR, processed_video_file)

print(f"🎬 Processing new video: '{video_file}'...")

# ==========================================
# 🛡️ ADVANCED PYTHON BACKUP SEO ENGINE
# ==========================================
def generate_fallback_metadata(filename):
    print("⚡ Activating Advanced Python Backup SEO Engine...")
    clean_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
    
    hooks = ["Ending Explained!", "Mind-Blowing Story!", "Don't Miss This!", "Dark Korean Thriller!"]
    selected_hook = random.choice(hooks)
    
    title = f"{clean_name}: {selected_hook} | Explain With Ali #shorts"
    
    description = (
        f"🎬 {clean_name} - Short Korean Movie Explanation Reel in Urdu/Hindi by Ali.\n\n"
        f"🔥 Welcome to Explain With Ali! In this 1-minute short, we dive into the intense story, "
        f"hidden details, and crazy ending of this masterpiece.\n\n"
        f"👉 Subscribe for daily 1-minute movie breakdowns!\n\n"
        f"#ExplainWithAli #KoreanMovieHindi #MovieExplanation #Shorts #Reels #HindiExplain #Kdrama"
    )
    
    tags = [
        "Explain With Ali", "Korean Movie in Hindi", "Movie Explanation", "Shorts", "Reels",
        "Korean Drama Hindi", "Hindi Explain", "Urdu Explain", "1 Minute Movie", "Movie Summary",
        "Korean Movie Urdu", "Ali Explains", "Viral Shorts", "Trending Reels", clean_name
    ]
    
    return {"title": title, "description": description, "tags": tags}

# ==========================================
# 🧠 GEMINI AI - GEMINI 3.1 PRIORITY SYSTEM
# ==========================================
title, description, tags = None, None, None

if GEMINI_API_KEY:
    print("🤖 Initializing Gemini AI Engine...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    movie_context = os.path.splitext(video_file)[0].replace("_", " ").title()
    
    prompt = f"""
    You are an expert SEO manager for a YouTube Shorts and Facebook Reels channel named "Explain With Ali".
    The channel uploads 1-minute Korean movie explanations and summaries in Hindi/Urdu.
    The video filename/topic is: "{movie_context}"
    
    Generate viral metadata in strict JSON format with exactly these keys:
    "title": Catchy title for YouTube Shorts (Max 60 characters, MUST end with " | Explain With Ali #shorts").
    "description": 3-line engaging description in English/Hindi mix explaining this is a 1-min movie summary by Ali, ending with 5 viral hashtags.
    "tags": Array of 15 strong SEO keyword tags (strings only).
    
    Return ONLY JSON. No markdown backticks.
    """
    
    # 🔥 Updated Priority: Gemini 3.1 -> Gemini 3.0 -> Latest active fallbacks
    available_models = ['gemini-3.1-flash', 'gemini-3.1-pro', 'gemini-3.0-flash', 'gemini-2.5-flash-latest']
    ai_success = False
    
    for model_name in available_models:
        if ai_success:
            break
            
        print(f"🔄 Attempting with AI Model: {model_name}...")
        
        for attempt in range(1, 4):
            try:
                print(f"   [Attempt {attempt}/3] Sending request to {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        response_mime_type="application/json"
                    )
                )
                
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                ai_data = json.loads(raw_text.strip())
                title = ai_data.get("title")
                description = ai_data.get("description")
                tags = ai_data.get("tags")
                
                if title and description and tags:
                    print(f"✅ Success with {model_name} on attempt {attempt}!")
                    ai_success = True
                    break
                    
            except Exception as e:
                print(f"   ⚠️ Error on {model_name} (Attempt {attempt}): {e}")
                time.sleep(2)
                
    if not ai_success:
        print("❌ All Gemini AI models failed or unavailable! Switching to fallback engine.")
        ai_data = generate_fallback_metadata(video_file)
        title, description, tags = ai_data["title"], ai_data["description"], ai_data["tags"]

else:
    print("⚠️ GEMINI_API_KEY not found in secrets! Switching to fallback engine.")
    ai_data = generate_fallback_metadata(video_file)
    title, description, tags = ai_data["title"], ai_data["description"], ai_data["tags"]

print(f"\n📌 FINAL TITLE: {title}\n")

# ==========================================
# 📹 FFmpeg Transformation Logic
# ==========================================
print("🛠️ Running FFmpeg to make video copyright-safe...")
if os.path.exists(LOGO_PATH):
    filter_str = '[0:v]hflip[flipped];[1:v]scale=180:-1[watermark];[flipped][watermark]overlay=W-w-15:H-h-15'
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', raw_video_path, '-i', LOGO_PATH,
        '-filter_complex', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'copy',
        processed_video_path
    ]
else:
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', raw_video_path, '-vf', 'hflip',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'copy',
        processed_video_path
    ]

try:
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("✅ FFmpeg transformation successful!")
except subprocess.CalledProcessError as e:
    print(f"❌ FFmpeg Error:\n{e.stderr.decode()}")
    exit(1)

# ==========================================
# 🚀 Webhook Upload With 3-RETRY PROTECTION
# ==========================================
if not WEBHOOK_URL:
    print("❌ MAKE_WEBHOOK_URL environment variable missing! Cannot send to Make.com")
    exit(1)

form_data = {
    "filename": processed_video_file,
    "title": title,
    "description": description,
    "tags_string": ", ".join(tags) if isinstance(tags, list) else str(tags)
}

webhook_success = False

for attempt in range(1, 4):
    print(f"🚀 [Attempt {attempt}/3] Sending ACTUAL VIDEO FILE directly to Make.com Webhook...")
    try:
        # File stream ko har retry par fresh open karna zaroori hai
        with open(processed_video_path, "rb") as video_stream:
            files = {
                'file': (processed_video_file, video_stream, 'video/mp4')
            }
            # 120 seconds (2 mins) ka timeout taake Make.com aram se bari file process kar sake
            res = requests.post(WEBHOOK_URL, data=form_data, files=files, timeout=120)
        
        if res.status_code == 200:
            print("✅ Webhook successfully triggered with Direct Video File!")
            webhook_success = True
            break
        else:
            print(f"⚠️ Webhook server error! Status Code: {res.status_code}\nResponse snippet: {res.text[:150]}...")
            print("⏳ Waiting 5 seconds before retrying...")
            time.sleep(5)
            
    except Exception as e:
        print(f"⚠️ Network/Timeout exception during webhook upload: {e}")
        print("⏳ Waiting 5 seconds before retrying...")
        time.sleep(5)

if webhook_success:
    # Update History Record
    new_record = {
        "original_filename": video_file,
        "processed_filename": processed_video_file,
        "upload_timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "title_used": title
    }
    history_data.append(new_record)
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    print(f"📒 Added '{video_file}' to history.json")
    
    # Archive files
    shutil.move(raw_video_path, os.path.join(ARCHIVE_DIR, video_file))
    shutil.move(processed_video_path, os.path.join(ARCHIVE_DIR, processed_video_file))
    print(f"📦 Moved both video files to '{ARCHIVE_DIR}/' folder.")
else:
    print("❌ All 3 Webhook upload attempts failed! Please check Make.com scenario status or Cloudflare limits.")
    exit(1)
