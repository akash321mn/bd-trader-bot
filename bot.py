from __future__ import annotations
import asyncio
from datetime import date
from typing import Final

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

from .config import BOT_TOKEN, OWNER_CONTACT, ADMIN_IDS
from .validators import is_valid_pair, is_otc_pair, to_deriv_symbol, is_supported_tf, granularity
from .data.deriv_client import get_candles
from .analysis.signal import compute_indicators, analyze_and_signal
from .storage.db import (
    init_db, get_or_create_user, record_usage, count_usage_today,
    get_first_seen_date, is_vip, set_vip, remove_vip, list_vip, vip_stats,
    log_signal, set_country
)

# --------- Conversation states ---------
ASK_PAIR, ASK_TF, ASK_COUNTRY = range(3)

TF_KEYBOARD = ReplyKeyboardMarkup([["M5", "M10", "M15"]], one_time_keyboard=True, resize_keyboard=True)

# --------- Helpers ---------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --------- Commands ---------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id)
    msg = (
        "👋 Welcome to BD Trader Auto Bot\n\n"
        "Use /getsignal to generate a real-time signal.\n"
        "No OTC pairs allowed. Default timeframe options: M5, M10, M15.\n\n"
        "Free plan: Day 1 unlimited. From Day 2: max 5 signals/day.\n"
        f"For Premium, contact {OWNER_CONTACT}."
    )
    await update.message.reply_text(msg)

async def getsignal_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id)

    # Free/VIP Limit Check
    if not is_vip(user.id):
        first_seen = get_first_seen_date(user.id)
        if first_seen and first_seen < date.today():
            used = count_usage_today(user.id)
            if used >= 5:
                await update.message.reply_text(
                    "Your daily limit has been reached. Please try again after 3 hours or contact "
                    f"{OWNER_CONTACT} for Premium access."
                )
                return ConversationHandler.END

    await update.message.reply_text(
        "Please type a valid pair (e.g., EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD, ETHUSD).",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PAIR

async def ask_tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = (update.message.text or "").strip().upper()

    if is_otc_pair(pair):
        await update.message.reply_text("OTC pairs are not allowed. Please enter a different pair.")
        return ASK_PAIR
    if not is_valid_pair(pair):
        await update.message.reply_text("Invalid pair. Try again (e.g., EURUSD, XAUUSD, BTCUSD).")
        return ASK_PAIR

    context.user_data["pair_user"] = pair
    context.user_data["pair_deriv"] = to_deriv_symbol(pair)
    await update.message.reply_text("Select timeframe:", reply_markup=TF_KEYBOARD)
    return ASK_TF

async def ask_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tf = (update.message.text or "").strip().upper()
    if not is_supported_tf(tf):
        await update.message.reply_text("Invalid timeframe. Please choose one of M5, M10, M15.", reply_markup=TF_KEYBOARD)
        return ASK_TF

    context.user_data["tf"] = tf
    await update.message.reply_text(
        "Please type your country name (for future timezone adjustments).",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_COUNTRY

async def do_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = (update.message.text or "").strip().title()
    user = update.effective_user

    if country:
        # Store country text (timezone enhancement later)
        set_country(user.id, country, None)

    pair_user = context.user_data.get("pair_user")
    pair_deriv = context.user_data.get("pair_deriv")
    tf = context.user_data.get("tf")
    gran = granularity(tf)

    # Show analyzing info
    status = await update.message.reply_text(f"🔍 Analyzing {pair_user} on {tf}... Please wait.")

    try:
        candles = await get_candles(pair_deriv, gran, count=120)
        import pandas as pd
        df = compute_indicators(candles)
        result = analyze_and_signal(df, pair_user, tf)

        # Send signal
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result["message"])
        # Risk warning as separate message
        if result["risky"]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("⚠️ Risk Warning\nThis setup is considered risky. "
                      "Consider waiting for a cleaner setup or try another pair/timeframe.")
            )

        # Log + usage
        record_usage(user.id)
        log_signal(user.id, pair_user, tf, result["confidence"], result["risky"], result["message"])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Want another? Click /getsignal"
        )
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error while processing signal: {e}")
    finally:
        try:
            await status.delete()
        except Exception:
            pass

    return ConversationHandler.END

# --------- Admin Commands (Phase 6–7) ---------
async def setvip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setvip <user_id> <days>")
        return
    try:
        target = int(context.args[0]); days = int(context.args[1])
        set_vip(target, days)
        await update.message.reply_text(f"✅ VIP set for {target} for {days} days.")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def removevip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removevip <user_id>")
        return
    try:
        target = int(context.args[0])
        remove_vip(target)
        await update.message.reply_text(f"✅ VIP removed for {target}.")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def viplist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    rows = list_vip()
    if not rows:
        await update.message.reply_text("No active VIPs.")
        return
    lines = ["Active VIP users:"]
    for uid, exp in rows:
        lines.append(f"- {uid} (expires: {exp})")
    await update.message.reply_text("\n".join(lines))

async def vipstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    st = vip_stats()
    await update.message.reply_text(f"VIP: {st['vip']} / Total users: {st['total']}")

# --------- Main ---------
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("getsignal", getsignal_entry)],
        states={
            ASK_PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tf)],
            ASK_TF: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_country)],
            ASK_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_analyze)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    # Admin
    app.add_handler(CommandHandler("setvip", setvip_cmd))
    app.add_handler(CommandHandler("removevip", removevip_cmd))
    app.add_handler(CommandHandler("viplist", viplist_cmd))
    app.add_handler(CommandHandler("vipstats", vipstats_cmd))

    print("BD Trader Auto Bot is running...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
