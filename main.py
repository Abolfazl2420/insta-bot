import os
import re
import json
import html
import tempfile
import asyncio
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# توکن فعال شما
TOKEN = "8880124550:AAG75YAujlTDOuoZE8qQvyl0mg76IX-w7MA"

# ----------------- وب‌سرور برای زنده ماندن روی پلن رایگان -----------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ----------------- موتورهای دانلود ضدبلاک اینستاگرام -----------------

def extract_shortcode(url: str) -> str:
    """استخراج کد اختصاصی پست یا ریلز"""
    match = re.search(r'/(?:reel|p|tv|share/[a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)', url)
    if not match:
        match = re.search(r'instagram\.com/(?:reel|p|tv)/([a-zA-Z0-9_\-]+)', url)
    return match.group(1) if match else ""

def save_stream_to_file(stream_url: str, output_path: str, headers: dict = None) -> bool:
    """دانلود بافر ویدیو با سرعت بالا"""
    try:
        req_headers = headers or {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(stream_url, headers=req_headers, stream=True, timeout=30, allow_redirects=True)
        if res.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 15000:
                return True
    except Exception as e:
        print(f"Stream error: {e}")
    return False

def engine_instagram_embed(shortcode: str, output_path: str) -> bool:
    """موتور ۱: استخراج مستقیم از لایه Embed بدون مسدودی آی‌پی"""
    try:
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        res = requests.get(embed_url, headers=headers, timeout=12)
        if res.status_code == 200:
            # جستجوی آدرس مستقیم ویدیو داخل کدهای صفحه
            matches = re.findall(r'video_url\\":\\"([^"]+)\\"', res.text)
            if not matches:
                matches = re.findall(r'"video_url":\s*"([^"]+)"', res.text)
            if matches:
                raw_url = matches[0].replace(r'\u0026', '&').replace(r'\\/', '/').replace(r'\/', '/')
                return save_stream_to_file(raw_url, output_path)
    except Exception as e:
        print(f"Embed engine error: {e}")
    return False

def engine_cobalt_cluster(url: str, output_path: str) -> bool:
    """موتور ۲: کلاستر سرورهای قدرتمند واسط جهانی"""
    instances = [
        "https://api.cobalt.tools",
        "https://cobalt-api.kwiatekm.pl",
        "https://cobalt.canine.tools",
        "https://cobalt.xy2401.com",
        "https://api.wuk.sh"
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    payload = {"url": url, "videoQuality": "720", "downloadMode": "auto"}

    for endpoint in instances:
        try:
            res = requests.post(f"{endpoint}/", json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                video_url = data.get("url")
                if not video_url and "picker" in data and len(data["picker"]) > 0:
                    video_url = data["picker"][0].get("url")
                if video_url:
                    if save_stream_to_file(video_url, output_path):
                        return True
        except Exception:
            continue
    return False

def engine_edge_proxy(shortcode: str, output_path: str) -> bool:
    """موتور ۳: سرورهای پروکسی لبه CDN"""
    proxies = [
        f"https://ddinstagram.com/videos/{shortcode}/1",
        f"https://g.ddinstagram.com/videos/{shortcode}/1",
        f"https://instagramez.com/videos/{shortcode}/1"
    ]
    for p_url in proxies:
        if save_stream_to_file(p_url, output_path):
            return True
    return False

def engine_ytdlp_fallback(url: str, output_path: str) -> bool:
    """موتور ۴: yt-dlp بهینه‌شده با پروفایل آیفون"""
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept': '*/*',
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return os.path.exists(output_path) and os.path.getsize(output_path) > 15000
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return False

def download_instagram_video(url: str, output_path: str) -> bool:
    """اجرای ترتیبی موتورها تا دانلود قطعی فایل"""
    shortcode = extract_shortcode(url)

    if shortcode:
        # تست موتور ۱ (Embed)
        if engine_instagram_embed(shortcode, output_path):
            return True
        # تست موتور ۲ (Cobalt)
        if engine_cobalt_cluster(url, output_path):
            return True
        # تست موتور ۳ (Edge CDN)
        if engine_edge_proxy(shortcode, output_path):
            return True

    # تست موتور ۴ (yt-dlp fallback)
    return engine_ytdlp_fallback(url, output_path)

# ----------------- هندلرهای تلگرام -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! لینک هر ریلز یا پستی از اینستاگرام را بفرستید تا فوراً ویدیو را تحویل دهم."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    insta_match = re.search(r'(https?://(?:www\.)?instagram\.com/[^\s]+)', text)
    if not insta_match:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر از اینستاگرام ارسال کنید.")
        return

    url = insta_match.group(0).split("?")[0]
    status_msg = await update.message.reply_text("⚡ در حال دریافت ویدیو با نهایت سرعت...")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    try:
        success = await asyncio.to_thread(download_instagram_video, url, temp_filename)
        if success and os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 10000:
            await status_msg.edit_text("🚀 در حال آپلود ویدیو...")
            with open(temp_filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ دانلود شده با موفقیت",
                    supports_streaming=True
                )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ خطایی رخ داد. لطفاً مطمئن شوید پیج خصوصی نباشد یا لینک دیگری بفرستید.")
    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit_text("❌ مشکلی در ارسال ویدیو پیش آمد.")
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

    print("Ultra-Fast Multi-Engine Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
