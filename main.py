import discord

from discord.ext import commands
from discord import app_commands
from discord.utils import get
from discord import FFmpegAudio
import youtube_dl
import asyncio
from functools import partial
from async_timeout import timeout
import itertools
from datetime import datetime, timedelta
from youtube_dl import YoutubeDL
intents = discord.Intents.default()

#Setprefix command (เครื่องหมาย !)
bot = commands.Bot(command_prefix = "!", intents=discord.Intents.all(),help_command=None)

#ytld broke



#-------------------------------- Ytdl IS NOT WORKing dont mind this function na kub 
ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

}

ytdl = YoutubeDL(ytdlopts)
class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        await ctx.send(f'```ini\n[Added {data["title"]} to the Queue.]\n```', delete_after=15)

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title']}

        return cls(discord.FFmpegOpusAudio(source, **ffmpegopts), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpegopts), data=data, requester=requester)


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            self.np = await self._channel.send(f'**Now Playing:** `{source.title}` requested by '
                                               f'`{source.requester}`')
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    async def destroy(self, guild):
        """Disconnect and cleanup the player."""
        del players[self._guild]
        await self.guild.voice_client.disconnect()
        return self.bot.loop.create_task(self._cog.cleanup(guild))
#-------------------------------- Ytdl IS NOT WORKing ---------------------------#


#บอก Status
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"IM READY!")


#Slash Commands /
@bot.tree.command(name="ping", description="Shows pings/เเสดงค่าปิง")
async def ping(interaction: discord.Interaction):
     bot_latency = round(bot.latency * 1000)
     await interaction.response.send_message(f"ping = {bot_latency} ms.!!")

@bot.tree.command(name="help", description="dwalen helps you")
async def ping(interaction: discord.Interaction):
     await interaction.response.send_message(f"Press !help to show more commands")


#Prefix Commands !
@bot.command()
async def play(ctx,* ,search: str):
     channel = ctx.author.voice.channel
     voice_client = get(bot.voice_clients, guild=ctx.guild)

     if voice_client == None:
          ctx.channel.send("Joined")
          await channel.connect()
          voice_client = get(bot.voice_clients, guild=ctx.guild)


     _player = get_player(ctx)
     source = await YTDLSource.create_source(ctx, search, loop=bot.loop, download=False)

     await _player.queue.put(source)

players = {}
def get_player(ctx):
    try:
        player = players[ctx.guild.id]
    except:
        player = MusicPlayer(ctx)
        players[ctx.guild.id] = player
     
    return player

@bot.command()
async def stop(ctx):
     voice_client = get(bot.voice_clients, guild=ctx.guild)
     if voice_client == None:
          await ctx.channel.send("Dwalen is not connected to VC!")
          return

     if voice_client.channel != ctx.author.voice.channel:
          await ctx.channel.send("Dwalen is currently to another channel!")
          return
     voice_client.stop()

@bot.command()
async def pause(ctx):
     voice_client = get(bot.voice_clients, guild=ctx.guild)
     if voice_client == None:
          await ctx.channel.send("Dwalen is not connected to VC!")
          return

     if voice_client.channel != ctx.author.voice.channel:
          await ctx.channel.send("Dwalen is currently to another channel!")
          return
     voice_client.pause()

@bot.command()
async def resume(ctx):
     voice_client = get(bot.voice_clients, guild=ctx.guild)
     if voice_client == None:
          await ctx.channel.send("Dwalen is not connected to VC!")
          return

     if voice_client.channel != ctx.author.voice.channel:
          await ctx.channel.send("Dwalen is currently to another channel!")
          return
     voice_client.resume()
   
@bot.command()
async def leave(ctx):
     channel = ctx.author.voice.channel
     del players[ctx.guild.id]
     await channel.disconnect()

#show help ui
@bot.command()
async def help(ctx):
     emBed = discord.Embed(title="**Commands Lists**", description="All Dwalen Commands!", color=0x0fefff)
     emBed.add_field(name="!play (youtube url)", value="เพื่อเล่นเพลง", inline=False)
     emBed.add_field(name="!stop", value="เพื่อเป็นการหยุดเพลง", inline=False)
     emBed.add_field(name="!pause", value="เพื่อเป็นการหยุดเพลงชั่วคราว", inline=False)
     emBed.add_field(name="!resume", value="เพื่อเป็นการให้เพลงเล่นต่อ", inline=False)
     emBed.add_field(name="!Hello", value="ทักทาย Dwalen", inline=False)
     emBed.add_field(name="!join", value="เพื่อให้บอทเข้าVC", inline=False)
     emBed.add_field(name="!leave", value="เพื่อให้บอทออกจากVC", inline=False)
     emBed.add_field(name="!skip", value="เพื่อข้ามเพลง", inline=False)
     emBed.add_field(name="!queuelist", value="เช็คคิวเพลง", inline=False)

     emBed.set_thumbnail(url='https://playgroundai.com/post/cln0a3so908z2s601mgz2l2zdg')
     emBed.set_footer(text='**Enjoy!!**', icon_url='https://playgroundai.com/post/cln0a3so908z2s601mgz2l2zd')
     await ctx.send(embed=emBed)

#Bot prefix commands
@bot.command()
async def join(ctx):
     channel = ctx.author.voice.channel
     voice_client = get(bot.voice_clients, guild=ctx.guild)

     if voice_client == None:
          ctx.channel.send("Joined")
          await channel.connect()
          voice_client = get(bot.voice_clients, guild=ctx.guild)

@bot.command()
async def Hello(ctx):
      await ctx.channel.send("Hi!!")

@bot.command()
async def queuelist(ctx):
    voice_client = get(bot.voice_clients, guild=ctx.guild)

    if voice_client == None or not voice_client.is_connected():
          await ctx.channel.send("Dwalen is not connected to VC!", delete_after=10)
          return
    
    player = get_player(ctx)
    if player.queue.empty():
        return await ctx.send('There are currently no more queued!')
    
    upcoming = list(itertools.islice(player.queue._queue,0,player.queue.qsize()))
    fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
    embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)
    await ctx.send(embed=embed)

@bot.command()
async def skip(ctx):
   voice_client = get(bot.voice_clients, guild=ctx.guild)

   if voice_client == None or not voice_client.is_connected():
            await ctx.channel.send("Bot is not connected to vc", delete_after=10)
            return

   if voice_client.is_paused():
            pass
   elif not voice_client.is_playing():
            return

   voice_client.stop()
   await ctx.send(f'**`{ctx.author}`**: Skipped the song!')
    

bot.run("your token")

