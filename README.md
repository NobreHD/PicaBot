# PicaBot

PicaBot is a Python library designed to simplify the creation of bots for Picarto.tv. It provides a framework for handling WebSocket connections, managing commands, and handling events, making it easy to build and customize your own bot.

## Features

- **Easy WebSocket Connection**: Seamlessly connect to Picarto.tv using WebSockets.
- **Command Management**: Define custom commands with a prefix, and let your bot respond to user inputs.
- **Event Handling**: Register handlers for different events like `message` (more in the future).
- **Reconnection Handling**: Automatically attempts to reconnect in case of connection loss.

## Installation

You can install PicaBot via pip:

```bash
pip install picabot
```

## Usage

Here is a basic example of how to use PicaBot to create a bot:

```python
import asyncio
from picabot import PicaBot, PicaMessage

bot = PicaBot.from_password(
  "BOT_ACCOUNT_USERNAME",
  "BOT_ACCOUNT_PASSWORD from https://oauth.picarto.tv/chat/bot",
  "BOT_CHANNEL_NAME"
)

@bot.command("hello")
async def hello_command(message: PicaMessage, *args):
    await bot.sent_message(f"Hello, {message.user_name}!")

@bot.on("message")
async def on_message(message: PicaMessage):
  print(f"{message.user_name}: {message.message}")

asyncio.run_until_complete(bot.connect())
```

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## License

PicaBot is licensed under the GNU GPL-3.0 License. See `LICENSE` for more details.
