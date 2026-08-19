"""
Telegram Bot entry point for the Pixel 10 Pro Google One Gemini Bot.

Commands:
  /start        – Show welcome message and available commands
  /login        – Begin credential capture flow (email → password)
  /check_offer  – Run Google One automation and look for Gemini Pro offer
  /get_link     – Show the last captured offer link
  /status       – Show current session status and device profile
  /cancel       – Cancel current operation
"""

import asyncio
import html
import logging
import sys

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
from device_simulator import create_device_profile
from google_automation import GoogleAutomationError, check_gemini_offer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
AWAIT_EMAIL, AWAIT_PASSWORD = range(2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(chat_id: int) -> dict:
    """Return (creating if absent) the session dict for *chat_id*."""
    if chat_id not in config.SESSION_STORE:
        config.SESSION_STORE[chat_id] = {}
    return config.SESSION_STORE[chat_id]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message with command menu and reset any pending conversation."""
    context.user_data.pop("pending_email", None)
    
    welcome_text = (
        "🤖 <b>Pixel 10 Pro Google One Bot</b>\n\n"
        "This bot simulates a Google Pixel 10 Pro (Android 16) device, "
        "logs into your Google account, and retrieves the <b>12-month free "
        "Gemini Pro</b> offer link from Google One.\n\n"
        "📋 <b>Available Commands:</b>\n"
        "• /login – Enter your Gmail credentials\n"
        "• /check_offer – Detect the Gemini Pro offer\n"
        "• /get_link – Show the last captured offer link\n"
        "• /status – View current session & device info\n"
        "• /cancel – Cancel current input\n\n"
        "⚠️ <b>Privacy Note:</b> Credentials are held in memory only for the "
        "duration of the session and never stored persistently."
    )
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END


# ── /login conversation ───────────────────────────────────────────────────────

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the login conversation – ask for email."""
    await update.message.reply_text(
        "📧 Please enter your Gmail address:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAIT_EMAIL


async def login_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the email and ask for password."""
    email = update.message.text.strip()
    context.user_data["pending_email"] = email
    
    await update.message.reply_text(
        f"✅ Email received: <code>{html.escape(email)}</code>\n\n🔒 Now enter your password:",
        parse_mode=ParseMode.HTML,
    )
    return AWAIT_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store credentials, generate a new device profile, and finish."""
    chat_id = update.effective_chat.id
    password = update.message.text.strip()
    email = context.user_data.pop("pending_email", "")

    session = _get_session(chat_id)
    session["email"] = email
    session["password"] = password
    session["device"] = create_device_profile()
    session["offer_link"] = None

    # Delete the user's password message for security
    try:
        await update.message.delete()
    except Exception:
        pass

    summary_text = html.escape(session["device"].summary())

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✅ <b>Credentials saved</b> and a new Pixel 10 Pro device profile has "
            "been created for this session.\n\n"
            f"<pre>{summary_text}</pre>\n\n"
            "Use /check_offer to search for the Gemini Pro offer."
        ),
        parse_mode=ParseMode.HTML,
    )
    return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the login conversation."""
    context.user_data.pop("pending_email", None)
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── /check_offer ──────────────────────────────────────────────────────────────

async def check_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Google One automation and report the result."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    if not session.get("email") or not session.get("password"):
        await update.message.reply_text(
            "⚠️ No credentials found. Please use /login first."
        )
        return

    device = session.get("device")
    if not device:
        device = create_device_profile()
        session["device"] = device

    status_msg = await update.message.reply_text(
        "⏳ Launching Pixel 10 Pro device simulator and logging in…\n"
        "This may take up to 60 seconds."
    )

    try:
        # Offload synchronous browser automation to background thread
        offer_link = await asyncio.to_thread(
            check_gemini_offer,
            session["email"],
            session["password"],
            device,
        )
    except GoogleAutomationError as exc:
        await update.message.reply_text(
            f"❌ <b>Automation Error:</b> {html.escape(str(exc))}",
            parse_mode=ParseMode.HTML
        )
        return
    except Exception as exc:
        logger.exception("Unexpected error in check_offer for chat %s", chat_id)
        await update.message.reply_text(
            f"❌ <b>Unexpected error:</b> {html.escape(str(exc))}",
            parse_mode=ParseMode.HTML
        )
        return

    if offer_link:
        session["offer_link"] = offer_link
        await update.message.reply_text(
            "🎉 <b>Gemini Pro Offer Found!</b>\n\n"
            "Click the link below to activate your 12-month free Gemini Pro:\n\n"
            f"🔗 <a href='{offer_link}'>{html.escape(offer_link)}</a>\n\n"
            "<i>Use /get_link to retrieve this link again.</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    else:
        await update.message.reply_text(
            "😔 No active Gemini Pro offer was detected on your Google One "
            "account at this time.\n\n"
            "The offer may not be available for your account region or may "
            "have already been activated. Try again later."
        )


# ── /get_link ─────────────────────────────────────────────────────────────────

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the last captured offer link for this session."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)
    link = session.get("offer_link")

    if link:
        await update.message.reply_text(
            f"🔗 <b>Last captured offer link:</b>\n\n"
            f"<a href='{link}'>{html.escape(link)}</a>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    else:
        await update.message.reply_text(
            "ℹ️ No offer link has been captured yet. "
            "Use /check_offer to search for the Gemini Pro offer."
        )


# ── /status ───────────────────────────────────────────────────────────────────

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current session and device profile summary."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    if not session:
        await update.message.reply_text(
            "ℹ️ No active session. Use /login to get started."
        )
        return

    email = session.get("email", "—")
    has_creds = bool(session.get("email") and session.get("password"))
    offer_link = session.get("offer_link")
    device = session.get("device")

    lines = [
        "📊 <b>Session Status</b>\n",
        f"Account: <code>{html.escape(email)}</code>",
        f"Credentials loaded: {'✅' if has_creds else '❌'}",
        f"Offer link captured: {'✅' if offer_link else '❌'}",
    ]

    if device:
        lines.append(f"\n<pre>{html.escape(device.summary())}</pre>")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ── Application setup ─────────────────────────────────────────────────────────

def main() -> None:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it in Replit Secrets and restart."
        )
        sys.exit(1)

    app = Application.builder().token(token).build()

    # /login conversation handler with cancel and start fallbacks
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            AWAIT_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_email)
            ],
            AWAIT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", login_cancel),
            CommandHandler("start", start),
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(login_conv)
    app.add_handler(CommandHandler("check_offer", check_offer))
    app.add_handler(CommandHandler("get_link", get_link))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancel", login_cancel))

    logger.info("Bot is running. Press Ctrl-C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
