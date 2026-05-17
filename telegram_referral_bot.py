import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN      = "8717273284:AAHZ5L4eZLE6XniPt-r11vg8P1M1tFk9vHM"
CHANNEL_ID     = "@Oencommunity"
ADMIN_IDS      = [1190231984]
POINTS_PER_REF = 10
DB_FILE        = "bot_data.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}}


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def get_user(db, user_id):
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
        }
    return db["users"][uid]


async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ I've Joined — Continue", callback_data="check_join")],
    ])


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Balance",     callback_data="balance"),
            InlineKeyboardButton("🔗 My Referral", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
            InlineKeyboardButton("💸 Withdraw",    callback_data="withdraw"),
        ],
        [InlineKeyboardButton("ℹ️ How it Works", callback_data="howto")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    args    = context.args
    db      = load_db()
    profile = get_user(db, user_id)
    profile["username"]   = user.username or ""
    profile["first_name"] = user.first_name or ""

    if args and profile["referred_by"] is None:
        ref_id = args[0]
        if ref_id != str(user_id) and ref_id in db["users"]:
            profile["referred_by"] = ref_id
            db["users"][ref_id]["points"]    += POINTS_PER_REF
            db["users"][ref_id]["referrals"] += 1
            try:
                await context.bot.send_message(
                    chat_id=int(ref_id),
                    text=f"🎉 *New Referral!*\n\n*{user.first_name}* joined using your link.\nYou earned *{POINTS_PER_REF} points!* 🪙",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    save_db(db)

    if not await is_member(context, user_id):
        await update.message.reply_text(
            f"👋 Welcome, *{user.first_name}!*\n\nTo use this bot, you must first join our channel.\nAfter joining, tap *\"I've Joined\"* below. ✅",
            parse_mode="Markdown",
            reply_markup=join_keyboard(),
        )
        return

    await update.message.reply_text(
        f"🏠 *Home Menu*\n\nWelcome back, *{user.first_name}!* 👋\n\nEarn points by inviting friends with your referral link. 🎁",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user    = query.from_user
    user_id = user.id
    data    = query.data
    await query.answer()

    if data == "check_join":
        if await is_member(context, user_id):
            db      = load_db()
            profile = get_user(db, user_id)
            profile["username"]   = user.username or ""
            profile["first_name"] = user.first_name or ""
            save_db(db)
            await query.edit_message_text(
                f"🏠 *Home Menu*\n\nWelcome, *{user.first_name}!* 👋\n\nEarn points by inviting friends! 🎁",
                parse_mode="Markdown",
                reply_markup=main_keyboard(),
            )
        else:
            await query.answer("❌ You haven't joined yet! Please join the channel first.", show_alert=True)
        return

    if not await is_member(context, user_id):
        await query.edit_message_text("⚠️ You must join our channel to use this bot.", reply_markup=join_keyboard())
        return

    db      = load_db()
    profile = get_user(db, user_id)
    back    = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]])

    if data == "balance":
        await query.edit_message_text(
            f"💰 *Your Balance*\n\n🪙 Points : *{profile['points']}*\n👥 Referrals : *{profile['referrals']}*\n📅 Member since : {profile['joined_at'][:10]}\n\nEach referral earns *{POINTS_PER_REF} points!*",
            parse_mode="Markdown", reply_markup=back,
        )

    elif data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        await query.edit_message_text(
            f"🔗 *Your Referral Link*\n\n`{ref_link}`\n\nShare this link with friends.\nYou earn *{POINTS_PER_REF} points* for every person who joins!\n\n👥 Total referrals: *{profile['referrals']}*",
            parse_mode="Markdown", reply_markup=back,
        )

    elif data == "leaderboard":
        all_users = sorted(db["users"].values(), key=lambda u: u["points"], reverse=True)[:10]
        medals = ["🥇","🥈","🥉"] + ["🏅"]*7
        lines = []
        for i, u in enumerate(all_users):
            name = u.get("first_name","Unknown") or f"User {u['id']}"
            you  = " ← You" if u["id"] == user_id else ""
            lines.append(f"{medals[i]} *{name}* — {u['points']} pts{you}")
        await query.edit_message_text(
            f"🏆 *Top 10 Leaderboard*\n\n" + ("\n".join(lines) if lines else "No users yet."),
            parse_mode="Markdown", reply_markup=back,
        )

    elif data == "withdraw":
        min_pts = 100
        if profile["points"] < min_pts:
            txt = f"💸 *Withdraw Points*\n\n🪙 Your points: *{profile['points']}*\n⚠️ Minimum required: *{min_pts} points*\n\nKeep referring to reach the minimum!"
        else:
            txt = f"💸 *Withdraw Request*\n\n🪙 Available: *{profile['points']} points*\n\nSend your bKash/Nagad number to the admin.\nAdmin will process within 24 hours. ✅"
        await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=back)

    elif data == "howto":
        await query.edit_message_text(
            f"ℹ️ *How It Works*\n\n1️⃣ Join our channel ✅\n2️⃣ Get your referral link 🔗\n3️⃣ Share with friends 📤\n4️⃣ They join → you earn *{POINTS_PER_REF} points* 🪙\n5️⃣ Redeem at 100 pts! 💸\n\nMore referrals = more earnings! 🚀",
            parse_mode="Markdown", reply_markup=back,
        )

    elif data == "home":
        await query.edit_message_text(
            f"🏠 *Home Menu*\n\nWelcome back, *{user.first_name}!* 👋\n\nEarn points by inviting friends! 🎁",
            parse_mode="Markdown", reply_markup=main_keyboard(),
        )

    save_db(db)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    db = load_db()
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n👤 Total Users: *{len(db['users'])}*\n🔗 Total Referrals: *{sum(u['referrals'] for u in db['users'].values())}*",
        parse_mode="Markdown",
    )


async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
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
    await update.message.reply_text(f"📢 Done!\n✅ Sent: {sent}\n❌ Failed: {failed}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("stats",     admin_stats))
    app.add_handler(CommandHandler("addpoints", admin_add_points))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
