import websockets, json, asyncio, logging, re
from datetime import datetime
from typing import Callable, Any, Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class PicaBot:
  """
  A bot library for connecting and interacting with Picarto.tv chat websocket.
  """
  def __init__(
    self, 
    uri: str, 
    command_prefix: str, 
    bot_name: str, 
    server: str = "chat.picarto.tv"
  ):
    self.bot_name = bot_name
    self.uri = uri
    self.server = server
    self.prefix = command_prefix
    self.ws: Optional[websockets.WebSocketClientProtocol] = None
    self._listeners: Dict[str, List[Callable[..., Any]]] = {}
    self._reconnection_attempts = []
    self._commands: Dict[str, Callable[..., Any]] = {}
    
  @property
  def connected(self) -> bool:
      """Indicates whether the bot is currently connected to the server."""
      return self.ws is not None
  
  def _should_reconnect(self) -> bool:
    """
    Tracks reconnection attempts and prevents more than five within ten seconds.

    Returns:
      bool: True if reconnection is allowed, False otherwise.
    """
    self._reconnection_attempts.append(datetime.now())
    
    for attempt in self._reconnection_attempts:
      if (datetime.now() - attempt).seconds > 10:
        self._reconnection_attempts.remove(attempt)

    if len(self._reconnection_attempts) >= 5:
      return False

    return True
  
  async def connect(self):
    """
    Connects to the WebSocket server and begins listening for messages.

    This method will attempt to reconnect if the connection is lost, 
    up to a maximum of five attempts within ten seconds.
    """
    while self._should_reconnect():
      try:
        self.ws = await websockets.connect(self.uri)
        logger.info(f"Connected to {self.server}")
        await self._listen()
      except KeyboardInterrupt:
        await self.close()
        return
      except Exception as e:
        logger.error(f"Failed to connect: {e}")
      
      logger.info("Reconnecting in 1 second...")
      await asyncio.sleep(1)
    
    logger.info("Reconnection attempts exceeded. Exiting...")
  
  async def _listen(self):        
    """
    Listens for incoming messages from the WebSocket connection.

    This method is called after successfully connecting to the server.
    """
    try:
      async for message in self.ws:
        await self._on_message(message)
    except websockets.exceptions.ConnectionClosed as e:
      logger.error(f"Connection closed: {e}")
    except Exception as e:
      logger.error(f"Error: {e}")
    
  def _split_message(self, message: str) -> List[str]:
    """
    Splits a message into its components, respecting quoted strings.

    Parameters:
      message (str): The message to split.
      
    Returns:
       List[str]: A list of components of the message.
    """
    matches = re.findall(r'"(.*?)"|(\S+)', message)
    result = [m[0] if m[0] else m[1] for m in matches]
    return result
  
  async def _on_message(self, msg: str):
    """
    Handles incoming messages and triggers appropriate events.

    Parameters:
      msg (str): The raw message received from the WebSocket.
    """
    if not msg:
      return
    
    try:
      message = json.loads(msg)
    except json.JSONDecodeError:
      logger.error(f"Failed to parse message: {msg}")
      return
    
    await self.emit("raw", message)
    
    if message.get("t") == "c":
      for part in message["m"]:
        p_message = PicaMessage(part)
        who = p_message.user_name
        message = p_message.message
        if who == self.bot_name:
          continue
        
        if message.startswith(self.prefix):
          command_name, *args = self._split_message(message[len(self.prefix):])
          if command_name in self._commands:
            await self._commands[command_name](p_message, *args)
            continue

        await self.emit("message", p_message)
  
  async def send(self, message: dict):
    """
    Sends a message through the WebSocket connection.

    Parameters:
      message (dict): The message to send as a dictionary.
    
    Raises:
      ConnectionError: If not connected to the WebSocket server.
    """
    if self.ws is None:
      raise ConnectionError("Not connected")
    await self.ws.send(json.dumps(message))
  
  async def sent_message(self, message: str):
    """
    Sends a chat message.

    Parameters:
      message (str): The message to send as a string.
    
    Raises:
      ConnectionError: If not connected to the WebSocket server.
    """
    await self.send({
      "type": "chat",
      "message": message
    })
    
  async def delete_message(self, message_id: str, channel_id: str):
    """
    Deletes a message from a channel. It won't work if the bot isn't moderator.

    Parameters:
      message_id (str): The ID of the message to delete.
      channel_id (str): The ID of the channel where the message is located.

    Raises:
      ConnectionError: If not connected to the WebSocket server.
    """
    await self.send({
      "type": "removeMessage",
      "messageId": message_id,
      "channelId": channel_id
    })

  async def close(self):
    """
    Closes the WebSocket connection.
    """
    if self.ws is not None:
      await self.ws.close()
      
  async def emit(self, event: str, *args, **kwargs):
    """
    Emits a custom event, triggering all listeners registered for that event.

    Parameters:
      event (str): The name of the event.
      args: Positional arguments to pass to the event listeners.
      kwargs: Keyword arguments to pass to the event listeners.
    """
    if event in self._listeners:
      tasks = [listener(*args, **kwargs) for listener in self._listeners[event]]
      await asyncio.gather(*tasks)
  
  def on(self, event: str):
    """
    Registers a listener for a specific event.

    Parameters:
      event (str): The name of the event to listen for.
    """
    def decorator(func):
      if event not in self._listeners:
        self._listeners[event] = []
      self._listeners[event].append(func)
      return func
    return decorator
  
  def command(self, name: str):
    """
    Registers a command handler for a specific command.

    Parameters:
      event (str): The name of the event to listen for.
    """
    def decorator(func):
      self._commands[name] = func
      return func
    return decorator
  
  
  @staticmethod
  def from_token(
    token: str, 
    bot_name: str, 
    command_prefix: str = "!",
    server: str = "chat.picarto.tv", 
    secure: bool = True
  ):
    """
    Creates a PicaBot instance using an authentication token.

    Parameters:
      token (str): The authentication token.
      command_prefix (str): Prefix for bot commands.
      bot_name (str): The bot's username.
      server (str): The chat server to connect to.
      secure (bool): Whether to use a secure (wss) or insecure (ws) WebSocket connection.

    Returns:
      PicaBot: A configured instance of PicaBot.
    """
    return PicaBot(
      f"{'wss' if secure else 'ws'}://{server}/chat/token={token}", 
      command_prefix, 
      bot_name, 
      server
    )
  
  @staticmethod
  def from_password(
    username: str, 
    password: str, 
    bot_name: str, 
    command_prefix: str = "!", 
    server: str = "chat.picarto.tv", 
    secure: bool = True
  ):
    """
    Creates a PicaBot instance using the normal way

    Parameters:
      username (str): The bot's login username.
      password (str): The bot's login password. Get it from https://oauth.picarto.tv/chat/bot.
      bot_name (str): The bot's username.
      command_prefix (str): Prefix for bot commands.
      server (str): The chat server to connect to.
      secure (bool): Whether to use a secure (wss) or insecure (ws) WebSocket connection.

    Returns:
      PicaBot: A configured instance of PicaBot.
    """
    return PicaBot(
      f"{'wss' if secure else 'ws'}://{server}/bot/username={username}&password={password}", 
      command_prefix, 
      bot_name, 
      server
    )
    
