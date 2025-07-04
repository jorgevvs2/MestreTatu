import discord
from discord.ext import commands
import asyncio
import logging
import os
import sqlite3
import json
from datetime import datetime
from collections import defaultdict

log = logging.getLogger(__name__)

# --- Constantes de Configuração ---
PLAYER_ROLE_NAME = "Aventureiro"

# --- CORREÇÃO: Caminho absoluto e correto para o volume persistente ---
# Todos os dados persistentes devem estar no diretório /data
DB_FILE = '/data/stats.db'
SESSION_DATA_FILE = '/data/session_data.json'


def setup_database():
    """Garante que o banco de dados exista no caminho correto."""
    # O diretório /data é criado e montado pela Fly.io, não precisamos criá-lo.
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Cria a tabela se ela não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                session_number INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                action TEXT NOT NULL,
                amount INTEGER NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        log.info(f"Banco de dados '{DB_FILE}' verificado/criado com sucesso.")
    except Exception as e:
        log.error(f"Falha ao inicializar o banco de dados em '{DB_FILE}': {e}", exc_info=True)

# --- VIEWS (Lógica de UI) ---
# As Views foram adaptadas para chamar os métodos do COG que agora usam o banco de dados.

class StatsSelectorView(discord.ui.View):
    """Uma View para selecionar um jogador e mostrar suas estatísticas totais."""

    def __init__(self, author: discord.Member, cog_instance):
        super().__init__(timeout=180)
        self.author = author
        self.cog = cog_instance
        self.message = None

        players = self.cog._get_players(author.guild)
        if not players:
            return

        options = [discord.SelectOption(label=player.display_name, value=str(player.id)) for player in players]
        player_select_menu = discord.ui.Select(placeholder="Selecione um jogador...", options=options)
        player_select_menu.callback = self.player_select_callback
        self.add_item(player_select_menu)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Apenas quem iniciou o comando pode interagir.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    async def player_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_player_id = self.children[0].values[0]
        player = interaction.guild.get_member(int(selected_player_id))

        if not player:
            await interaction.followup.send("Jogador não encontrado.", ephemeral=True)
            return

        # <-- NOVA LÓGICA: Busca os dados do banco
        stats = self.cog._get_player_total_stats(interaction.guild.id, player.display_name)

        embed = discord.Embed(title=f"Estatísticas Totais de {player.display_name}", color=player.color)
        embed.set_thumbnail(url=player.display_avatar.url)
        embed.add_field(name="⚔️ Dano Causado", value=f"`{stats['causado']}`", inline=True)
        embed.add_field(name="🛡️ Dano Recebido", value=f"`{stats['recebido']}`", inline=True)
        embed.add_field(name="❤️ Cura Realizada", value=f"`{stats['cura']}`", inline=True)
        embed.add_field(name="✨ Acertos Críticos", value=f"`{stats['critico_sucesso']}`", inline=True)
        embed.add_field(name="💥 Falhas Críticas", value=f"`{stats['critico_falha']}`", inline=True)
        embed.add_field(name="💀 Vezes Caído", value=f"`{stats['jogador_caido']}`", inline=True)
        embed.add_field(name="🎯 Eliminações", value=f"`{stats['eliminacao']}`", inline=True)

        await interaction.edit_original_response(embed=embed, view=None)


