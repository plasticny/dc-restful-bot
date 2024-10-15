from bot import Bot
from asyncio import run

class SampleBot(Bot):
  def is_filtered(self, data):
    return False

  def handle_recv(self, data):
    print(data)
  
async def main():
  bot = SampleBot(
    auth='your dc token',
    guild_id='your guild id',
    channel_id='your channel id'
  )
  await bot.connect()
  bot.send_message("Hello, World!")
  await bot.start()

if __name__ == "__main__":
  run(main())
