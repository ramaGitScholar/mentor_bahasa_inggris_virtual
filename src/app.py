import src.core.env as env

import os
import random

from zoneinfo import ZoneInfo # WIB - Asia/Jakarta

from telegram import Update
from google.genai.errors import ClientError
from telegram.ext import (
    ContextTypes,
    Application,
    CommandHandler, # /start /report
    MessageHandler, # text atau suara (voice note)
    Defaults,
    filters
)

from telegram.constants import ParseMode # MarkdownV2
from loguru import logger
from datetime import time, date, timedelta # generate - per 1 minggu / 7 hari

from src.agents.lead import LeadAgent
from src.repository.chat_repository import ChatRepository
from src.core.format import to_telegram_markdown
from src.core.artifacts import Artifact

timezone = ZoneInfo("Asia/Jakarta")

chat_repository = ChatRepository()
lead_agent = LeadAgent()

# python-telegram-bot config
bot_config = Defaults(
    parse_mode=ParseMode.MARKDOWN_V2,
    tzinfo=timezone
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    chat_id = update.effective_chat.id
    
    chat_repository.save_user(
        user_id=user_id,
        username=username,
        chat_id=chat_id
    )
    
    safe_text = to_telegram_markdown(
        f"Halo!, Selamat datang {username} di Mentor Bahasa Inggris Virtual.\n"
        "Aku siap bantu kamu untuk belajar bahasa inggris! \n"
        "Kamu bisa langsung coba ketik pesan seperti ini: \n"
        "- *buatkan soal reading*\n"
        "- *periksa: I goes to school*\n"
        "- *kasih tips belajar*\n"
        "atau ngobrol bebas untuk melatih *speaking atau writing* kamu!\n"
        "- Ketik /start untuk mendaftarkan akun dan mulai belajar\n"
        "- Ketik /report untuk membuat laporan belajar\n",
    )
    
    await update.message.reply_text(safe_text)

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(to_telegram_markdown("Laporan sedang dibuat mohon tunggu.."))
    
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    
    report_file_path = lead_agent.handle_report(
        user_id=user_id,
        username=username,
        start_date=start_date,
        end_date=end_date
    )
    
    with open(report_file_path, "rb") as report_pdf:
        await update.message.reply_document(
            document=report_pdf,
            caption=to_telegram_markdown(f"laporan belajar bahasa inggris dari tanggal {start_date.isoformat()} - {end_date.isoformat()}")
            )

async def _send_artifact(update: Update, artifact: Artifact):
    artifact_path = artifact.get("path")
    kind = artifact.get("kind")
    caption = artifact.get("caption")
    
    safe_caption_text = to_telegram_markdown(caption)
    
    if not os.path.exists(artifact_path):
        logger.warning(f"Artifact tidak ditemukan")
        
    with open(artifact_path, "rb") as artifact_file:
        if kind == "audio":
            await update.message.reply_audio(audio=artifact_file, caption=safe_caption_text)
        else:
            await update.message.reply_document(
                document=artifact_file,
                caption=safe_caption_text
            )
    
    os.remove(artifact_path)     
    
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = await update.message.reply_text(to_telegram_markdown("mentor sedang menyiapkan jawaban..."))
    
    user_id = update.message.from_user.id
    user_message = update.message.text

    try:
        response = lead_agent.handle_send_message(user_id=user_id, message_text=user_message)
    except ClientError as error:
        if getattr(error, "code", None) == 429:
            await reply_text.edit_text(to_telegram_markdown(
                "Mentor sedang sibuk karena kuota permintaan ke layanan AI sudah penuh. "
                "Coba lagi beberapa saat lagi ya."
            ))
            return
        raise

    safe_text = to_telegram_markdown(response["text"])

    await reply_text.edit_text(safe_text)
    
    if response["artifacts"]:
        artifact = Artifact(response["artifacts"][0])
        await _send_artifact(update, artifact)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = await update.message.reply_text(to_telegram_markdown("suara sedang diproses, mohon tunggu.."))
    
    user_id = update.message.from_user.id
    
    env.TEMP.mkdir(parents=True, exist_ok=True)
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    voice_file_path = env.TEMP / f"{update.message.voice.file_id}.ogg"
    
    await voice_file.download_to_drive(str(voice_file_path))
    
    evaluation_speaking_result = lead_agent.handle_send_voice(
        user_id=user_id,
        voice_file_path=voice_file_path
    )
    
    safe_text = to_telegram_markdown(evaluation_speaking_result)
    
    await reply_text.edit_text(safe_text)
    
    os.remove(str(voice_file_path))

async def task_reminder(context: ContextTypes.DEFAULT_TYPE):
    users = chat_repository.get_users()
    skill_types = ["reading", "writing", "listening", "speaking"]
    
    for user in users.data:
        user_id = user["user_id"]
        message = f"Pagi! ☀️ Yuk, luangkan 5 menit untuk latihan {random.choice(skill_types)} hari ini."
        chat_repository.save_message(
            user_id = user_id,
            role="model",
            message_text = message
        )
        safe_text = to_telegram_markdown(message)
        await context.bot.send_message(chat_id=user_id, text=safe_text)
    
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

    if not isinstance(update, Update) or not update.effective_message:
        return

    error = context.error

    if isinstance(error, ClientError) and getattr(error, "code", None) == 429:
        user_message = (
            "Mentor sedang sibuk karena kuota permintaan ke layanan AI sudah penuh. "
            "Coba lagi beberapa saat lagi ya."
        )
    else:
        user_message = "Maaf, terjadi kesalahan di sisi mentor. Coba kirim ulang pesanmu ya."

    try:
        await update.effective_message.reply_text(to_telegram_markdown(user_message))
    except Exception as send_error:  # jangan sampai error handler ikut crash
        logger.error(f"Gagal mengirim pesan error ke user: {send_error}")
    
def run():
    app = Application.builder().token(env.TELEGRAM_BOT_TOKEN).defaults(bot_config).build()
    
    # Register route handler
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("report", report_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND , handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # reminder
    target_time = time(hour=10, minute=3, second=0, tzinfo=timezone)
    app.job_queue.run_daily(
        callback=task_reminder,
        time=target_time,
        name="task_reminder"
    )
    
    app.add_error_handler(error_handler)
    
    print("Mentor Bahasa Inggris Virtual berhasil dijalankan..")
    app.run_polling(allowed_updates=Update.ALL_TYPES, timeout=30)