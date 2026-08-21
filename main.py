import os
import re
import tempfile
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "8880124550:AAHvbLVGZVA2z8NbIxvNHofjxf5m8IMnTSo"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! لینک ریلز یا پست اینستاگرام رو بفرست تا ویدیو رو برات دانلود کنم."
    )

def download_instagram_video(url: str, output_path: str) -> bool:
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"Download Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    insta_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[a-zA-Z0-9_\-]+)', text)
    if not insta_match:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر از اینستاگرام ارسال کنید.")
        return

    url = insta_match.group(0)
    status_msg = await update.message.reply_text("⏳ در حال دریافت ویدیو...")

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
            await status_msg.edit_text("❌ خطا در دانلود. ممکن است پیج خصوصی (Private) باشد.")
    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit_text("❌ مشکلی در پردازش ویدیو رخ داد.")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    threading.Thread(target=start_health_check_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is successfully running!")
    app.run_polling()

if __name__ == "__main__":
    main()
