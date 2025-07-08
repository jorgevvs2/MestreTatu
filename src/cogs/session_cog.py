# src/cogs/session_cog.py

import discord
from discord.ext import commands
import logging
import asyncio
import sqlite3

# Imports dos nossos componentes refatorados
from .session_components.database_setup import DB_FILE, SESSION_DATA_FILE, setup_database
from .session_components.data_manager import SessionDataManager
from .session_components.views import (
    StatsSelectorView,
    SessionStatsSelectorView,
    SessionTrackerView,
    CampaignSelectorView,  # Importa a nova View
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

    # --- Comandos de Gerenciamento de Campanha ---

    @commands.command(name='createcampaign', help='Cria uma nova campanha ou one-shot.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def create_campaign(self, ctx: commands.Context, * name: str ):
        """Cria uma nova campanha para o servidor. Use aspas para nomes com espaços."""
        try:
            self.data_manager.create_campaign(ctx.guild.id, name)
            embed = discord.Embed(
                title="🗺️ Nova Campanha Criada!",
                description=f"A campanha **{name}** foi criada com sucesso.\nUse `.setcampaign` para ativá-la.",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed)
        except sqlite3.IntegrityError:
            await ctx.reply(f"❌ Erro: Uma campanha com o nome '{name}' já existe neste servidor.")
        except Exception as e:
            log.error(f"Erro ao criar campanha: {e}", exc_info=True)
            await ctx.reply("Ocorreu um erro inesperado ao criar a campanha.")

    @commands.command(name='setcampaign', help='Define a campanha ativa para os comandos de estatísticas.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_campaign(self, ctx: commands.Context):
        """Abre um menu para selecionar a campanha ativa do servidor."""
        view = CampaignSelectorView(author=ctx.author, data_manager=self.data_manager)
        if not view.children:
            embed = discord.Embed(
                title="👑 Definir Campanha Ativa",
                description="Nenhuma campanha foi criada neste servidor ainda.\n\nUse o comando `.createcampaign <nome>` para começar.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="👑 Definir Campanha Ativa",
            description="Selecione no menu abaixo qual campanha você quer tornar ativa.",
            color=discord.Color.gold()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    # --- Comandos de Sessão (Agora dependem da campanha ativa) ---

    @commands.command(name='log', help='Abre um menu para registrar eventos da sessão.')
    @commands.guild_only()
    async def log_event(self, ctx: commands.Context):
        """Inicia o menu interativo para registrar estatísticas da sessão."""
        if not self.data_manager.get_active_campaign_id(ctx.guild.id):
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de registrar logs.")
            return

        view = SessionTrackerView(author=ctx.author, bot=self.bot, data_manager=self.data_manager)
        initial_embed = view._create_embed("Selecione o tipo de evento que deseja registrar:")
        message = await ctx.send(embed=initial_embed, view=view)
        view.message = message

    @commands.command(name='stats', aliases=['estatisticas'], help='Mostra as estatísticas de um jogador na campanha ativa.')
    @commands.guild_only()
    async def show_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas de um jogador na campanha ativa."""
        if not self.data_manager.get_active_campaign_id(ctx.guild.id):
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de ver as estatísticas.")
            return

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
            title="📊 Visualizador de Estatísticas da Campanha Ativa",
            description="Selecione um jogador no menu abaixo para ver suas estatísticas.",
            color=discord.Color.gold()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='sessionstats', aliases=['sessao'], help='Mostra as estatísticas de uma sessão da campanha ativa.')
    @commands.guild_only()
    async def show_session_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas de uma sessão da campanha ativa."""
        if not self.data_manager.get_active_campaign_id(ctx.guild.id):
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de ver as estatísticas.")
            return

        view = SessionStatsSelectorView(author=ctx.author, data_manager=self.data_manager)
        if not view.children:
            embed = discord.Embed(
                title="📜 Visualizador de Sessão",
                description="Nenhum dado de sessão foi registrado para a campanha ativa.\n\nUse o comando `.log` para começar.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📜 Visualizador de Sessão da Campanha Ativa",
            description="Selecione uma sessão no menu abaixo para ver seus detalhes e estatísticas.",
            color=discord.Color.purple()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='setsession', help='Define o número da sessão atual para a campanha ativa.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_session(self, ctx: commands.Context, session_number: int):
        """Define o número da sessão atual para a campanha ativa."""
        active_campaign_id = self.data_manager.get_active_campaign_id(ctx.guild.id)
        if not active_campaign_id:
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de mudar a sessão.")
            return
        if session_number <= 0:
            await ctx.reply("O número da sessão deve ser um valor positivo.")
            return

        self.data_manager.set_active_session_num(ctx.guild.id, active_campaign_id, session_number)
        embed = discord.Embed(
            title="⚙️ Sessão da Campanha Atualizada",
            description=f"A sessão ativa para a campanha atual foi definida como **Sessão {session_number}**.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @commands.command(name='mvp', aliases=['destaques'], help='Mostra os destaques da campanha ativa.')
    @commands.guild_only()
    async def show_mvps(self, ctx: commands.Context):
        """Compila estatísticas da campanha ativa e mostra os recordistas."""
        active_campaign_id = self.data_manager.get_active_campaign_id(ctx.guild.id)
        if not active_campaign_id:
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de ver os destaques.")
            return

        async with ctx.typing():
            mvps = self.data_manager.get_mvps(ctx.guild.id)

            if not mvps:
                await ctx.reply("Ainda não há dados suficientes na campanha ativa para determinar os destaques.")
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
                title=f"🏆 Hall da Fama da Campanha Ativa",
                description="Os jogadores que deixaram sua marca nesta aventura!",
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

            embed.set_footer(text="Estes são os recordes totais da campanha ativa.")
            await ctx.send(embed=embed)

    @commands.command(name='endsession', help='Finaliza a sessão atual da campanha ativa com um resumo.')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def end_session(self, ctx: commands.Context, title: str, *, description: str):
        """Salva um resumo da sessão atual no banco de dados para a campanha ativa."""
        active_campaign_id = self.data_manager.get_active_campaign_id(ctx.guild.id)
        if not active_campaign_id:
            await ctx.reply("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de finalizar a sessão.")
            return

        try:
            # O DataManager já sabe qual campanha e sessão estão ativas
            self.data_manager.end_session(ctx.guild.id, title, description)
            session_number = self.data_manager.get_active_session_num(ctx.guild.id, active_campaign_id)

            embed = discord.Embed(
                title=f"✅ Sessão {session_number} da Campanha Ativa Finalizada!",
                description=f"**Título:** {title}\n\n**Resumo:** {description}",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            log.error(f"Erro ao finalizar a sessão no cog: {e}", exc_info=True)
            await ctx.reply("Ocorreu um erro ao tentar salvar o resumo da sessão.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(SessionCog(bot))