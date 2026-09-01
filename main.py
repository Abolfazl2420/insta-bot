import os
import re
import tempfile
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "8880124550:AAG75YAujlTDOuoZE8qQvyl0mg76IX-w7MA"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! لینک ریلز یا پست اینستاگرام رو بفرست تا ویدیو رو برات دانلود کنم."
    )

def download_file_stream(direct_url: str, output_path: str) -> bool:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.instagram.com/'
        }
        with requests.get(direct_url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"Direct stream error: {e}")
        return False

def extract_and_download(url: str, output_path: str) -> bool:
    # روش اول: استفاده از سرورهای دورزننده DDInstagram
    try:
        clean_url = re.sub(r'https?://(?:www\.)?instagram\.com', 'https://www.ddinstagram.com', url)
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
        res = requests.get(clean_url, headers=headers, timeout=12)
        
        match = re.search(r'<meta\s+property=["\']og:video(?::secure_url)?["\']\s+content=["\']([^"\']+)["\']', res.text)
        if not match:
            match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', res.text)
            
        if match:
            direct_video_url = match.group(1).replace("&amp;", "&")
            if download_file_stream(direct_video_url, output_path):
                return True
    except Exception as e:
        print(f"Engine 1 error: {e}")

    # روش دوم: استفاده از API رایگان Cobalt
    try:
        res = requests.post(
            "https://api.cobalt.tools/",
            json={"url": url, "videoQuality": "720"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=12
        )
        if res.status_code == 200:
            data = res.json()
            direct_url = data.get("url")
            if direct_url and download_file_stream(direct_url, output_path):
                return True
    except Exception as e:
        print(f"Engine 2 error: {e}")

    # روش سوم: موتور yt-dlp با هدر اختصاصی موبایل
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"Engine 3 error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    insta_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[a-zA-Z0-9_\-]+)', text)
    if not insta_match:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر از ریلز یا پست اینستاگرام ارسال کنید.")
        return

    url = insta_match.group(0)
    status_msg = await update.message.reply_text("⏳ در حال دریافت و آماده‌سازی ویدیو...")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    try:
        success = await asyncio.to_thread(extract_and_download, url, temp_filename)
        
        if success and os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
            await status_msg.edit_text("🚀 در حال ارسال ویدیو در تلگرام...")
            with open(temp_filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ دانلود شده با موفقیت",
                    supports_streaming=True
                )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ امکان دانلود این ویدیو وجود ندارد (ممکن است ریلز حذف شده یا محدودیت سنی داشته باشد).")
    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit_text("❌ مشکلی در پردازش ویدیو پیش آمد.")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    threading.Thread(target=start_health_check_server, daemon=True).start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is successfully running with Multi-Engine!")
    app.run_polling()

if __name__ == "__main__":
    main()
