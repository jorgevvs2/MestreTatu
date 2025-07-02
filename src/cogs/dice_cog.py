# src/cogs/dice_cog.py
import discord
from discord.ext import commands
import random
import re


class DiceCog(commands.Cog, name="Rolador de Dados"):
    """Um simples mas poderoso rolador de dados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='roll', aliases=['r'], help='Rola dados no formato XdY+Z.')
    async def roll(self, ctx: commands.Context, *, dice_string: str):
        # Regex para capturar rolagens como 1d20, 2d6+5, etc.
        match = re.match(r'(\d+)d(\d+)([\+\-]\d+)?', dice_string.lower().strip())

        if not match:
            await ctx.reply("Formato de rolagem inválido. Use algo como `1d20` ou `2d6+5`.")
            return

        num_dice = int(match.group(1))
        num_sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        if num_dice > 100 or num_sides > 1000:
            await ctx.reply("Calma, campeão! Muitos dados ou lados demais.")
            return

        rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
        total = sum(rolls) + modifier

        # Monta a resposta
        rolls_str = ", ".join(str(r) for r in rolls)
        modifier_str = f" + {modifier}" if modifier > 0 else f" - {abs(modifier)}" if modifier < 0 else ""

        embed = discord.Embed(
            title=f"🎲 Rolagem de {ctx.author.display_name}",
            description=f"**Resultado: {total}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Detalhes", value=f"`{dice_string}` ➔ [{rolls_str}]{modifier_str}")

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DiceCog(bot))
