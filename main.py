import os
import re
import json
import tempfile
import asyncio
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# توکن فعال ربات شما
TOKEN = "8880124550:AAG75YAujlTDOuoZE8qQvyl0mg76IX-w7MA"

# ----------------- وب‌سرور برای زنده ماندن روی پلن رایگان رندر -----------------
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

# ----------------- موتورهای دانلود هوشمند -----------------

def clean_instagram_url(text: str) -> str:
    match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|share)/[a-zA-Z0-9_\-]+)', text)
    if match:
        return match.group(0).replace("/reels/", "/reel/")
    short_match = re.search(r'(https?://(?:www\.)?instagram\.com/[^\s\?]+)', text)
    if short_match:
        return short_match.group(0)
    return ""

def extract_shortcode(url: str) -> str:
    match = re.search(r'/(?:p|reel|tv|share)/([a-zA-Z0-9_\-]+)', url)
    return match.group(1) if match else ""

def download_file(video_url: str, output_path: str) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        if res.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"Error downloading stream: {e}")
    return False

def method_instagram_public_api(shortcode: str, output_path: str) -> bool:
    """استفاده از GraphQL و شناسه رسمی وب اینستاگرام"""
    try:
        api_url = f"https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-IG-App-ID": "936619743392459",
            "Accept": "*/*"
        }
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            shortcode_media = data.get("data", {}).get("shortcode_media", {})
            video_url = shortcode_media.get("video_url")
            if video_url:
                return download_file(video_url, output_path)
    except Exception as e:
        print(f"Method 1 error: {e}")
    return False

def method_external_gateway(url: str, output_path: str) -> bool:
    """استفاده از درگاه واسط پرسرعت"""
    gateways = [
        f"https://api.vkrdown.com/web/insta.php?url={url}",
        f"https://insta-downloader-api.vercel.app/api/video?url={url}"
    ]
    for gw in gateways:
        try:
            res = requests.get(gw, timeout=12)
            if res.status_code == 200:
                data = res.json()
                video_url = data.get("video_url") or data.get("url") or data.get("download_url")
                if not video_url and "data" in data:
                    video_url = data["data"].get("video_url") or data["data"].get("url")
                if video_url and download_file(video_url, output_path):
                    return True
        except Exception:
            continue
    return False

def method_ddinstagram_direct(shortcode: str, output_path: str) -> bool:
    """استخراج از CDNهای اختصاصی"""
    stream_urls = [
        f"https://ddinstagram.com/videos/{shortcode}/1",
        f"https://g.ddinstagram.com/videos/{shortcode}/1"
    ]
    for surl in stream_urls:
        if download_file(surl, output_path):
            return True
    return False

def download_instagram_video(url: str, output_path: str) -> bool:
    shortcode = extract_shortcode(url)
    
    # اجرای متوالی موتورها
    if shortcode and method_instagram_public_api(shortcode, output_path):
        return True
        
    if method_external_gateway(url, output_path):
        return True
        
    if shortcode and method_ddinstagram_direct(shortcode, output_path):
        return True
        
    return False

# ----------------- هندلرهای تلگرام -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! لینک ریلز یا پست اینستاگرام رو بفرست تا ویدیو رو سریع برات بفرستم."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    url = clean_instagram_url(text)
    if not url:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر اینستاگرام ارسال کنید.")
        return

    status_msg = await update.message.reply_text("⚡ در حال پردازش و استخراج ویدیو...")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    try:
        success = await asyncio.to_thread(download_instagram_video, url, temp_filename)
        if success and os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 5000:
            await status_msg.edit_text("🚀 در حال ارسال ویدیو در تلگرام...")
            with open(temp_filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ دانلود شده با موفقیت",
                    supports_streaming=True
                )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ دانلود ناموفق بود. مطمئن شوید پست عمومی (Public) است یا لینک دیگری بفرستید.")
    except Exception as e:
        print(f"Execution Error: {e}")
        await status_msg.edit_text("❌ خطایی در ارسال پیش آمد.")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    threading.Thread(target=start_health_check_server, daemon=True).start()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Instagram Downloader Bot is running smoothly!")
    app.run_polling()

if __name__ == "__main__":
    main()
