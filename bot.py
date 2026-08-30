import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from music_editor import MusicEditor

# Load environment variables
load_dotenv()

# Set up logging with rotating file handler
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = RotatingFileHandler('bot.log', maxBytes=1_000_000, backupCount=2)
log_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[log_handler, console_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Create temp directory for files
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# Conversation states
WAITING_FOR_AUDIO, WAITING_FOR_MENU, WAITING_FOR_TITLE_INPUT, WAITING_FOR_ARTIST_INPUT, WAITING_FOR_COVER_INPUT = range(5)

# MIME type to extension mapping
MIME_TO_EXTENSION = {
    'audio/mpeg': '.mp3',
    'audio/mp3': '.mp3',
    'audio/x-mp3': '.mp3',
    'audio/flac': '.flac',
    'audio/x-flac': '.flac',
    'audio/ogg': '.ogg',
    'audio/vorbis': '.ogg',
    'audio/x-vorbis': '.ogg',
    'audio/opus': '.opus',
    'audio/x-opus': '.opus',
    'audio/x-m4a': '.m4a',
    'audio/mp4': '.m4a',
    'audio/aac': '.aac',
    'audio/wav': '.wav',
    'audio/x-wav': '.wav',
    'audio/wave': '.wav',
    'audio/aiff': '.aiff',
    'audio/x-aiff': '.aiff',
}


class MusicMetadataBot:
    def __init__(self):
        self.music_editor = MusicEditor(TEMP_DIR)
        self.user_sessions = {}

    def _get_file_extension(self, file_name: str, mime_type: str = None) -> str:
        """Get file extension based on filename or MIME type"""
        if file_name:
            _, ext = os.path.splitext(file_name)
            if ext.lower() in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wav', '.aiff', '.opus']:
                return ext.lower()

        # Fall back to MIME type
        if mime_type:
            ext = MIME_TO_EXTENSION.get(mime_type.lower())
            if ext:
                return ext

        # Default to .mp3
        return '.mp3'

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start command handler"""
        await update.message.reply_text(
            "👋 Hey! Welcome to the Music Tag Editor\n\n"
            "─────────────────\n"
            "Drop any audio file here and I'll let\nyou edit its tags before saving.\n\n"
            "▸ 🎵 Song title\n"
            "▸ 🎤 Artist name\n"
            "▸ 🖼 Cover art\n\n"
            "Forward a file from any downloader bot\nto get started!"
        )
        return WAITING_FOR_AUDIO

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Help command handler"""
        await update.message.reply_text(
            "ℹ️ How to use:\n\n"
            "─────────────────\n\n"
            "▸ Forward any audio file here\n"
            "▸ Use the menu to edit title, artist or cover\n"
            "▸ Hit Save & Send to get your file back"
        )

    async def receive_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive audio file from user"""
        # Handle URL/link messages
        if update.message.text:
            if update.message.text.startswith(('http://', 'https://', 'www.')):
                await update.message.reply_text(
                    "❌ Link received\n\n"
                    "─────────────────\n\n"
                    "I need the actual audio file. Please forward the audio file\nfrom the downloader bot (the message that shows a music note 🎵)."
                )
            else:
                await update.message.reply_text(
                    "🎵 Please send an audio file\n\n"
                    "─────────────────\n\n"
                    "Supported formats: MP3, FLAC, OGG, M4A, WAV, etc."
                )
            return WAITING_FOR_AUDIO

        if not update.message.audio and not update.message.document:
            await update.message.reply_text(
                "🎵 No audio detected\n\n"
                "─────────────────\n\n"
                "Please send an audio file (or document). Supported formats: MP3, FLAC, OGG, M4A, WAV, etc."
            )
            return WAITING_FOR_AUDIO34

        try:
            # Get file info
            if update.message.audio:
                file = update.message.audio
                filename = file.file_name
                mime_type = file.mime_type
            else:
                file = update.message.document
                filename = file.file_name
                mime_type = file.mime_type

            # Determine extension
            ext = self._get_file_extension(filename, mime_type)

            # Build filename with correct extension
            if not filename:
                filename = f"audio_{file.file_id}{ext}"
            else:
                base_name = os.path.splitext(filename)[0]
                filename = f"{base_name}{ext}"

            # Download file
            file_obj = await context.bot.get_file(file.file_id)
            file_path = TEMP_DIR / f"{update.effective_user.id}_{filename}"
            await file_obj.download_to_drive(file_path)

            # Get current metadata
            current_data = self.music_editor.read_metadata(str(file_path))

            # Store session data
            user_id = update.effective_user.id
            self.user_sessions[user_id] = {
                'file_path': file_path,
                'filename': filename,
                'title': None,
                'artist': None,
                'cover_path': None,
                'current_title': current_data.get('title', 'Unknown'),
                'current_artist': current_data.get('artist', 'Unknown'),
                'menu_message_id': None,
                'prompt_message_id': None,
            }

            # Show the menu
            await self._show_menu(update, context, user_id)
            return WAITING_FOR_MENU

        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            await update.message.reply_text(
                "❌ Error processing file\n\n"
                "─────────────────\n\n"
                f"{str(e)}"
            )
            return WAITING_FOR_AUDIO

    async def _show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show the inline keyboard menu for editing metadata"""
        session = self.user_sessions.get(user_id)
        if not session:
            return

        title = session['title'] if session['title'] else session['current_title']
        artist = session['artist'] if session['artist'] else session['current_artist']
        cover_status = "✓" if session['cover_path'] else "✗"

        keyboard = [
            [InlineKeyboardButton(f"✏️  Title: {title[:30]}", callback_data="edit_title")],
            [InlineKeyboardButton(f"🎤  Artist: {artist[:30]}", callback_data="edit_artist")],
            [InlineKeyboardButton(f"🖼  Cover {cover_status}", callback_data="edit_cover")],
            [InlineKeyboardButton("─────────────────", callback_data="noop")],
            [
                InlineKeyboardButton("✅ Save & Send", callback_data="save_and_send"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_edit"),
            ],
        ]

        message_text = (
            f"📋 Editing: {session['filename']}\n\n"
            f"─────────────────\n\n"
            f"Current metadata:\n"
            f"▸ 🎵 Title: {session['current_title']}\n"
            f"▸ 🎤 Artist: {session['current_artist']}\n\n"
            f"New values:\n"
            f"▸ 🎵 Title: {title}\n"
            f"▸ 🎤 Artist: {artist}\n"
            f"▸ 🖼 Cover: {cover_status}\n\n"
            f"What would you like to change?"
        )

        # If menu already exists, edit it in place
        if session['menu_message_id']:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=session['menu_message_id'],
                    text=message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error editing menu message: {e}")
                # Fallback: send new message
                msg = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                session['menu_message_id'] = msg.message_id
        else:
            # First time: send new message and store ID
            if update.message:
                msg = await update.message.reply_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                msg = await update.callback_query.edit_message_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                # callback_query.edit doesn't return the message, use callback_query.message
                msg = update.callback_query.message

            session['menu_message_id'] = msg.message_id

    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle inline keyboard button presses"""
        query = update.callback_query
        user_id = update.effective_user.id

        if user_id not in self.user_sessions:
            await query.answer("Session expired. Please send an audio file again.", show_alert=True)
            return WAITING_FOR_AUDIO

        if query.data == "noop":
            await query.answer()
            return WAITING_FOR_MENU

        if query.data == "edit_title":
            await query.answer()
            prompt_text = (
                "🎵 New title\n\n"
                "─────────────────\n\n"
                "Send the new song title:"
            )
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=prompt_text
            )
            self.user_sessions[user_id]['prompt_message_id'] = msg.message_id
            context.user_data['editing'] = 'title'
            return WAITING_FOR_TITLE_INPUT

        elif query.data == "edit_artist":
            await query.answer()
            prompt_text = (
                "🎤 New artist\n\n"
                "─────────────────\n\n"
                "Send the new artist name:"
            )
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=prompt_text
            )
            self.user_sessions[user_id]['prompt_message_id'] = msg.message_id
            context.user_data['editing'] = 'artist'
            return WAITING_FOR_ARTIST_INPUT

        elif query.data == "edit_cover":
            await query.answer()
            prompt_text = (
                "🖼 New cover\n\n"
                "─────────────────\n\n"
                "Send the album cover image (or send /cancel to skip):"
            )
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=prompt_text
            )
            self.user_sessions[user_id]['prompt_message_id'] = msg.message_id
            context.user_data['editing'] = 'cover'
            return WAITING_FOR_COVER_INPUT

        elif query.data == "save_and_send":
            await query.answer()
            return await self.apply_changes(update, context)

        elif query.data == "cancel_edit":
            await query.answer()
            self._cleanup_session(user_id)
            await query.edit_message_text(
                "❌ Cancelled\n\n"
                "─────────────────\n\n"
                "Send /start to begin again."
            )
            return ConversationHandler.END

        return WAITING_FOR_MENU

    async def receive_title_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive title input from inline menu"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return WAITING_FOR_AUDIO

        if update.message.text:
            self.user_sessions[user_id]['title'] = update.message.text

            # Delete user's message
            try:
                await update.message.delete()
            except Exception as e:
                logger.debug(f"Could not delete user message: {e}")

            # Delete prompt message
            session = self.user_sessions[user_id]
            if session['prompt_message_id']:
                try:
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=session['prompt_message_id']
                    )
                except Exception as e:
                    logger.debug(f"Could not delete prompt message: {e}")
                session['prompt_message_id'] = None

            # Show updated menu in place
            await self._show_menu(update, context, user_id)
            return WAITING_FOR_MENU
        else:
            await update.message.reply_text(
                "❌ Invalid input\n\n"
                "─────────────────\n\n"
                "Please send text for the title."
            )
            return WAITING_FOR_TITLE_INPUT

    async def receive_artist_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive artist input from inline menu"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return WAITING_FOR_AUDIO

        if update.message.text:
            self.user_sessions[user_id]['artist'] = update.message.text

            # Delete user's message
            try:
                await update.message.delete()
            except Exception as e:
                logger.debug(f"Could not delete user message: {e}")

            # Delete prompt message
            session = self.user_sessions[user_id]
            if session['prompt_message_id']:
                try:
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=session['prompt_message_id']
                    )
                except Exception as e:
                    logger.debug(f"Could not delete prompt message: {e}")
                session['prompt_message_id'] = None

            # Show updated menu in place
            await self._show_menu(update, context, user_id)
            return WAITING_FOR_MENU
        else:
            await update.message.reply_text(
                "❌ Invalid input\n\n"
                "─────────────────\n\n"
                "Please send text for the artist name."
            )
            return WAITING_FOR_ARTIST_INPUT

    async def receive_cover_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive cover image from inline menu"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return WAITING_FOR_AUDIO

        if update.message.photo:
            try:
                from PIL import Image
                import io

                photo = update.message.photo[-1]
                file_obj = await context.bot.get_file(photo.file_id)

                # Download to memory first
                buf = io.BytesIO()
                await file_obj.download_to_memory(buf)
                buf.seek(0)

                # Convert to proper RGB JPEG
                img = Image.open(buf).convert('RGB')
                cover_path = TEMP_DIR / f"{user_id}_cover.jpg"
                img.save(str(cover_path), format='JPEG', quality=95)

                self.user_sessions[user_id]['cover_path'] = str(cover_path)

                # Delete user's message (the photo)
                try:
                    await update.message.delete()
                except Exception as e:
                    logger.debug(f"Could not delete user message: {e}")

                # Delete prompt message
                session = self.user_sessions[user_id]
                if session['prompt_message_id']:
                    try:
                        await context.bot.delete_message(
                            chat_id=update.effective_chat.id,
                            message_id=session['prompt_message_id']
                        )
                    except Exception as e:
                        logger.debug(f"Could not delete prompt message: {e}")
                    session['prompt_message_id'] = None

                # Show updated menu in place
                await self._show_menu(update, context, user_id)
                return WAITING_FOR_MENU
            except Exception as e:
                logger.error(f"Error receiving cover: {e}")
                await update.message.reply_text(
                    "❌ Error processing image\n\n"
                    "─────────────────\n\n"
                    f"{str(e)}"
                )
                return WAITING_FOR_COVER_INPUT
        else:
            await update.message.reply_text(
                "🖼 No image detected\n\n"
                "─────────────────\n\n"
                "Please send an image file."
            )
            return WAITING_FOR_COVER_INPUT

    async def apply_changes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Apply metadata changes to audio file"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return WAITING_FOR_AUDIO

        try:
            query = update.callback_query
            session = self.user_sessions[user_id]

            # Helper function to create progress bar
            def progress_bar(filled: int, total: int = 10) -> str:
                bar = "█" * filled + "▱" * (total - filled)
                return bar

            # Step 1: Processing your file
            await query.edit_message_text(
                "⏳ Processing your file...\n\n"
                f"{progress_bar(0)}  0%\n"
                "─────────────────"
            )
            await asyncio.sleep(0.4)

            # Step 2: Writing tags
            await query.edit_message_text(
                "📝 Writing tags...\n\n"
                f"{progress_bar(2)}  20%\n"
                "─────────────────"
            )
            await asyncio.sleep(0.4)

            # Apply changes (metadata editing)
            output_path = self.music_editor.edit_metadata(
                str(session['file_path']),
                title=session['title'],
                artist=session['artist'],
                cover_path=session['cover_path']
            )

            # Step 3: Embedding cover art (only if cover exists)
            if session['cover_path'] and Path(session['cover_path']).exists():
                await query.edit_message_text(
                    "🖼 Embedding cover art...\n\n"
                    f"{progress_bar(4)}  40%\n"
                    "─────────────────"
                )
                await asyncio.sleep(0.4)

            # Step 4: Finalising file
            await query.edit_message_text(
                "🔧 Finalising file...\n\n"
                f"{progress_bar(6)}  60%\n"
                "─────────────────"
            )
            await asyncio.sleep(0.4)

            # Step 5: Uploading to Telegram
            await query.edit_message_text(
                "📤 Uploading to Telegram...\n\n"
                f"{progress_bar(8)}  80%\n"
                "─────────────────"
            )

            # Send modified file back
            with open(output_path, 'rb') as f:
                title = session['title'] or session['current_title']
                artist = session['artist'] or session['current_artist']

                # Send with thumbnail if cover was set
                if session['cover_path'] and Path(session['cover_path']).exists():
                    with open(session['cover_path'], 'rb') as thumb:
                        await context.bot.send_audio(
                            chat_id=update.effective_chat.id,
                            audio=f,
                            title=title,
                            performer=artist,
                            thumbnail=thumb
                        )
                else:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=f,
                        title=title,
                        performer=artist
                    )

            # Step 6: Done!
            await query.edit_message_text(
                "✅ Done!\n\n"
                f"{progress_bar(10)}  100%\n"
                "─────────────────\n\n"
                "Send another audio file or /cancel to quit."
            )
            await asyncio.sleep(0.5)

            # Delete the done message
            try:
                await query.delete_message()
            except Exception as e:
                logger.debug(f"Could not delete done message: {e}")

            # Cleanup
            self._cleanup_session(user_id)
            return WAITING_FOR_AUDIO

        except Exception as e:
            logger.error(f"Error applying changes: {e}")
            await query.edit_message_text(
                "❌ Error processing file\n\n"
                "─────────────────\n\n"
                f"{str(e)}"
            )
            self._cleanup_session(user_id)
            return WAITING_FOR_AUDIO

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel operation"""
        user_id = update.effective_user.id
        self._cleanup_session(user_id)

        await update.message.reply_text(
            "❌ Cancelled\n\n"
            "─────────────────\n\n"
            "Send /start to begin again."
        )
        return ConversationHandler.END

    def _cleanup_session(self, user_id: int):
        """Clean up temporary files for user"""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            try:
                if Path(session['file_path']).exists():
                    Path(session['file_path']).unlink()
                if session['cover_path'] and Path(session['cover_path']).exists():
                    Path(session['cover_path']).unlink()
            except Exception as e:
                logger.error(f"Error cleaning up files: {e}")

            # Clear message IDs
            session['menu_message_id'] = None
            session['prompt_message_id'] = None
            del self.user_sessions[user_id]


async def post_init(application):
    """Register bot commands with Telegram and clear any old sessions"""
    try:
        # Clear any webhook that might be active
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared")
    except Exception as e:
        logger.debug(f"Webhook clear attempt: {e}")

    # Register bot commands
    await application.bot.set_my_commands([
        ("start", "🎵 Start the music editor"),
        ("cancel", "❌ Cancel current operation"),
        ("help", "ℹ️ How to use this bot"),
    ])


async def main():
    """Main function to run the bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env file")

    bot_instance = MusicMetadataBot()

    # Create application
    application = Application.builder().token(token).post_init(post_init).build()

    # Conversation handler with callback query
    conv_handler = ConversationHandler(
        per_chat=True,
        per_message=False,
        entry_points=[CommandHandler('start', bot_instance.start)],
        states={
            WAITING_FOR_AUDIO: [
                MessageHandler(
                    (filters.AUDIO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
                    bot_instance.receive_audio
                )
            ],
            WAITING_FOR_MENU: [
                CallbackQueryHandler(bot_instance.handle_menu_callback),
            ],
            WAITING_FOR_TITLE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.receive_title_input),
            ],
            WAITING_FOR_ARTIST_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.receive_artist_input),
            ],
            WAITING_FOR_COVER_INPUT: [
                MessageHandler(
                    (filters.PHOTO | filters.TEXT) & ~filters.COMMAND,
                    bot_instance.receive_cover_input
                ),
            ],
        },
        fallbacks=[CommandHandler('cancel', bot_instance.cancel)],
    )

    application.add_handler(conv_handler)

    # Add help command handler (outside conversation)
    application.add_handler(CommandHandler('help', bot_instance.help))

    logger.info("Bot started! Listening for messages...")
    logger.info("Press Ctrl+C to stop the bot")

    # Start the bot
    async with application:
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        logger.info("Bot is polling...")
        try:
            # Keep bot running
            await asyncio.sleep(float('inf'))
        finally:
            await application.updater.stop()
            await application.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\nBot stopped")
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()