class SessionStatsSelectorView(discord.ui.View):
    """Uma View para selecionar uma SESSÃO e mostrar suas estatísticas."""

    def __init__(self, author: discord.Member, cog_instance):
        super().__init__(timeout=180)
        self.author = author
        self.cog = cog_instance
        self.message = None

        # <-- NOVA LÓGICA: Busca as sessões do banco
        sessions = self.cog._get_available_sessions(author.guild.id)
        if not sessions:
            return

        options = [discord.SelectOption(label=f"Sessão {s}", value=str(s)) for s in sorted(sessions, reverse=True)]
        session_select_menu = discord.ui.Select(placeholder="Selecione uma sessão...", options=options)
        session_select_menu.callback = self.session_select_callback
        self.add_item(session_select_menu)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Apenas quem iniciou o comando pode interagir.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    async def session_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_session = int(self.children[0].values[0])

        # <-- NOVA LÓGICA: Busca os dados da sessão do banco
        session_stats = self.cog._get_session_stats(interaction.guild.id, selected_session)

        embed = discord.Embed(title=f"Resumo da Sessão {selected_session}", color=discord.Color.purple())
        if not session_stats:
            embed.description = "Nenhum dado encontrado para esta sessão."
            await interaction.edit_original_response(embed=embed, view=None)
            return

        summary_text = ""
        action_names = {
            "causado": "Dano Causado", "recebido": "Dano Recebido", "cura": "Cura",
            "eliminacao": "Abates", "jogador_caido": "Quedas",
            "critico_sucesso": "Críticos (20)", "critico_falha": "Falhas (1)"
        }

        for player, stats in sorted(session_stats.items()):
            summary_text += f"**{player}**\n"
            player_lines = [f"• {friendly_name}: `{stats[action]}`" for action, friendly_name in action_names.items() if
                            stats.get(action, 0) > 0]
            summary_text += "\n".join(player_lines) + "\n\n" if player_lines else "Nenhuma atividade registrada.\n\n"

        embed.description = summary_text
        await interaction.edit_original_response(embed=embed, view=None)


