import discord
from discord.ext import commands
import random
import re
from typing import Dict, Any


class DiceCog(commands.Cog, name="Rolador de Dados"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _parse_and_roll(self, expression: str) -> Dict[str, Any]:

        match = re.match(r'(\d+)?d(\d+)((?:[kd][hl])?\d+)?([+-]\d+)?', expression, re.IGNORECASE)

        if not match:
            raise ValueError("Formato de rolagem inválido. Use algo como `2d6`, `d20+5` ou `4d6kh3`.")

        num_dice_str, num_sides_str, keep_drop_str, modifier_str = match.groups()

        num_dice = int(num_dice_str) if num_dice_str else 1
        num_sides = int(num_sides_str)
        modifier = int(modifier_str) if modifier_str else 0

        if num_dice <= 0 or num_sides <= 0 or num_dice > 100:
            raise ValueError("Número de dados ou lados inválido. Use valores positivos e no máximo 100 dados.")

        all_rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
        rolls_to_sum = list(all_rolls)
        dropped_rolls = []

        if keep_drop_str:
            kd_match = re.match(r'([kd])([hl])?(\d+)', keep_drop_str, re.IGNORECASE)
            if kd_match:
                mode, high_low, count_str = kd_match.groups()
                count = int(count_str)

                if count >= num_dice:
                    raise ValueError("Não é possível manter/descartar mais dados do que o total rolado.")

                sorted_rolls = sorted(rolls_to_sum)

                if mode.lower() == 'k':
                    if high_low and high_low.lower() == 'l':
                        rolls_to_sum = sorted_rolls[:count]
                        dropped_rolls = sorted_rolls[count:]
                    else:
                        rolls_to_sum = sorted_rolls[-count:]
                        dropped_rolls = sorted_rolls[:-count]

                elif mode.lower() == 'd':
                    if high_low and high_low.lower() == 'h':
                        rolls_to_sum = sorted_rolls[:-count]
                        dropped_rolls = sorted_rolls[-count:]
                    else:
                        rolls_to_sum = sorted_rolls[count:]
                        dropped_rolls = sorted_rolls[:count]

        total = sum(rolls_to_sum) + modifier
        return {
            "total": total,
            "initial_rolls": all_rolls,
            "final_rolls": rolls_to_sum,
            "dropped_rolls": dropped_rolls,
            "modifier": modifier
        }

    @commands.command(name='roll', aliases=['r'],
                      help='Rola dados usando a notação de RPG (ex: 2d6, d20+5, 4d6kh3, adv).')
    async def roll(self, ctx: commands.Context, *, expression: str):
        expression = expression.lower().strip().replace(" ", "")

        # Casos especiais: Vantagem e Desvantagem
        if expression in ['adv', 'advantage']:
            expression = '2d20kh1'

        if expression in ['dis', 'disadvantage']:
            expression = '2d20kl1'

        # Caso geral
        try:
            roll_data = self._parse_and_roll(expression)

            embed = discord.Embed(
                title="🎲 Rolagem de Dados",
                description=f"Resultado para `{expression}`: **{roll_data['total']}**",
                color=discord.Color.blue()
            )

            rolls_str = " + ".join(map(str, roll_data['final_rolls']))
            modifier_str = f" {roll_data['modifier']:+}" if roll_data['modifier'] != 0 else ""
            calculation = f"Soma: ({rolls_str}){modifier_str} = {roll_data['total']}"

            embed.add_field(name="Rolagens Iniciais", value=f"`{roll_data['initial_rolls']}`", inline=False)
            if roll_data['dropped_rolls']:
                embed.add_field(name="Dados Descartados", value=f"`{sorted(roll_data['dropped_rolls'])}`", inline=True)

            embed.add_field(name="Cálculo", value=calculation, inline=False)
            embed.set_footer(text=f"Rolado por {ctx.author.display_name}")

            await ctx.reply(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Erro na Rolagem",
                description=str(e),
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DiceCog(bot))