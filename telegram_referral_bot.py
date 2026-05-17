"""
=======================================================
  Telegram Referral Bot with Channel Join + Points System
  -------------------------------------------------------
  Features:
    - Mandatory channel join before using bot
    - Unique referral link per user
    - Points earned per successful referral
    - Balance, leaderboard, withdraw commands
    - Admin panel to manage users & set points
=======================================================

HOW TO SETUP:
1. Install dependencies:
      pip install python-telegram-bot==20.7

2. Create a bot via @BotFather on Telegram → get BOT_TOKEN

3. Fill in the CONFIG section below:
      BOT_TOKEN      → your bot token
      CHANNEL_ID     → your channel username e.g. @mychannel
      ADMIN_IDS      → your Telegram user ID(s)
      POINTS_PER_REF → how many points per referral

4. Run:
      python telegram_referral_bot.py
"""

import logging
import json
import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberStatus,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────
#  ★  CONFIG — Fill these before running  ★
# ─────────────────────────────────────────────
BOT_TOKEN      = "8717273284:AAHZ5L4eZLE6XniPt-r11vg8P1M1tFk9vHM"
CHANNEL_ID     = "@Oencommunity"
ADMIN_IDS      = [1190231984]
POINTS_PER_REF = 10                              # Points given per referral
DB_FILE        = "bot_data.json"                 # Local database file
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#   DATABASE  (simple JSON file)
# ══════════════════════════════════════════════

def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}}


def save_db(db: dict):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def get_user(db: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "id": user_id,
            "username": "",
            "first_name": "",
            "points": 0,
            "referrals": 0,
            "referred_by": None,
            "joined_at": datetime.now().isoformat(),
            "pending_withdraw": 0,
        }
    return db["users"][uid]


# ══════════════════════════════════════════════
#   HELPERS
# ══════════════════════════════════════════════

async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ]
    except Exception:
        return False


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ I've Joined — Continue", callback_data="check_join")],
    ])


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Balance",    callback_data="balance"),
            InlineKeyboardButton("🔗 My Referral", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
            InlineKeyboardButton("💸 Withdraw",    callback_data="withdraw"),
        ],
        [InlineKeyboardButton("ℹ️ How it Works", callback_data="howto")],
    ])


