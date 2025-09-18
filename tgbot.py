import os
import tempfile
import hashlib
import boto3
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIG ---
TELEGRAM_TOKEN = "8190406880:AAGF98A-DZKMj93tgOnKX1BQyQVPrHKuMYs"  # BotFather-dan olingan token
AWS_REGION = "eu-west-1"
S3_BUCKET = "your-bucket-name"
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

# Allowed domains (faqat ruxsatli manbalar)
ALLOWED_DOMAINS = ("kali.org", "cdimage.kali.org", "http.kali.org")

# --- INIT AWS CLIENT ---
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

# --- HELPERS ---
def is_allowed_url(url: str) -> bool:
    try:
        host = requests.utils.urlparse(url).hostname
        if not host:
            return False
        return any(host == dom or host.endswith("." + dom) for dom in ALLOWED_DOMAINS)
    except Exception:
        return False

def stream_to_s3(url: str, s3_key: str) -> str:
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        sha256 = hashlib.sha256()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    tmp.write(chunk)
                    sha256.update(chunk)
            tmp_path = tmp.name

    s3.upload_file(tmp_path, S3_BUCKET, s3_key)
    os.unlink(tmp_path)
    return sha256.hexdigest()

def make_presigned_url(key: str, expires=3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Kali live URL yuboring (masalan https://cdimage.kali.org/...).\n"
        "Men rasmiy manbadan ISO ni yuklab olib, sizga 1 soatlik yuklab olish linkini yuboraman."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url = text.split()[0]
    chat_id = update.effective_chat.id

    if not is_allowed_url(url):
        await update.message.reply_text(
            "❌ Manzil ruxsat etilmagan.\n"
            "Faqat rasmiy *kali.org* manbalarini yuboring."
        )
        return

    msg = await update.message.reply_text(
        "⏳ Yuklanmoqda… serverga yuborilmoqda, biroz kuting (fayl katta bo‘lishi mumkin)."
    )

    filename = url.split("/")[-1] or "kali.iso"
    s3_key = f"kali_iso/{chat_id}/{filename}"

    try:
        sha256 = stream_to_s3(url, s3_key)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Yuklashda xatolik: {e}")
        return

    presigned = make_presigned_url(s3_key, expires=3600)
    reply = (
        f"✅ Yuklandi!\n\n"
        f"ISO fayl: `{filename}`\n"
        f"SHA256: `{sha256}`\n\n"
        f"Yuklab olish uchun link (1 soat amal qiladi):\n{presigned}\n\n"
        "⚠️ Iltimos SHA256 va GPG tekshiruvini bajaring.\n"
        "Rasmiy sahifa: https://www.kali.org/get-kali/"
    )

    await update.message.reply_text(reply, disable_web_page_preview=True)

# --- MAIN ---
def main():
    print("🚀 Bot ishga tushmoqda...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Shu yerda asyncio.run() ishlatmasdan faqat run_polling()
    app.run_polling()

if __name__ == "__main__":
    main()

