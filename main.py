import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# توکن خود را اینجا بگذار
TOKEN = "8880124550:AAHvbLVGZVA2z8NbIxvNHofjxf5m8IMnTSo"

class HealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthCheck).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    print("Bot is starting...")
    app.run_polling()
