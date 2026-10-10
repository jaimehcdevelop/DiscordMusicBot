# 🎵 Discord Music & TTS Bot

An advanced music bot for Discord programmed in Python using `discord.py`. It features support for YouTube, Playlists, Spotify link integration (via oEmbed), interactive buttons, and an innovative Text-to-Speech (TTS) system powered by neural networks (`edge-tts`).

## ✨ Features

- **🎶 YouTube Playback:** Supports direct searches and URL links.
- **📚 YouTube Playlists:** Loads and queues full playlists.
- **🟢 Spotify Support:** Converts Spotify track and playlist links into exact YouTube searches.
- **🗣️ Celestial Preacher (TTS):** Converts text to speech using high-quality neural voices with built-in audio effects (equalization and echo).
- **🎛️ Interactive Buttons:** Control the music directly from the chat (Pause, Skip, Shuffle, Stop) via Discord UI Views.
- **🛡️ Anti-Timeouts:** Automatic reconnection system and extreme shielding against zombie connections or network drops.
- **💤 Auto-Disconnect:** Automatically leaves the voice channel after 1 minute of inactivity to save resources.

## 🛠️ Prerequisites

Before running this bot, make sure you have the following installed:
- [Python 3.8+](https://www.python.org/downloads/)
- [FFmpeg](https://ffmpeg.org/download.html) (Installed and added to your system PATH, or located at `C:/ffmpeg/bin/ffmpeg.exe` as currently hardcoded).

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git)
   cd YOUR_REPOSITORY_NAME