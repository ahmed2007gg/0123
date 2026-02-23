import json
import logging
import asyncio
import os
from datetime import datetime
from typing import Set

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

CALENDARS = [
    {
        "url": "https://appointment.mosaicvisa.com/calendar/7",
        "city": "وهران",
        "state_file": "state7.json"
    },
    {
        "url": "https://appointment.mosaicvisa.com/calendar/9",
        "city": "الجزائر",
        "state_file": "state9.json"
    }
]

CHECK_INTERVAL = 600  # 10 دقائق
SUB_FILE = "subs.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_subs() -> Set[int]:
    try:
        with open(SUB_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_subs(data: Set[int]):
    with open(SUB_FILE, "w") as f:
        json.dump(list(data), f)

def fetch(url: str) -> Set[str]:
    try:
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("tr")
        dates = set()

        for r in rows:
            text = r.get_text(" ", strip=True)
            if "Reserved 0" not in text and any(c.isdigit() for c in text):
                dates.add(text)

        return dates
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return set()

def load_state(file: str) -> Set[str]:
    try:
        with open(file, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_state(file: str, data: Set[str]):
    with open(file, "w") as f:
        json.dump(list(data), f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = load_subs()
    subs.add(update.effective_chat.id)
    save_subs(subs)
    await update.message.reply_text("تم الاشتراك ✅")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = load_subs()
    subs.discard(update.effective_chat.id)
    save_subs(subs)
    await update.message.reply_text("تم إلغاء الاشتراك ❌")

async def check_loop(app: Application):
    while True:
        subs = load_subs()
        if not subs:
            logger.info("لا يوجد مشتركين حالياً، تخطي الإشعارات.")
        else:
            for cal in CALENDARS:
                current = fetch(cal["url"])
                old = load_state(cal["state_file"])
                new = current - old

                if new:
                    msg = f"مواعيد جديدة في {cal['city']}:\n" + "\n".join(sorted(new))
                    for chat_id in subs:
                        try:
                            await app.bot.send_message(chat_id, msg)
                        except Exception as e:
                            logger.error(f"فشل إرسال الرسالة إلى {chat_id}: {e}")
                    save_state(cal["state_file"], current)
                else:
                    logger.info(f"لا توجد مواعيد جديدة في {cal['city']}.")

        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    if not BOT_TOKEN:
        logger.error("الرجاء تعيين متغير البيئة BOT_TOKEN قبل التشغيل.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))

    # بدء المهمة الدورية
    app.create_task(check_loop(app))

    logger.info("البوت يعمل الآن...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
