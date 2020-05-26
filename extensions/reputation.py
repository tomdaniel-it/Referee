import logging

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB
from config import reputation_config

from utils import emoji

from datetime import datetime, date, timedelta

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("Referee")


class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGReputationDB()
        self.guild = None


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]
        self.self_thank_emoji = discord.utils.get(self.guild.emojis, name="cmonBruh")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if message.content.lower().startswith("thank"):
                members = message.mentions
                logger.info(f"Recieved thanks from {message.author} to {', '.join(str(m) for m in members)}")
                last_given_diff = await self.db.get_time_between_lg_now(message.author.id)
                if last_given_diff:
                    if last_given_diff <= reputation_config.RepDelay:
                        await message.add_reaction(emoji.hourglass)
                        logger.debug("Cooldown active, returning")
                        return

                if len(members) > reputation_config.max_mentions:
                    await message.channel.send(
                        f"Maximum number of simultaneous thanks is {reputation_config.max_mentions}. Try again with less mentions.",
                        delete_after=10
                    )
                elif not members:
                    await message.channel.send(
                        f"Say \"Thanks @HelpfulUser @OtherHelpfulUser @AnotherHelpfulUser\" to award up to {reputation_config.max_mentions} people with a point on the support scoreboard!",
                        delete_after=10
                    )
                else:
                    for member in members:
                        if member.bot:
                            logger.debug(f"Thanking {member} canceled: User is bot")
                            await message.add_reaction(emoji.robot)
                        elif member == message.author and not reputation_config.Debug:
                            logger.debug(f"Thanking {member} canceled: User thanking themselves")
                            await message.add_reaction(self.self_thank_emoji)
                        else:
                            await self.db.thank(message.author.id, member.id, message.channel.id)
                            await message.add_reaction(emoji.thumbs_up)


    @commands.command(name="rep", aliases=["get_rep", "score", "thanks"])
    async def get_rep(self, ctx: commands.Context, member: discord.Member = None):
        if not member:
            member = ctx.author
        leaderboard = await self.db.get_leaderboard()

        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(x["current_rep"] for x in leaderboard), reverse=True))}

        rep = await self.db.get_user_rep(member.id)
        embed = discord.Embed(title="Support Score", color=discord.Color.dark_gold())
        embed.add_field(name=f"{member.name}:",
                        value=f"{rep} (Rank #{ranks.get(rep, len(ranks) + 1)})",
                        inline=True)
        await ctx.send(embed=embed)


    @commands.group(name="leaderboard", aliases=["scoreboard"])
    async def leaderboard(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.trigger_typing()
            leaderboard = await self.db.get_leaderboard()
            ranks = {score: i + 1 for i, score in
                     enumerate(sorted(set(x["current_rep"] for x in leaderboard), reverse=True))}

            embed = discord.Embed(title="Scoreboard", color=discord.Color.dark_gold())
     #       embed.add_field(
     #           name="Highest Support Scores:",
     #           value="\n".join(
     #               "{}: {}#{}: {}".format(
     #                   str(ranks.get(x["current_rep"])).zfill(len(str(reputation_config.Leader_Limit))),
     #                   self.bot.get_user(x['user_id']).name,
     #                   self.bot.get_user(x['user_id']).discriminator, x['current_rep']
     #               )
     #               for x in leaderboard if x["current_rep"] > 0))
            scores = [(ranks.get(x["current_rep"]), self.bot.get_user(x['user_id']), x['current_rep']) for x in
                      leaderboard]
            await draw_scoreboard(scores)

            await ctx.send(file=discord.File("scoreboard.png"))


    @leaderboard.command()
    async def month(self, ctx: commands.Context, month_number: int = date.today().month):

        month_name = datetime.strptime(str(month_number), "%m").strftime("%B")

        since = date(date.today().year, month_number, 1)
        until = since + timedelta(days=30)

        member_scores = {}
        for res in await self.db.get_thanks_timeframe(since, until):
            member_scores[res["target_user"]] = member_scores.get(res["target_user"], 0) + 1

        leaderboard = sorted(member_scores, key=member_scores.get, reverse=True)
        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(member_scores.values()), reverse=True))}

        if not leaderboard:
            embed = discord.Embed(title=f"No entries for {month_name}", color=discord.Color.dark_gold())
        else:
            embed = discord.Embed(title="Scoreboard", color=discord.Color.dark_gold())
            i = 0
            embed.add_field(
                name=f"Highest Support Scores for {month_name}:",
                value="\n".join(
                    "{}: {}#{}: {}".format(
                        str(ranks.get(member_scores.get(user_id))).zfill(len(str(reputation_config.Leader_Limit))),
                        self.bot.get_user(user_id).name,
                        self.bot.get_user(user_id).discriminator, member_scores.get(user_id)
                    )
                    for user_id in leaderboard if member_scores.get(user_id) > 0))
        await ctx.send(embed=embed)


    @leaderboard.command()
    async def week(self, ctx: commands.Context):

        until = date.today() + timedelta(days=1)
        since = until - timedelta(days=8)

        member_scores = {}
        for res in await self.db.get_thanks_timeframe(since, until):
            member_scores[res["target_user"]] = member_scores.get(res["target_user"], 0) + 1

        leaderboard = sorted(member_scores, key=member_scores.get, reverse=True)
        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(member_scores.values()), reverse=True))}

        embed = discord.Embed(title="Scoreboard", color=discord.Color.dark_gold())
        i = 0
        embed.add_field(
            name=f"Highest Support Scores for previous 7 days:",
            value="\n".join(
                "{}: {}#{}: {}".format(
                    str(ranks.get(member_scores.get(user_id))).zfill(len(str(reputation_config.Leader_Limit))),
                    self.bot.get_user(user_id).name,
                    self.bot.get_user(user_id).discriminator, member_scores.get(user_id)
                )
                for user_id in leaderboard if member_scores.get(user_id) > 0))
        await ctx.send(embed=embed)


