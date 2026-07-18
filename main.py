import os
import shutil
import requests
import subprocess
import json
import re
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

# 1. Load Upload History
history_data = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            history_data = json.load(f)
    except Exception as e:
        print(f"⚠️ History file read error: {e}. Starting fresh.")
        history_data = []

# Get list of already uploaded original filenames
uploaded_files = [item["original_filename"] for item in history_data if "original_filename" in item]

# 2. Scan for MP4 video files
videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4") and not f.startswith("processed_")]

if not videos:
    print("⚠️ Koi raw video file nahi mili 'videos/' folder mein! Process stopping.")
    exit(0)

# 3. Find the first video NOT in history
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
# 🧠 Gemini AI - SEO Metadata Generation
# ==========================================
print("🤖 Calling Gemini API for viral SEO metadata...")
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Filename se clean title nikalna taake Gemini ko context mile
    movie_context = os.path.splitext(video_file)[0].replace("_", " ").title()
    
    prompt = f"""
    You are an expert SEO manager for a YouTube Shorts and Facebook Reels channel named "Explain With Ali".
    The channel uploads 1-minute Korean movie explanations and summaries in Hindi/Urdu.
    
    The video filename/topic is: "{movie_context}"
    
    Generate viral metadata in strict JSON format with exactly these fields:
    1. "title": A catchy, clickbaity title for YouTube Shorts (Max 60 characters, include "| Explain With Ali #shorts" at the end).
    2. "description": A short, engaging 3-line description in English/Hindi mix explaining this is a 1-min movie summary by Ali, ending with 5 viral hashtags.
    3. "tags": An array of 15 strong SEO keyword tags (e.g., ["Korean Drama in Hindi", "Movie Explain", ...]).
    
    Return ONLY valid JSON without any markdown formatting or extra text.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json"
        )
    )
    
    # Parse JSON output from Gemini
    ai_data = json.loads(response.text)
    title = ai_data.get("title", f"{movie_context} | Explain With Ali #shorts")
    description = ai_data.get("description", f"{movie_context} - Korean Movie Explained in Hindi/Urdu by Ali.\n\n#ExplainWithAli #Shorts #KoreanMovie")
    tags = ai_data.get("tags", ["Explain With Ali", "Korean Movie in Hindi", "Shorts", "Movie Explanation"])
    print("✅ Gemini AI generated SEO successfully!")

except Exception as e:
    print(f"⚠️ Gemini API failed: {e}. Falling back to default metadata.")
    clean_name = os.path.splitext(video_file)[0].replace("_", " ").title()
    title = f"{clean_name} | Korean Movie Explain | Ali #shorts"
    description = f"{clean_name} - Short Korean Movie Explanation in Urdu/Hindi by Ali.\n\n#ExplainWithAli #KoreanMovieHindi #Shorts"
    tags = ["Explain With Ali", "Korean Movie Hindi", "Movie Explain", "Shorts", "Reels"]

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
# 🚀 Webhook & History Update
# ==========================================
raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/{BRANCH}/{VIDEO_DIR}/{processed_video_file}"

payload = {
    "video_url": raw_url,
    "filename": processed_video_file,
    "title": title,
    "description": description,
    "tags": tags,  # Send tags array to Make.com as well
    "tags_string": ", ".join(tags) # Send comma-separated string just in case
}

if not WEBHOOK_URL:
    print("❌ MAKE_WEBHOOK_URL environment variable missing!")
    exit(1)

print(f"🚀 Sending data to Make.com Webhook...")
res = requests.post(WEBHOOK_URL, json=payload)

if res.status_code == 200:
    print("✅ Webhook successfully triggered!")
    
    # Update History Record
    new_record = {
        "original_filename": video_file,
        "processed_filename": processed_video_file,
        "upload_timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "title_used": title
    }
    history_data.append(new_record)
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=4)
    print(f"📒 Added '{video_file}' to history.json")
    
    # Archive files
    shutil.move(raw_video_path, os.path.join(ARCHIVE_DIR, video_file))
    shutil.move(processed_video_path, os.path.join(ARCHIVE_DIR, processed_video_file))
    print(f"📦 Moved both video files to '{ARCHIVE_DIR}/' folder.")
else:
    print(f"❌ Webhook Failed! Status Code: {res.status_code}\nResponse: {res.text}")
    exit(1)
