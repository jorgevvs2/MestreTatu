import discord
from discord.ext import commands


class HelpCog(commands.Cog, name="Ajuda"):
    """Um Cog para gerenciar o comando de ajuda personalizado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cog = self.bot.get_cog('MessageCog')

    @commands.command(name='help', aliases=['ajuda'])
    async def help(self, ctx: commands.Context, *, command_name: str = None):
        """Mostra informações sobre os comandos do bot."""
        if not self.message_cog:
            self.message_cog = self.bot.get_cog('MessageCog')

        # Se nenhum comando específico for solicitado, mostra a ajuda geral
        if command_name is None:
            embed = discord.Embed(
                title="❓ Ajuda - Comandos do TatuBeats",
                description="Aqui estão todos os comandos disponíveis, organizados por categoria. "
                            "Use `.help <comando>` para obter mais detalhes sobre um comando específico.",
                color=discord.Color.purple()
            )

            # Agrupa comandos por Cog
            cogs = {cog_name: cog for cog_name, cog in self.bot.cogs.items() if cog.get_commands()}

            for cog_name, cog in cogs.items():
                # Ignora o próprio Cog de Ajuda na lista
                if cog_name == "Ajuda":
                    continue

                commands_list = [f"`{cmd.name}`" for cmd in cog.get_commands() if not cmd.hidden]
                if commands_list:
                    embed.add_field(name=f"🎶 Comandos de {cog_name}", value=" ".join(commands_list), inline=False)

            embed.set_footer(text="Bot desenvolvido com carinho e código limpo.")
            await ctx.send(embed=embed)

        # Se um comando específico for solicitado, mostra detalhes sobre ele
        else:
            command = self.bot.get_command(command_name.lower())
            if command is None or command.hidden:
                embed = self.message_cog.create_embed(f"O comando `{command_name}` não foi encontrado.", type="error")
                await self.message_cog.send_message(ctx, embed)
                return

            embed = discord.Embed(
                title=f"❓ Ajuda: .{command.name}",
                description=command.help or "Nenhuma descrição disponível.",
                color=discord.Color.purple()
            )

            # Adiciona aliases, se existirem
            if command.aliases:
                aliases = ", ".join([f"`{alias}`" for alias in command.aliases])
                embed.add_field(name="Aliases (atalhos)", value=aliases, inline=False)

            # Adiciona o modo de uso
            usage = f".{command.name} {command.signature}"
            embed.add_field(name="Como Usar", value=f"`{usage}`", inline=False)

            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Função de setup para carregar o Cog."""
    await bot.add_cog(HelpCog(bot))