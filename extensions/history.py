import asyncio
import discord
from discord.ext import commands
import timeit

from db_classes.PGHistoryDB import PGHistoryDB
from models.history_models import HistoryMessage
import logging

logger = logging.getLogger("Referee")


class History(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGHistoryDB()
        self.guild: discord.Guild = None  # initialized in on_ready

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Called by api whenever a message is received.
        """


    async def process_message(self, message: discord.Message):
        if not message.guild:
            return
        if not message.type == discord.MessageType.default:
            return
        if not message.content:
            return

        msg = HistoryMessage(user_id=message.author.id,
                             channel_id=message.channel.id,
                             timestamp=message.created_at,
                             content=message.content)

        await self.db.put_message(msg)


    @commands.command(name="rebase")
    @commands.has_permissions(kick_members=True)
    async def rebase(self, ctx: commands.Context):
        """
        Pulls the entire servers history. RIP.
        """
        if ctx.author.id != 238359385888260096:
            logger.warning(f"{ctx.author} tried to rebase")
            await ctx.send("Ehh. Please discuss this with <@238359385888260096>")
            return
        await ctx.send("This is going to take a while Q_Q", delete_after=30)

        logger.info("Attempting to rebase history")
        for channel in ctx.guild.channels:  # type: discord.TextChannel
            if type(channel) != discord.TextChannel:
                continue
            start = timeit.default_timer()
            async for message in channel.history(oldest_first=True):
                await self.process_message(message)
            dur = timeit.default_timer() - start
            logger.info(f"{channel.name} pulled in {int(dur)}s")


def setup(bot: commands.Bot):
    bot.add_cog(History(bot))