class PicaMessage:
  """ 
  PicaMessage is a class designed to encapsulate the details of a message received from the WebSocket. 
  It extracts and provides easy access to various attributes related to the message, the channel it was sent in, and the user who sent it.
  """
  def __init__(self, message: dict):
    self.data = message
    
  @property
  def channel_id(self) -> str:
    """
    Returns:
      str: The ID of the channel the message was sent in.
    """
    return self.data["c"]
  
  @property
  def channel_name(self) -> str:
    """
    Returns:
      str: The name of the channel the message was sent in.
    """
    return self.data["rn"]
  
  @property
  def channel_color(self) -> str:
    """
    Returns:
      str: The username's color of the channel the message was sent in.
    """
    return self.data["rc"]
  
  @property
  def message_timestamp(self) -> int:
    """
    Returns:
      int: The Unix timestamp in milliseconds of the message.
    """
    return int(self.data["a"])
  
  @property
  def message_id(self) -> str:
    """
    Returns:
      str: The ID of the message.
    """
    return self.data["id"]
  
  @property
  def message(self) -> str:
    """
    Returns:
      str: The contents of the message.
    """
    return self.data["m"]
  
  @property
  def user_id(self) -> str:
    """
    Returns:
      str: The ID of the user who sent the message.
    """
    return self.data["u"]
  
  @property
  def user_name(self) -> str:
    """
    Returns:
      str: The username of the user who sent the message.
    """
    return self.data["n"]
  
  @property
  def user_color(self) -> str:
    """
    Returns:
      str: The username's color of the user who sent the message.
    """
    return self.data["k"]
  
  @property
  def user_profile_pic(self) -> str:
    """
    Returns:
      str: The URL of the user's profile picture.
    """
    return self.data["i"]
