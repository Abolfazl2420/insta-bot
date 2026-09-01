import os
import re
import tempfile
import asyncio
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# توکن جدید شما
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

def extract_shortcode(url: str) -> str:
    match = re.search(r'/(?:p|reel|tv|share/[a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)', url)
    if not match:
        match = re.search(r'instagram\.com/(?:reel|p|tv)/([a-zA-Z0-9_\-]+)', url)
    if match:
        return match.group(1)
    return ""

def download_via_embed_bridges(shortcode: str, output_path: str) -> bool:
    """دور زدن تحریم و فایروال اینستاگرام از طریق سرورهای ایمبد"""
    bridges = ["ddinstagram.com", "instagramez.com", "g.ddinstagram.com"]
    headers = {
        "User-Agent": "TelegramBot (like TwitterBot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    for bridge in bridges:
        try:
            target_url = f"https://{bridge}/reel/{shortcode}/"
            res = requests.get(target_url, headers=headers, timeout=12, allow_redirects=True)
            if res.status_code == 200:
                # استخراج لینک مستقیم ویدیو از متا تگ‌ها
                vid_match = re.search(
                    r'<meta\s+(?:property|name)=["\'](?:og:video|og:video:secure_url|twitter:player:stream)["\']\s+content=["\']([^"\']+)["\']',
                    res.text,
                    re.IGNORECASE
                )
                if not vid_match:
                    vid_match = re.search(
                        r'content=["\']([^"\']+)["\']\s+(?:property|name)=["\'](?:og:video|og:video:secure_url|twitter:player:stream)["\']',
                        res.text,
                        re.IGNORECASE
                    )

                if vid_match:
                    video_url = vid_match.group(1).replace("&amp;", "&")
                    if video_url.startswith("http"):
                        v_res = requests.get(video_url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=25)
                        if v_res.status_code == 200:
                            with open(output_path, "wb") as f:
                                for chunk in v_res.iter_content(chunk_size=1024*1024):
                                    if chunk:
                                        f.write(chunk)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                                return True
        except Exception as e:
            print(f"Bridge error ({bridge}): {e}")
            continue

    # تلاش از طریق لینک مستقیم ویدیویی سرورها
    direct_urls = [
        f"https://ddinstagram.com/videos/{shortcode}/1",
        f"https://g.ddinstagram.com/videos/{shortcode}/1"
    ]
    for d_url in direct_urls:
        try:
            v_res = requests.get(d_url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=15, allow_redirects=True)
            if v_res.status_code == 200 and 'video' in v_res.headers.get('Content-Type', ''):
                with open(output_path, "wb") as f:
                    for chunk in v_res.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                    return True
        except Exception as e:
            print(f"Direct stream error: {e}")
            continue

    return False

def download_via_ytdlp(url: str, output_path: str) -> bool:
    """موتور کمکی نهایی با هدرهای شبیه‌ساز مرورگر موبایل"""
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return False

def download_instagram_video(url: str, output_path: str) -> bool:
    shortcode = extract_shortcode(url)
    if shortcode:
        # متد اول: سرورهای واسط ضدبلاک
        if download_via_embed_bridges(shortcode, output_path):
            return True

    # متد دوم: موتور کمکی yt-dlp
    return download_via_ytdlp(url, output_path)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    insta_match = re.search(r'(https?://(?:www\.)?instagram\.com/[^\s]+)', text)
    if not insta_match:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر از ریلز یا پست اینستاگرام ارسال کنید.")
        return

    url = insta_match.group(0).split("?")[0]
    status_msg = await update.message.reply_text("⏳ در حال دریافت و آماده‌سازی ویدیو...")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    try:
        success = await asyncio.to_thread(download_instagram_video, url, temp_filename)
        if success and os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
            await status_msg.edit_text("🚀 در حال آپلود در تلگرام...")
            with open(temp_filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ دانلود شده با موفقیت",
                    supports_streaming=True
                )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ خطا در دانلود ویدیو. ممکن است ریلز حذف شده یا پیج کاملاً خصوصی باشد.")
    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit_text("❌ مشکلی در پردازش ویدیو رخ داد.")
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

    print("Bot is successfully running with Multi-Bridge Engine!")
    app.run_polling()

if __name__ == "__main__":
    main()