async def draw_scoreboard(scores: list):
    width = 512
    row_height = reputation_config.fontsize + reputation_config.fontsize // 2
    height = (len(scores) + 1) * row_height

    bg = Image.new("RGB", (width, height), reputation_config.background).convert("RGBA")
    text = Image.new("RGBA", bg.size, (255, 255, 255, 0))
    pics = Image.new("RGBA", bg.size, (255, 255, 255, 0))
    fnt = ImageFont.truetype('coolvetica.ttf', reputation_config.fontsize)
    big_fnt = ImageFont.truetype('coolvetica.ttf', int(reputation_config.fontsize*1.5))
    text_draw = ImageDraw.Draw(text)

    avatar_size = int(reputation_config.fontsize * 1.3)
    avatar_x = avatar_size // 2

    rank_x = 2 * avatar_size
    name_x = 2 * avatar_size
    point_x = width - reputation_config.fontsize

    line_x = name_x
    max_line_width = (point_x-name_x)

    for i, (rank, member, points) in enumerate(scores):
        row_y = i * row_height + (reputation_config.fontsize // 2)
        row_color = reputation_config.fontcolors.get(rank, reputation_config.default_fontcolor)
    #    text_draw.text((rank_x, row_y), f"{rank}.", font=fnt,
    #                   fill=row_color)
        text_draw.text((name_x, row_y), f"{member.display_name}", font=fnt,
                       fill=row_color)
        w, h = text_draw.textsize(f"{points}", font=fnt)
        text_draw.text((point_x-w, row_y), f"{points}", font=fnt,
                       fill=row_color)
        text_draw.line([line_x, row_y+int(avatar_size), line_x + int(max_line_width * points / scores[0][2]),
                        row_y+int(avatar_size)], fill=row_color, width=2)

        await member.avatar_url_as(format="png", size=256).save("temp.png")
        avatar = Image.open("temp.png").resize((avatar_size, avatar_size))
        txt = Image.new('RGBA', avatar.size, (255, 255, 255, 0))

        box = (
            avatar_x,
            row_y,
            avatar_x + avatar_size,
            row_y + avatar_size
        )
        d = ImageDraw.Draw(txt)
        w, h = d.textsize(f"{rank}", font=fnt)
        d.text(((avatar_size-w)//2, (avatar_size-h)//2), f"{rank}",
               font=fnt, fill=(255, 255, 255, 50), stroke_fill=(0, 0, 0, 120), stroke_width=1)
        pics.paste(avatar, box)
        #pics.paste(txt, box)

    out = Image.alpha_composite(Image.alpha_composite(bg, text), pics)
    out.save("scoreboard.png")
    return out


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
