# 🎵 Telegram Music Metadata Editor Bot

A Telegram bot that allows you to modify audio file metadata including title, artist, and album cover art.

## Features

✨ **Supports Multiple Audio Formats:**
- MP3 (ID3 tags)
- FLAC
- OGG Vorbis
- OGG Opus
- MP4/M4A/AAC
- WAV
- AIFF

🎯 **Edit Capabilities:**
- Change song title/name
- Change artist name
- Add or update album cover art
- Preview current metadata before changes
- Download modified file directly


## Usage

1. **Start the bot**
```bash
python bot.py
```

2. **In Telegram:**
   - Start a conversation with your bot
   - Send `/start` to begin
   - Send an audio file
   - Follow the prompts to edit metadata
   - Confirm changes and receive the modified file

## Commands

- `/start` - Start the bot and receive instructions
- `/cancel` - Cancel current operation

## How It Works

1. User sends an audio file to the bot
2. Bot reads and displays current metadata
3. User enters new title (or skips)
4. User enters new artist (or skips)
5. User optionally sends a new cover image
6. Bot shows a summary of changes
7. User confirms or cancels
8. Bot applies changes and sends back the modified file

## File Structure

```
music_changer/
├── bot.py              # Main bot logic and conversation handler
├── music_editor.py     # Audio metadata editing functions
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment file
├── .gitignore          # Git ignore rules
├── README.md          # This file
└── temp_files/        # Temporary directory for file processing
```

## Supported Metadata Tags

- **Title/Name**: Song title or name
- **Artist**: Artist or performer name
- **Album**: Album name
- **Cover Art**: Album artwork image (JPEG)

## Notes

- Temporary files are automatically cleaned up after processing
- Cover images are optimized to 1024x1024 for formats that support it
- File size limits depend on Telegram's limits (typically 50MB for files)
- The bot creates a `temp_files` directory for temporary storage

## Troubleshooting

### Bot doesn't start
- Check that your bot token is correct in `.env`
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### Metadata not updating
- Some audio files may have read-only permissions
- Try converting to a different format first

### Cover art not showing
- Ensure the image is in JPEG format
- Try a smaller image size

## License

This project is open source and available for personal use.

## Support

For issues or questions, refer to the [Telegram Bot API Documentation](https://core.telegram.org/bots/api) or [Mutagen Documentation](https://mutagen.readthedocs.io/).
