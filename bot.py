from websockets import connect as ws_connect
from websockets import WebSocketClientProtocol
from requests import post, get
from typing import Optional
from abc import abstractmethod
from time import sleep
from dataclasses import dataclass
from json import dumps as dumps_json, loads as loads_json
from asyncio import gather as async_gather, sleep as async_sleep

class Bot:
  @dataclass
  class PostReq:
    url: str
    headers: dict
    json: dict

  def __init__(self, auth: str, guild_id: str, channel_id: str) -> None:
    self.ws: Optional[WebSocketClientProtocol] = None

    self.post_req_ls: list[Bot.PostReq] = []
    self.sending_req_sem = 0
    
    self.interval: int = None
    self.heartbeat_d: int = None

    self.auth = auth
    self.guild_id = guild_id
    self.channel_id = channel_id
    self.session_id: str = None # init when READY

  @abstractmethod
  def handle_recv(self, data):
    pass
  
  async def connect(self):
    """ Connect to Discord Gateway """
    self.ws = await ws_connect('wss://gateway.discord.gg/?encoding=json&v=10', max_size=5000000)

    # identify
    await self.ws.send(
      dumps_json({
        'op': 2,
        'd': {
          'token': self.auth,
          'properties': {
            '$os': 'windows',
            '$browser': 'chrome',
            '$device': 'pc'
          }
        }
      })
    )
    identify_res = loads_json(await self.ws.recv())
    self.interval = int((identify_res['d']['heartbeat_interval'] - 2000) / 1000)
    print(f'[connect] connected with heartbeat interval: {self.interval}')

    # receive READY
    while self.session_id is None:
      data = loads_json(await self.ws.recv())
      if data['t'] == 'READY':
        self.session_id = data['d']['session_id']
        print('[connect] session_id:', self.session_id)

  async def start(self):
    """ Start bot """
    await async_gather(self.__heartbeat(), self.__listen())

  async def __heartbeat(self):
    """
    Send heartbeat to Discord Gateway\n
    Dont use this method directly, use start() instead
    """
    print('[heartbeat] heartbeat started')
    while self.ws.open:
      await async_sleep(self.interval)
      await self.ws.send(dumps_json({
        'op': 1,
        'd': self.heartbeat_d
      }))
      print(f'[heartbeat] send heartbeat: {self.heartbeat_d}')
    print('[heartbeat] heartbeat stopped')

  async def __listen(self):
    """
    Listen to Discord Gateway\n
    Dont use this method directly, use start() instead
    """
    print('[listen] start')
    while self.ws.open:
      data: dict = loads_json(await self.ws.recv())

      # update heartbeat
      if data.get('s', None) is not None:
        self.heartbeat_d = int(data['s'])

      if not self.is_filtered(data):
        self.handle_recv(data)

  def is_filtered (self, data: dict) -> bool:
    """ Filter data, return True if data is filtered """
    d = data.get('d', None)
    if d is None or isinstance(d, list):
      return False
    
    guild_id = d.get('guild_id', None)
    channel_id = d.get('channel_id', None)

    if guild_id is not None and guild_id != self.guild_id:
      return True
    if channel_id is not None and channel_id != self.channel_id:
      return True
    return False

  def __send_request(self, url: str, headers: dict, json: dict):
    """ Handle the flow of sending request """
    self.post_req_ls.append(Bot.PostReq(url, headers, json))
    if self.sending_req_sem != 0:
      return
    self.sending_req_sem += 1

    while self.sending_req_sem == 1 and len(self.post_req_ls) > 0:
      req = self.post_req_ls.pop(0)
      response = post(req.url, headers=req.headers, json=req.json)
      try:
        print(response.json())
      except:
        pass
      sleep(1)
    self.sending_req_sem -= 1

  def send_json (self, url, json):
    """ Send JSON to Discord API """
    self.__send_request(
      url,
      headers = {
        'Authorization': self.auth,
        'Content-Type': 'application/json'
      },
      json = json
    )

  def send_message (self, msg):
    """ Send message to Discord Channel """
    self.send_json(
      f'https://discord.com/api/v9/channels/{self.channel_id}/messages',
      { 'content': msg }
    )

  def send_interaction (
    self, application_id: str,
    command_version: str, command_id: str, command_nm: str,
    options: list = []
  ):
    """ Send Interaction to Discord Channel """
    self.send_json(
      "https://discord.com/api/v9/interactions",
      {
        "type": 2,
        "application_id": application_id,
        "guild_id": self.guild_id,
        "channel_id": self.channel_id,
        "session_id": self.session_id,
        "data": {
          "version": command_version,
          "id": command_id,
          "name": command_nm,
          "options": options
        }
      }
    )

  def get_message (self, limit: int = 10):
    return get(
      f'https://discord.com/api/v9/channels/{self.channel_id}/messages?limit={limit}',
      headers = {
        'Authorization': self.auth
      }
    ).json()
