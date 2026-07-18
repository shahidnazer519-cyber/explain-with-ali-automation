import os
import requests
import sys
import warnings
import time
import json

# Pillow وارننگز ہٹانے کے لیے
warnings.filterwarnings("ignore", category=DeprecationWarning)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from moviepy.editor import VideoFileClip
from google import genai
from google.genai import types

# کانفیگریشن
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL") or os.getenv("BUFFER_WEBHOOK_URL")
VIDEOS_DIR = "videos"
HISTORY_FILE = "history.txt"

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def ensure_history_file():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("")

def get_history():
    ensure_history_file()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def add_to_history(filename):
    ensure_history_file()
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

def process_video_high_quality(input_path, output_path):
    """
    ویڈیو کو بہترین کوالٹی میں پروسیس کرنا اور فیس بک کا فارمیٹ ایرر ٹھیک کرنا
    """
    print("🎥 Processing High-Quality Video for Facebook & YouTube...")
    clip = VideoFileClip(input_path)
    
    # -pix_fmt yuv420p: فیس بک کے لیے ضروری فارمیٹ
    # -crf 23: زبردست ویڈیو کوالٹی کے لیے متوازن سیٹنگ
    clip.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac",
        audio_bitrate="128k",
        preset="fast",   
        ffmpeg_params=[
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
            "-crf", "23", 
            "-pix_fmt", "yuv420p" 
        ]
    )
    clip.close()

def upload_to_cloud(filepath):
    """Make.com کی 5MB لمٹ سے بچنے کے لیے ویڈیو کو کلاؤڈ پر بھیج کر ڈائریکٹ لنک حاصل کرنا"""
    print("☁️ Uploading HD Video to Cloud (Catbox) to bypass Webhook limits...")
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                'https://catbox.moe/user/api.php',
                data={'reqtype': 'fileupload'},
                files={'fileToUpload': f},
                timeout=300
            )
        if response.status_code == 200:
            video_link = response.text.strip()
            print(f"✅ Cloud Upload Success! Link: {video_link}")
            return video_link
        else:
            print("⚠️ Cloud upload failed.")
            return None
    except Exception as e:
        print(f"⚠️ Upload exception: {e}")
        return None

def generate_seo(topic_name):
    default_title = f"{topic_name}: Amazing Facts! | Explain With Ali #shorts"
    default_desc = f"🎬 Amazing facts and summary about {topic_name}.\n\n👉 Subscribe for more fact videos!\n\n#Shorts #Facts #Viral #ExplainWithAli"
    
    if not client:
        return {"title": default_title, "description": default_desc}
        
    prompt = f"""
    You are an expert YouTube Shorts SEO manager for a channel named "Explain With Ali".
    Create viral metadata for a 1-minute facts video about: '{topic_name}'.
    Remember: We ONLY upload fact videos, absolutely no nature content.
    
    Return STRICT JSON format with exactly these two keys:
    "title": A catchy viral title (Max 60 chars, MUST end with " | Explain With Ali #shorts").
    "description": 3 lines of engaging facts summary, ending with 5 strong hashtags.
    
    Return ONLY valid JSON without markdown formatting or extra text.
    """
    
    models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    for model in models:
        try:
            print(f"🤖 Calling Gemini AI ({model})...")
            res = client.models.generate_content(
                model=model, 
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, response_mime_type="application/json")
            )
            data = json.loads(res.text.strip())
            if "title" in data:
                print("✅ AI Success!")
                return data
        except:
            time.sleep(1)
            
    return {"title": default_title, "description": default_desc}

def main():
    ensure_history_file()
    if not os.path.exists(VIDEOS_DIR):
        os.makedirs(VIDEOS_DIR)
        return

    if not MAKE_WEBHOOK_URL:
        print("❌ Webhook URL missing!")
        return

    history = get_history()
    files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov')) and not f.startswith("processed_")]
    target_video = None
    
    for f in sorted(files):
        if f not in history:
            target_video = f
            break
            
    if not target_video:
        print("✅ No new videos to upload.")
        return

    input_path = os.path.join(VIDEOS_DIR, target_video)
    output_path = os.path.join(VIDEOS_DIR, "processed_" + target_video)
    base_name = os.path.splitext(target_video)[0]
    clean_topic = base_name.split("__")[0].strip() if "__" in base_name else base_name.strip()
        
    try:
        process_video_high_quality(input_path, output_path)
    except Exception as e:
        print(f"❌ Video Processing Failed: {e}")
        return
    
    seo_data = generate_seo(clean_topic)
    
    # 1. کلاؤڈ پر اپلوڈ کریں اور لنک لیں
    video_url = upload_to_cloud(output_path)
    if not video_url:
        print("❌ Could not get video URL. Stopping.")
        return

    # 2. صرف ڈیٹا اور لنک Make.com کو بھیجیں (بھاری فائل نہیں)
    print("🚀 Sending Data & Link to Make.com Webhook...")
    data_dict = {
        "video_name": clean_topic,
        "title": seo_data["title"],
        "description": seo_data["description"],
        "topic": clean_topic,
        "video_url": video_url,
        "filename": target_video
    }
    
    try:
        res = requests.post(MAKE_WEBHOOK_URL, json=data_dict, timeout=30)
        if res.status_code in [200, 201]:
            print("✅ Successfully triggered Make.com!")
            add_to_history(target_video)
            os.remove(input_path)
            os.remove(output_path)
            print("🗑️ Cleaned up files.")
        else:
            print(f"⚠️ Webhook Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"⚠️ Request exception: {e}")

if __name__ == "__main__":
    main()
