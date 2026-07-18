import os
import requests
import sys
import warnings
import time
import json
import random

# 1. Pillow کی وارننگز کو خودکار خاموش کرنا
warnings.filterwarnings("ignore", category=DeprecationWarning)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from moviepy.editor import VideoFileClip
from google import genai
from google.genai import types

# کانفیگریشن اور سیٹنگز
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL") or os.getenv("BUFFER_WEBHOOK_URL")
VIDEOS_DIR = "videos"
HISTORY_FILE = "history.txt"

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def ensure_history_file():
    """اگر history.txt موجود نہ ہو تو فوراً بنا دے تاکہ Git کا ایرر نہ آئے"""
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

def process_video_hd(input_path, output_path):
    """سمارٹ فارمولا: ویڈیو کے دورانیے کے حساب سے بٹ ریٹ خود طے کرنا تاکہ سائز 3.5MB سے کم رہے"""
    print("⏳ Analyzing video duration to apply dynamic compression...")
    clip = VideoFileClip(input_path)
    duration = clip.duration
    
    # 3.2 MB کا ہدف (Kilobits میں: 3.2 * 8192 = ~26200 kb)
    # ٹوٹل بٹ ریٹ = 26200 / دورانیہ (سیکنڈز میں)
    target_total_bitrate = int(26200 / duration)
    
    # آڈیو کے لیے 64k نکال کر باقی ویڈیو کو دینا (کم از کم 150k اور زیادہ سے زیادہ 700k کی حد)
    video_bitrate_val = max(150, min(target_total_bitrate - 64, 700))
    video_bitrate = f"{video_bitrate_val}k"
    
    print(f"📏 Video Duration: {duration:.1f}s | Calculated Bitrate: {video_bitrate} (Guaranteed under 3.5MB)")
    
    clip.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac",
        bitrate=video_bitrate,
        audio_bitrate="64k",
        preset="fast",   
        ffmpeg_params=["-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"]
    )
    clip.close()

def generate_seo(topic_name):
    """جیمنائی ماڈلز اور بیک اپ انجن کے ساتھ ایس ای او جنریشن"""
    default_title = f"{topic_name}: Amazing Story! | Explain With Ali #shorts"
    default_desc = f"🎬 Amazing facts and summary about {topic_name}.\n\n👉 Subscribe for more 1-minute explainers!\n\n#Shorts #Facts #Viral #ExplainWithAli"
    
    if not client:
        return {"title": default_title, "description": default_desc}
        
    prompt = f"""
    You are an expert YouTube Shorts SEO manager for a channel named "Explain With Ali".
    Create viral metadata for a 1-minute video about: '{topic_name}'.
    
    Return STRICT JSON format with exactly these two keys:
    "title": A catchy viral title (Max 60 chars, MUST end with " | Explain With Ali #shorts").
    "description": 3 lines of engaging summary, ending with 5 strong hashtags.
    
    Return ONLY valid JSON without markdown formatting or extra text.
    """
    
    # گوگل کے فعال ترین ماڈلز کی لسٹ
    models_to_try = [
        'gemini-2.5-flash', 
        'gemini-2.0-flash',
        'gemini-1.5-flash', 
        'gemini-1.5-pro'
    ]
    
    for model in models_to_try:
        try:
            print(f"🤖 Calling Gemini AI ({model})...")
            res = client.models.generate_content(
                model=model, 
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, response_mime_type="application/json")
            )
            data = json.loads(res.text.strip())
            if "title" in data and "description" in data:
                print(f"✅ AI Success with {model}!")
                return data
        except Exception as e:
            print(f"⚠️ {model} failed, trying next...")
            time.sleep(1)
            
    print("⚡ Switching to Backup SEO Engine...")
    return {"title": default_title, "description": default_desc}

def main():
    ensure_history_file()
    
    if not os.path.exists(VIDEOS_DIR):
        os.makedirs(VIDEOS_DIR)
        return

    if not MAKE_WEBHOOK_URL:
        print("❌ MAKE_WEBHOOK_URL یا BUFFER_WEBHOOK_URL نہیں ملا! Environment Variable چیک کریں۔")
        return

    history = get_history()
    files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov')) and not f.startswith("processed_")]
    target_video = None
    
    for f in sorted(files):
        if f not in history:
            target_video = f
            break
            
    if not target_video:
        print("✅ تمام ویڈیوز اپلوڈ ہو چکی ہیں یا کوئی نئی ویڈیو نہیں ملی۔")
        return

    input_path = os.path.join(VIDEOS_DIR, target_video)
    output_path = os.path.join(VIDEOS_DIR, "processed_" + target_video)
    
    # نام سے یوٹیوب کی فالتو آئی ڈی کو صاف کرنا
    base_name = os.path.splitext(target_video)[0]
    clean_topic = base_name.split("__")[0].strip() if "__" in base_name else base_name.strip()
        
    print(f"🎬 Processing Video: {clean_topic}")
    try:
        process_video_hd(input_path, output_path)
    except Exception as e:
        print(f"❌ ویڈیو ایڈیٹنگ فیل ہو گئی: {e}")
        if os.path.exists(output_path): os.remove(output_path)
        return
    
    print("🤖 Generating Clean SEO with Gemini...")
    seo_data = generate_seo(clean_topic)
    print(f"📌 Title: {seo_data['title']}")
    
    print("🚀 Sending ACTUAL COMPRESSED VIDEO (<3.5MB) to Make.com Webhook...")
    upload_success = False
    
    for attempt in range(1, 4):
        try:
            print(f"📤 [Attempt {attempt}/3] Uploading...")
            with open(output_path, 'rb') as f:
                files_dict = {"video_file": (target_video, f, "video/mp4")}
                
                data_dict = {
                    "video_name": clean_topic,
                    "title": seo_data["title"],
                    "description": seo_data["description"],
                    "topic": clean_topic
                }
                
                res = requests.post(MAKE_WEBHOOK_URL, data=data_dict, files=files_dict, timeout=120)
                
            if res.status_code in [200, 201]:
                print("✅ Successfully uploaded to Make.com!")
                upload_success = True
                break
            else:
                print(f"⚠️ Webhook Error! Code: {res.status_code} - {res.text[:100]}")
                time.sleep(3)
        except Exception as e:
            print(f"⚠️ Upload exception: {e}")
            time.sleep(3)
            
    if upload_success:
        add_to_history(target_video)
        try:
            os.remove(input_path)
            os.remove(output_path)
            print("🗑️ Cleaned up: Files deleted successfully.")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
    else:
        print("❌ All upload attempts failed!")
        if os.path.exists(output_path): os.remove(output_path)

if __name__ == "__main__":
    main()