# ══════════════════════════════════════════════
#   /start
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    args    = context.args  # referral param

    db      = load_db()
    profile = get_user(db, user_id)

    # Update name/username
    profile["username"]   = user.username or ""
    profile["first_name"] = user.first_name or ""

    # Credit referrer (only first time, and can't refer yourself)
    if args and profile["referred_by"] is None:
        ref_id = args[0]
        if ref_id != str(user_id) and ref_id in db["users"]:
            profile["referred_by"] = ref_id
            db["users"][ref_id]["points"]   += POINTS_PER_REF
            db["users"][ref_id]["referrals"] += 1
            # Notify referrer
            try:
                await context.bot.send_message(
                    chat_id=int(ref_id),
                    text=(
                        f"🎉 *New Referral!*\n\n"
                        f"*{user.first_name}* joined using your link.\n"
                        f"You earned *{POINTS_PER_REF} points!* 🪙\n\n"
                        f"Keep sharing to earn more!"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    save_db(db)

    # Check channel membership
    if not await is_member(update, context, user_id):
        await update.message.reply_text(
            f"👋 Welcome, *{user.first_name}!*\n\n"
            f"To use this bot, you must first join our channel.\n"
            f"After joining, tap *\"I've Joined\"* below. ✅",
            parse_mode="Markdown",
            reply_markup=join_keyboard(),
        )
        return

    await show_home(update, context, user.first_name, edit=False)


async def show_home(update, context, first_name, edit=False):
    text = (
        f"🏠 *Home Menu*\n\n"
        f"Welcome back, *{first_name}!* 👋\n\n"
        f"Earn points by inviting friends with your referral link.\n"
        f"Redeem points for rewards! 🎁"
    )
    if edit:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=main_keyboard()
        )


# ══════════════════════════════════════════════
#   CALLBACK QUERY HANDLER
# ══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user    = query.from_user
    user_id = user.id
    data    = query.data

    await query.answer()

    # ── Check join ──────────────────────────────
    if data == "check_join":
        if await is_member(update, context, user_id):
            db      = load_db()
            profile = get_user(db, user_id)
            profile["username"]   = user.username or ""
            profile["first_name"] = user.first_name or ""
            save_db(db)
            await show_home(update, context, user.first_name, edit=True)
        else:
            await query.answer("❌ You haven't joined yet! Please join the channel first.", show_alert=True)
        return

    # ── Guard: must be member ────────────────────
    if not await is_member(update, context, user_id):
        await query.edit_message_text(
            "⚠️ You must join our channel to use this bot.",
            reply_markup=join_keyboard(),
        )
        return

    db      = load_db()
    profile = get_user(db, user_id)

    # ── Balance ──────────────────────────────────
    if data == "balance":
        await query.edit_message_text(
            f"💰 *Your Balance*\n\n"
            f"🪙 Points : *{profile['points']}*\n"
            f"👥 Referrals : *{profile['referrals']}*\n"
            f"📅 Member since : {profile['joined_at'][:10]}\n\n"
            f"Each referral earns you *{POINTS_PER_REF} points!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
        )

    # ── Referral Link ─────────────────────────────
    elif data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        await query.edit_message_text(
            f"🔗 *Your Referral Link*\n\n"
            f"`{ref_link}`\n\n"
            f"Share this link with friends.\n"
            f"You earn *{POINTS_PER_REF} points* for every person who joins!\n\n"
            f"👥 Total referrals so far: *{profile['referrals']}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
        )

    # ── Leaderboard ───────────────────────────────
    elif data == "leaderboard":
        all_users = sorted(
            db["users"].values(),
            key=lambda u: u["points"],
            reverse=True,
        )[:10]

        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines  = []
        for i, u in enumerate(all_users):
            name = u.get("first_name", "Unknown") or f"User {u['id']}"
            you  = " ← You" if u["id"] == user_id else ""
            lines.append(f"{medals[i]} *{name}* — {u['points']} pts{you}")

        board = "\n".join(lines) if lines else "No users yet."
        await query.edit_message_text(
            f"🏆 *Top 10 Leaderboard*\n\n{board}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
        )

    # ── Withdraw ──────────────────────────────────
    elif data == "withdraw":
        min_pts = 100  # Minimum points to withdraw
        if profile["points"] < min_pts:
            txt = (
                f"💸 *Withdraw Points*\n\n"
                f"🪙 Your points: *{profile['points']}*\n"
                f"⚠️ Minimum required: *{min_pts} points*\n\n"
                f"Keep referring to reach the minimum!"
            )
        else:
            txt = (
                f"💸 *Withdraw Request*\n\n"
                f"🪙 Available: *{profile['points']} points*\n\n"
                f"To withdraw, send a message to the admin with:\n"
                f"• Your bKash / Nagad number\n"
                f"• Amount of points to redeem\n\n"
                f"An admin will process your request within 24 hours. ✅"
            )
        await query.edit_message_text(
            txt,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
        )

    # ── How it works ──────────────────────────────
    elif data == "howto":
        await query.edit_message_text(
            "ℹ️ *How It Works*\n\n"
            f"1️⃣ Join our channel ✅\n"
            f"2️⃣ Get your personal referral link 🔗\n"
            f"3️⃣ Share it with friends 📤\n"
            f"4️⃣ When they join, you earn *{POINTS_PER_REF} points* 🪙\n"
            f"5️⃣ Redeem points for cash rewards once you hit 100 pts! 💸\n\n"
            f"The more you refer, the more you earn! 🚀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
        )

    # ── Home ──────────────────────────────────────
    elif data == "home":
        await show_home(update, context, user.first_name, edit=True)

    save_db(db)


# ══════════════════════════════════════════════
#   ADMIN COMMANDS
# ══════════════════════════════════════════════

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: /stats"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    db    = load_db()
    total = len(db["users"])
    total_refs = sum(u["referrals"] for u in db["users"].values())
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👤 Total Users  : *{total}*\n"
        f"🔗 Total Referrals : *{total_refs}*",
        parse_mode="Markdown",
    )


async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: /addpoints <user_id> <points>"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_id = str(context.args[0])
        pts       = int(context.args[1])
        db        = load_db()
        if target_id in db["users"]:
            db["users"][target_id]["points"] += pts
            save_db(db)
            await update.message.reply_text(f"✅ Added {pts} points to user {target_id}.")
        else:
            await update.message.reply_text("❌ User not found.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addpoints <user_id> <points>")


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: /broadcast <message>"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <your message>")
        return
    msg = " ".join(context.args)
    db  = load_db()
    sent, failed = 0, 0
    for uid in db["users"]:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}")


# ══════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))

    # Admin commands
    app.add_handler(CommandHandler("stats",     admin_stats))
    app.add_handler(CommandHandler("addpoints", admin_add_points))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))

    # Buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
