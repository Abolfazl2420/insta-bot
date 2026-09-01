import os
import re
import html
import json
import tempfile
import asyncio
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# توکن فعال شما
TOKEN = "8880124550:AAG75YAujlTDOuoZE8qQvyl0mg76IX-w7MA"

# ----------------- وب‌سرور برای زنده ماندن روی پلن رایگان -----------------
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

# ----------------- توابع کمکی -----------------

def clean_url(text: str) -> str:
    """پاکسازی لینک و حذف پارامترهای اضافی مثل ?igsh="""
    match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|share)/[a-zA-Z0-9_\-]+)', text)
    if match:
        return match.group(0).replace("/reels/", "/reel/")
    short_match = re.search(r'(https?://(?:www\.)?instagram\.com/[^\s\?]+)', text)
    return short_match.group(0) if short_match else ""

def save_stream(video_url: str, output_path: str) -> bool:
    """دانلود بافر ویدیو و ذخیره در فایل محلی"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=40, allow_redirects=True)
        if res.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                return True
    except Exception as e:
        print(f"Stream error: {e}")
    return False

# ----------------- موتورهای دانلود ضدبلاک -----------------

def engine_saveig_backend(url: str, output_path: str) -> bool:
    """موتور ۱: استخراج از سرور قدرتمند SaveIG"""
    try:
        api_url = "https://v3.saveig.app/api/ajaxSearch"
        data = {
            "q": url,
            "t": "media",
            "lang": "en"
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        res = requests.post(api_url, data=data, headers=headers, timeout=15)
        if res.status_code == 200:
            resp_data = res.json()
            raw_html = resp_data.get("data", "")
            # استخراج لینک‌های ویدیو با فرمت‌های مختلف
            video_links = re.findall(r'href=["\'](https?://[^"\']+\.mp4[^"\']*)["\']', raw_html)
            if not video_links:
                video_links = re.findall(r'href=["\'](https?://[^"\']*(?:dl\.snapinsta|download)[^"\']*)["\']', raw_html)
            if not video_links:
                video_links = re.findall(r'href=["\'](https?://download[a-zA-Z0-9_\-\./\?=]+)["\']', raw_html)
                
            for v_link in video_links:
                v_link = html.unescape(v_link)
                if save_stream(v_link, output_path):
                    return True
    except Exception as e:
        print(f"SaveIG engine error: {e}")
    return False

def engine_multi_api(url: str, output_path: str) -> bool:
    """موتور ۲: استفاده از سرورهای واسط با پروکسی مسکونی"""
    endpoints = [
        f"https://delirius-apiofc.vercel.app/download/instagram?url={url}",
        f"https://api.siputzx.my.id/api/d/igdl?url={url}",
        f"https://api.dorratz.com/v2/ig-dl?url={url}",
        f"https://api.vkrdown.com/web/insta.php?url={url}"
    ]
    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=12)
            if res.status_code == 200:
                data = res.json()
                video_url = None
                
                # استخراج داینامیک آدرس ویدیو از ساختارهای مختلف JSON
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    item = data["data"][0]
                    video_url = item.get("url") or item.get("download_url") or item.get("video")
                elif "data" in data and isinstance(data["data"], dict):
                    video_url = data["data"].get("url") or data["data"].get("video") or data["data"].get("download_url")
                elif "url" in data:
                    video_url = data.get("url")
                elif "download_url" in data:
                    video_url = data.get("download_url")

                if video_url and save_stream(video_url, output_path):
                    return True
        except Exception as e:
            print(f"API attempt error: {e}")
            continue
    return False

def engine_embed_scraper(url: str, output_path: str) -> bool:
    """موتور ۳: اسکرپر اختصاصی لایه Embed اینستاگرام"""
    try:
        shortcode_match = re.search(r'/(?:p|reel|tv)/([a-zA-Z0-9_\-]+)', url)
        if not shortcode_match:
            return False
        shortcode = shortcode_match.group(1)
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(embed_url, headers=headers, timeout=10)
        if res.status_code == 200:
            urls = re.findall(r'video_url\\":\\"([^"]+)\\"', res.text)
            if not urls:
                urls = re.findall(r'"video_url":\s*"([^"]+)"', res.text)
            if urls:
                direct_url = urls[0].replace(r'\u0026', '&').replace(r'\/', '/')
                return save_stream(direct_url, output_path)
    except Exception as e:
        print(f"Embed scraper error: {e}")
    return False

def download_instagram_video(url: str, output_path: str) -> bool:
    # ۱. اولویت اول: SaveIG
    if engine_saveig_backend(url, output_path):
        return True
    # ۲. اولویت دوم: سرورهای واسط
    if engine_multi_api(url, output_path):
        return True
    # ۳. اولویت سوم: لایه Embed
    if engine_embed_scraper(url, output_path):
        return True
    return False

# ----------------- مدیریت پیام‌های تلگرام -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! لینک ریلز یا پست مورد نظرت رو بفرست تا مستقیم ویدیو رو برات بفرستم."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    url = clean_url(text)
    if not url:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر از اینستاگرام ارسال کنید.")
        return

    status_msg = await update.message.reply_text("⚡ در حال استخراج و دانلود ویدیو...")

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
            await status_msg.edit_text("❌ متأسفانه دریافت این ویدیو با خطا مواجه شد. لطفاً لینک یک پست یا ریلز عمومی دیگر را امتحان کنید.")
    except Exception as e:
        print(f"Error handling message: {e}")
        await status_msg.edit_text("❌ مشکلی در ارسال فایل پیش آمد.")
    finally:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception:
                pass

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

    print("Instagram Downloader is 100% Ready and Active!")
    app.run_polling()

if __name__ == "__main__":
    main()