class SessionTrackerView(discord.ui.View):
    """Uma View interativa para registrar eventos de sessão."""

    def __init__(self, author: discord.Member, bot: commands.Bot):
        super().__init__(timeout=180)
        self.author = author
        self.bot = bot
        self.action_type = None
        self.player_select_menu = None
        self.message = None

    def _create_embed(self, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        return discord.Embed(title="Registro de Evento de Sessão", description=description, color=color)

    async def on_timeout(self):
        if self.message:
            timeout_embed = self._create_embed("Este menu de registro de evento expirou.", color=discord.Color.orange())
            await self.message.edit(embed=timeout_embed, view=None)

    def _get_players(self, guild: discord.Guild) -> list[discord.Member]:
        player_role = discord.utils.find(lambda r: r.name.lower() == PLAYER_ROLE_NAME.lower(), guild.roles)
        if not player_role:
            return []
        return [member for member in guild.members if player_role in member.roles and not member.bot]

    def _disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def _prompt_for_player(self, interaction: discord.Interaction, prompt_text: str):
        players = self._get_players(interaction.guild)
        if not players:
            error_embed = self._create_embed(
                f"Não encontrei nenhum membro com o cargo '{PLAYER_ROLE_NAME}'. Crie o cargo e atribua-o aos jogadores.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
            self.stop()
            return

        options = [discord.SelectOption(label=player.display_name, value=str(player.id)) for player in players]
        self.player_select_menu = discord.ui.Select(placeholder="Selecione o jogador...", options=options)

        if self.action_type in ["causado", "recebido", "cura"]:
            self.player_select_menu.callback = self.player_select_amount_callback
        else:
            self.player_select_menu.callback = self.player_select_event_callback

        self.add_item(self.player_select_menu)
        embed = self._create_embed(prompt_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Dano Causado", style=discord.ButtonStyle.green, row=0)
    async def damage_dealt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "causado"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **causado**. Agora, selecione o jogador:")

    @discord.ui.button(label="Dano Recebido", style=discord.ButtonStyle.red, row=0)
    async def damage_taken_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "recebido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **recebido**. Agora, selecione o jogador:")

    @discord.ui.button(label="Cura Realizada", style=discord.ButtonStyle.primary, row=0)
    async def healing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "cura"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Cura **realizada**. Agora, selecione o jogador:")

    @discord.ui.button(label="Crítico (Sucesso)", style=discord.ButtonStyle.success, row=1)
    async def crit_success_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_sucesso"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um **sucesso crítico**! Selecione o jogador:")

    @discord.ui.button(label="Crítico (Falha)", style=discord.ButtonStyle.danger, row=1)
    async def crit_fail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_falha"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Uma **falha crítica**! Selecione o jogador:")

    @discord.ui.button(label="Jogador Caído", style=discord.ButtonStyle.secondary, row=2)
    async def player_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "jogador_caido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um jogador **caiu em combate** (HP 0). Selecione o jogador:")

    @discord.ui.button(label="Eliminação", style=discord.ButtonStyle.secondary, row=2)
    async def elimination_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "eliminacao"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um inimigo foi **eliminado**. Selecione o jogador responsável:")

    async def player_select_amount_callback(self, interaction: discord.Interaction):
        self.player_select_menu.disabled = True
        player_id = int(self.player_select_menu.values[0])
        player = interaction.guild.get_member(player_id)

        prompt_message = f"Qual foi o valor de **{self.action_type}** para **{player.display_name}**? Digite apenas o número."
        embed = self._create_embed(prompt_message)
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            message = await self.bot.wait_for(
                "message", timeout=60.0,
                check=lambda
                    m: m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. O registro foi cancelado.", ephemeral=True)
            self.stop()
            return

        amount = int(message.content)
        self.bot.get_cog("Estatísticas de Sessão")._log_event(interaction.guild.id, player, self.action_type, amount)

        final_message = f"✅ Registrado: **{player.display_name}** - **{self.action_type.replace('_', ' ').title()}** - **{amount}**."
        final_embed = self._create_embed(final_message, color=discord.Color.green())
        await interaction.edit_original_response(embed=final_embed, view=None)

        try:
            await message.delete()
        except discord.HTTPException:
            pass
        self.stop()

    async def player_select_event_callback(self, interaction: discord.Interaction):
        self.player_select_menu.disabled = True
        player_id = int(self.player_select_menu.values[0])
        player = interaction.guild.get_member(player_id)

        self.bot.get_cog("Estatísticas de Sessão")._log_event(interaction.guild.id, player, self.action_type, 1)

        event_text = self.action_type.replace('_', ' ').title()
        final_message = f"✅ Registrado: **{player.display_name}** - **{event_text}**."
        final_embed = self._create_embed(final_message, color=discord.Color.green())
        await interaction.edit_original_response(embed=final_embed, view=None)
        self.stop()


# --- COG PRINCIPAL ---

class SessionCog(commands.Cog, name="Estatísticas de Sessão"):
    """Cog para registrar e visualizar estatísticas de sessão de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_data = self._load_session_data()
        setup_database()

    # --- Métodos de Gerenciamento de Dados (JSON para sessão ativa) ---
    def _load_session_data(self) -> dict:
        try:
            with open(SESSION_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_session_data(self):
        try:
            with open(SESSION_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=4)
        except IOError as e:
            log.error(f"Falha ao salvar os dados da sessão: {e}")

    # --- Métodos de Interação com o Banco de Dados (SQLite) ---
    def _log_event(self, guild_id: int, player: discord.Member, action: str, amount: int):
        """Registra um evento no banco de dados SQLite."""
        timestamp = datetime.utcnow().isoformat()
        session_number = self.session_data.get(str(guild_id), 1)

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_stats (timestamp, guild_id, session_number, player_name, action, amount) VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, str(guild_id), session_number, player.display_name, action, amount)
            )
            conn.commit()
            conn.close()
            log.info(f"Estatística registrada para {player.display_name}: {action} - {amount}")
        except Exception as e:
            log.error(f"Falha ao escrever no banco de dados: {e}", exc_info=True)

    def _get_player_total_stats(self, guild_id: int, player_name: str) -> defaultdict:
        """Busca as estatísticas totais de um jogador no banco de dados."""
        stats = defaultdict(int)
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, SUM(amount) FROM session_stats WHERE guild_id = ? AND player_name = ? GROUP BY action",
                (str(guild_id), player_name)
            )
            for action, total_amount in cursor.fetchall():
                stats[action] = total_amount
            conn.close()
        except Exception as e:
            log.error(f"Erro ao buscar estatísticas de {player_name}: {e}", exc_info=True)
        return stats

    def _get_available_sessions(self, guild_id: int) -> list[int]:
        """Retorna uma lista de números de sessão únicos do banco de dados."""
        sessions = []
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT session_number FROM session_stats WHERE guild_id = ?", (str(guild_id),))
            sessions = [row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            log.error(f"Erro ao buscar sessões disponíveis: {e}", exc_info=True)
        return sessions

    def _get_session_stats(self, guild_id: int, session_number: int) -> defaultdict:
        """Busca as estatísticas de uma sessão específica do banco de dados."""
        session_stats = defaultdict(lambda: defaultdict(int))
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT player_name, action, SUM(amount) FROM session_stats WHERE guild_id = ? AND session_number = ? GROUP BY player_name, action",
                (str(guild_id), session_number)
            )
            for player_name, action, total_amount in cursor.fetchall():
                session_stats[player_name][action] = total_amount
            conn.close()
        except Exception as e:
            log.error(f"Erro ao buscar estatísticas da sessão {session_number}: {e}", exc_info=True)
        return session_stats

    def _get_players(self, guild: discord.Guild) -> list[discord.Member]:
        """Helper para pegar membros com o cargo de jogador."""
        player_role = discord.utils.find(lambda r: r.name.lower() == PLAYER_ROLE_NAME.lower(), guild.roles)
        return [m for m in guild.members if player_role and player_role in m.roles and not m.bot] if player_role else []

    # --- Comandos do Bot ---
    @commands.command(name='log', help='Abre um menu para registrar eventos da sessão.')
    @commands.guild_only()
    async def log_event(self, ctx: commands.Context):
        """Inicia o menu interativo para registrar estatísticas da sessão."""
        view = SessionTrackerView(author=ctx.author, bot=self.bot)
        initial_embed = view._create_embed("Selecione o tipo de evento que deseja registrar:")
        message = await ctx.send(embed=initial_embed, view=view)
        view.message = message

    @commands.command(name='stats', aliases=['estatisticas'], help='Mostra as estatísticas totais de um jogador.')
    @commands.guild_only()
    async def show_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas totais de um jogador."""
        view = StatsSelectorView(author=ctx.author, cog_instance=self)
        if not view.children:
            embed = discord.Embed(
                title="Visualizador de Estatísticas",
                description=f"Não encontrei nenhum membro com o cargo '{PLAYER_ROLE_NAME}'.\nCrie o cargo e atribua-o aos jogadores para usar este comando.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="Visualizador de Estatísticas",
            description="Selecione um jogador no menu abaixo para ver suas estatísticas totais.",
            color=discord.Color.gold()
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='sessionstats', aliases=['sessao'], help='Mostra as estatísticas de uma sessão específica.')
    @commands.guild_only()
    async def show_session_stats(self, ctx: commands.Context):
        """Inicia um menu para visualizar as estatísticas de uma sessão específica."""
        view = SessionStatsSelectorView(author=ctx.author, cog_instance=self)
        if not view.children:
            embed = discord.Embed(
                title="Visualizador de Estatísticas de Sessão",
                description="Nenhum dado de sessão foi registrado neste servidor ainda. Use o comando `.log` para começar.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="Visualizador de Estatísticas de Sessão",
            description="Selecione uma sessão no menu abaixo para ver seus detalhes.",
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

        guild_id = str(ctx.guild.id)
        self.session_data[guild_id] = session_number
        self._save_session_data()

        embed = discord.Embed(
            title="Sessão Atualizada",
            description=f"A sessão ativa para registro de eventos foi definida como **Sessão {session_number}**.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @commands.command(name='mvp', aliases=['destaques'], help='Mostra os jogadores destaque da campanha.')
    @commands.guild_only()
    async def show_mvps(self, ctx: commands.Context):
        """Compila estatísticas do banco de dados e mostra os recordistas."""
        async with ctx.typing():
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()

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

                found_any_mvp = False
                for action, (title, desc) in action_map.items():
                    cursor.execute("""
                        SELECT player_name, SUM(amount) as total
                        FROM session_stats
                        WHERE guild_id = ? AND action = ?
                        GROUP BY player_name
                        ORDER BY total DESC
                        LIMIT 1
                    """, (str(ctx.guild.id), action))

                    result = cursor.fetchone()
                    if result and result[1] > 0:
                        player, value = result
                        embed.add_field(name=title, value=f"**{player}** com um total de `{value}`\n*({desc})*",
                                        inline=False)
                        found_any_mvp = True
                    else:
                        embed.add_field(name=title, value=f"Ninguém se destacou ainda.\n*({desc})*", inline=False)

                conn.close()

                if not found_any_mvp:
                    await ctx.reply("Ainda não há dados suficientes neste servidor para determinar os MVPs.")
                    return

                embed.set_footer(text="Estes são os recordes totais de todas as sessões.")
                await ctx.send(embed=embed)

            except Exception as e:
                log.error(f"Erro ao gerar MVPs: {e}", exc_info=True)
                await ctx.reply("Ocorreu um erro ao consultar o Hall da Fama.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(SessionCog(bot))