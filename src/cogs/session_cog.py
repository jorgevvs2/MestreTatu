# src/cogs/session_cog.py

import discord
from discord.ext import commands
import logging
import asyncio

# Imports dos nossos componentes refatorados
from .session_components.database_setup import DB_FILE, SESSION_DATA_FILE, setup_database
from .session_components.data_manager import SessionDataManager
from .session_components.views import (
    StatsSelectorView,
    SessionStatsSelectorView,
    SessionTrackerView,
    get_players,
    PLAYER_ROLE_NAME
)

log = logging.getLogger(__name__)

class SessionCog(commands.Cog, name="Estatísticas de Sessão"):
    """Cog para registrar e visualizar estatísticas de sessão de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Garante que o banco de dados e os diretórios estão prontos
        setup_database()
        # Instancia o gerenciador de dados, que será nossa única fonte de verdade
        self.data_manager = SessionDataManager(db_path=DB_FILE, session_file_path=SESSION_DATA_FILE)

    # --- Comandos do Bot (agora muito mais limpos) ---

    @commands.command(name='log', help='Abre um menu para registrar eventos da sessão.')
    @commands.guild_only()
    async def log_event(self, ctx: commands.Context):
        """Inicia o menu interativo para registrar estatísticas da sessão."""
        view = SessionTrackerView(author=ctx.author, bot=self.bot, data_manager=self.data_manager)
        initial_embed = view._create_embed("Selecione o tipo de evento que deseja registrar:")
        message = await ctx.send(embed=initial_embed, view=view)
        view.message = message

    @commands.command(name='stats', aliases=['estatisticas'], help='Mostra as estatísticas totais de um jogador.')
    @commands.guild_only()
    async def show_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas totais de um jogador."""
        view = StatsSelectorView(author=ctx.author, data_manager=self.data_manager)
        if not view.children:
            embed = discord.Embed(
                title="📊 Visualizador de Estatísticas",
                description=f"Não encontrei nenhum membro com o cargo **'{PLAYER_ROLE_NAME}'**.\n\nCrie o cargo e atribua-o aos jogadores para usar este comando.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📊 Visualizador de Estatísticas",
            description="Selecione um jogador no menu abaixo para ver suas estatísticas totais.",
            color=discord.Color.gold()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='sessionstats', aliases=['sessao'], help='Mostra as estatísticas de uma sessão específica.')
    @commands.guild_only()
    async def show_session_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas de uma sessão específica."""
        view = SessionStatsSelectorView(author=ctx.author, data_manager=self.data_manager)
        if not view.children:
            embed = discord.Embed(
                title="📜 Visualizador de Sessão",
                description="Nenhum dado de sessão foi registrado neste servidor ainda.\n\nUse o comando `.log` para começar.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📜 Visualizador de Sessão",
            description="Selecione uma sessão no menu abaixo para ver seus detalhes e estatísticas.",
            color=discord.Color.purple()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='setsession', help='Define o número da sessão atual para registro.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_session(self, ctx: commands.Context, session_number: int):
        """Define o número da sessão atual para este servidor."""
        if session_number <= 0:
            await ctx.reply("O número da sessão deve ser um valor positivo.")
            return

        self.data_manager.set_active_session(ctx.guild.id, session_number)

        embed = discord.Embed(
            title="⚙️ Sessão Atualizada",
            description=f"A sessão ativa para registro de eventos foi definida como **Sessão {session_number}**.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @commands.command(name='mvp', aliases=['destaques'], help='Mostra os jogadores destaque da campanha.')
    @commands.guild_only()
    async def show_mvps(self, ctx: commands.Context):
        """Compila estatísticas do banco de dados e mostra os recordistas."""
        async with ctx.typing():
            mvps = self.data_manager.get_mvps(ctx.guild.id)

            if not mvps:
                await ctx.reply("Ainda não há dados suficientes neste servidor para determinar os destaques.")
                return

            action_map = {
                "causado": ("⚔️ Mão Pesada", "Maior Dano Causado"),
                "recebido": ("🛡️ Muralha de Carne", "Maior Dano Recebido"),
                "cura": ("❤️ Fonte de Vida", "Maior Cura Realizada"),
                "eliminacao": ("🎯 O Carrasco", "Mais Eliminações"),
                "jogador_caido": ("💀 Saco de Pancada", "Mais Vezes Caído"),
                "critico_sucesso": ("✨ O Sortudo", "Mais Acertos Críticos (20)"),
                "critico_falha": ("💥 O Azarado", "Mais Falhas Críticas (1)"),
            }

            embed = discord.Embed(
                title=f"🏆 Hall da Fama de {ctx.guild.name}",
                description="Os jogadores que deixaram sua marca na campanha!",
                color=discord.Color.gold()
            )

            for action, (title, desc) in action_map.items():
                if action in mvps:
                    player_names, top_score = mvps[action]
                    player_list = ", ".join(f"**{name}**" for name in player_names)
                    embed.add_field(
                        name=title,
                        value=f"{player_list} com um total de `{top_score}`\n*({desc})*",
                        inline=False
                    )
                else:
                    embed.add_field(name=title, value=f"Ninguém se destacou ainda.\n*({desc})*", inline=False)

            embed.set_footer(text="Estes são os recordes totais de todas as sessões.")
            await ctx.send(embed=embed)

    @commands.command(name='endsession', help='Finaliza a sessão atual com um título e descrição.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def end_session(self, ctx: commands.Context, title: str, *, description: str):
        """
        Salva um resumo da sessão atual no banco de dados.
        Use aspas para títulos com espaços. Ex: .endsession "O Resgate do Ferreiro" O grupo...
        """
        session_number = self.data_manager.get_active_session(ctx.guild.id)

        try:
            self.data_manager.end_session(ctx.guild.id, session_number, title, description)
            embed = discord.Embed(
                title=f"✅ Sessão {session_number} Finalizada com Sucesso!",
                description=f"**Título:** {title}\n\n**Resumo:** {description}",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            log.error(f"Erro ao finalizar a sessão {session_number} no cog: {e}", exc_info=True)
            await ctx.reply("Ocorreu um erro ao tentar salvar o resumo da sessão.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(SessionCog(bot))