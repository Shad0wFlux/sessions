import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
USERNAME, PASSWORD, TWO_FACTOR = range(3)

# Set up your bot token here
BOT_TOKEN = '8119162508:AAEYY_1zN5IkHlqXumcYR-6TFbbUVp-HOo0'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"Hello {user.first_name}! 👋\n\n"
        "Welcome to the Instagram Session Extractor Bot!\n\n"
        "This bot will help you extract your Instagram session ID securely.\n"
        "Your credentials are not stored and are only used for the extraction process.\n\n"
        "To get started, use the /extract command."
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_message = (
        "🔹 Commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/extract - Extract Instagram session ID\n"
        "/cancel - Cancel the current operation\n\n"
        "How to use:\n"
        "1. Use /extract to start the process\n"
        "2. Enter your Instagram username\n"
        "3. Enter your password (it's secure)\n"
        "4. If 2FA is enabled, enter the verification code\n"
        "5. Receive your session ID\n\n"
        "Note: Your login credentials are not stored."
    )
    await update.message.reply_text(help_message)

async def extract(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the extraction process by asking for Instagram username."""
    await update.message.reply_text(
        "Let's extract your Instagram session ID.\n\n"
        "First, please enter your Instagram username:"
    )
    return USERNAME

async def username_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the username and ask for password."""
    username = update.message.text
    context.user_data['username'] = username
    
    # Delete the message containing the username for security
    await update.message.delete()
    
    await update.message.reply_text(
        "Now, please enter your Instagram password:\n\n"
        "⚠️ Your password will be deleted from the chat immediately for security."
    )
    return PASSWORD

async def password_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the password and try to login."""
    password = update.message.text
    username = context.user_data.get('username')
    
    # Delete the message with the password immediately
    await update.message.delete()
    
    status_message = await update.message.reply_text("Attempting to login... Please wait.")
    
    # Initialize Instagram client
    client = Client()
    context.user_data['client'] = client
    
    try:
        # Attempt to login
        await update.message.reply_text("⏳ Processing login... Please wait.")
        client.login(username, password)
        
        # If login successful
        session_id = client.sessionid
        await save_and_send_session(update, context, session_id)
        return ConversationHandler.END
        
    except TwoFactorRequired:
        await status_message.edit_text(
            "Two-factor authentication is required.\n"
            "Please enter the verification code from your authentication app:"
        )
        return TWO_FACTOR
        
    except ChallengeRequired:
        await status_message.edit_text(
            "⚠️ Account verification challenge required. "
            "This bot currently supports only username/password and 2FA login methods.\n\n"
            "Please use the desktop version to handle this challenge."
        )
        return ConversationHandler.END
        
    except Exception as e:
        await status_message.edit_text(
            f"❌ Login failed: {str(e)}\n\n"
            "Please try again with /extract"
        )
        return ConversationHandler.END

async def two_factor_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle two-factor authentication."""
    verification_code = update.message.text
    client = context.user_data.get('client')
    
    # Delete the message with the verification code
    await update.message.delete()
    
    status_message = await update.message.reply_text("Verifying 2FA code...")
    
    try:
        client.two_factor_login(verification_code)
        session_id = client.sessionid
        await save_and_send_session(update, context, session_id)
        return ConversationHandler.END
        
    except Exception as e:
        await status_message.edit_text(
            f"❌ Two-factor verification failed: {str(e)}\n\n"
            "Please try again with /extract"
        )
        return ConversationHandler.END

async def save_and_send_session(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str) -> None:
    """Save the session to a file and send it to the user."""
    username = context.user_data.get('username')
    
    # Create a file with the session ID
    filename = f"session_{username}.txt"
    with open(filename, "w") as file:
        file.write(session_id)
    
    # Also create/append to sessions.txt file
    with open("sessions.txt", "a") as file:
        file.write(f"{username}: {session_id}\n")
    
    # Send success message
    success_message = (
        f"✅ Session extracted successfully!\n\n"
        f"Username: {username}\n"
        f"Session ID: `{session_id}`\n\n"
        f"This session has also been saved to the sessions.txt file."
    )
    
    await update.message.reply_text(success_message, parse_mode="Markdown")
    
    # Send the session file
    with open(filename, "rb") as file:
        await update.message.reply_document(
            document=file,
            caption=f"Instagram session ID for {username}"
        )
    
    # Clean up the individual session file
    os.remove(filename)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Your information has been discarded.\n\n"
        "Use /extract to start again."
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Set up the conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("extract", extract)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username_received)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_received)],
            TWO_FACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, two_factor_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print("Instagram Session Extractor Bot is starting...")
    print("Press Ctrl+C to stop the bot")
    main()