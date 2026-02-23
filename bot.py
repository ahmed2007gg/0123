"""
Telegram Bot for Mosaic Visa Appointment Notifier (Oran & Algiers)
"""

import json
import logging
import asyncio
import os
from datetime import datetime
from typing import Dict, Set

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ======================== CONFIGURATION ========================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # ضع التوكن كمتغير بيئة

CALENDARS = [
    {
        "url": "https://appointment.mosaicvisa.com/calendar/7",
        "city": "وهران (Oran)",
        "state_file": "last_state_7.json"
    },
    {
        "url": "https://appointment.mosaicvisa.com/calendar/9",
        "city": "الجزائر (Algiers)",
        "state_file": "last_state_9.json"
    }
]

CHECK_INTERVAL_SECONDS = 600
SUBSCRIBERS_FILE = "subscribers.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================== SUBSCRIBERS ========================

def load_subscribers() -> Set[int]:
    try:
        with open(SUBSCRIBERS_FILE, "r") as f:
            return set(json.load(f).get("chat_ids", []))
    except:
        return set()

def save_subscribers(chat_ids: Set[int]):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump({"chat_ids": list(chat_ids)}, f)

# ======================== FETCH ========================

def fetch_appointments(url: str) -> Set[str]:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        available = set()

        rows = soup.find_all("tr")

        for row in rows:
            text = row.get_text(" ", strip=True)

            if "Reserved 0" not in text and any(char.isdigit() for char in text):
                available.add(text)

        return available

    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return set()

# ======================== STATE ========================

def load_state(path: str) -> Set[str]:
    try:
        with open(path, "r") as f:
            return set(json.load(f).get("dates", []))
    except:
        return set()

def save_state(path: str, dates: Set[str]):
    with open(path, "w") as f:
        json.dump({
            "dates": list(dates),
            "updated": datetime.now().isoformat()
        }, f)

# ======================== COMMANDS ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = load_subscribers()

    if chat_id not in subs:
        subs.add(chat_id)
        save_subscribers(subs)
        await update.message.reply_text("✅ تم الاشتراك في الإشعارات.")
    else:
        await update.message.reply_text("أنت مشترك بالفعل.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = load_subscribers()

    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
        await update.message.reply_text("❌ تم إلغاء الاشتراك.")
    else:
        await update.message.reply_text("لم تكن مشتركاً.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 البوت يعمل ويراقب المواعيد.")

# ======================== CHECKER ========================

async def check_loop(app: Application):
    while True:
        logger.info("Checking appointments...")
        subs = load_subscribers()

        if subs:
            for cal in CALENDARS:
                current = fetch_appointments(cal["url"])
                old = load_state(cal["state_file"])

                new_dates = current - old

                if new_dates:
                    msg = (
                        f"📅 مواعيد جديدة في {cal['city']}\n"
                        f"{', '.join(sorted(new_dates))}\n"
                        f"{cal['url']}"
                    )

                    for chat_id in subs:
                        await app.bot.send_message(chat_id, msg)

                    save_state(cal["state_file"], current)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# ======================== MAIN ========================

def main():
    if not BOT_TOKEN:
        print("ضع BOT_TOKEN كمتغير بيئة")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    app.job_queue.run_once(lambda ctx: asyncio.create_task(check_loop(app)), 1)

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
