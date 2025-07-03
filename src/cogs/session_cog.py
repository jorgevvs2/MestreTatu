import discord
from discord.ext import commands
import asyncio
import logging
import os
import csv
import json
from datetime import datetime
from collections import defaultdict

# Tenta importar a função específica do gerador de gráficos.
try:
    from utils.graph_generator import generate_session_graphs

    GRAPHING_ENABLED = True
except ImportError:
    GRAPHING_ENABLED = False
    logging.getLogger(__name__).warning(
        "Módulo 'graph_generator' ou suas dependências não encontrados. A geração de gráficos está desativada.")

# --- Constantes de Configuração ---
PLAYER_ROLE_NAME = "Aventureiro"
LOGS_DIR = "src/logs"
STATS_LOG_FILE = os.path.join(LOGS_DIR, "rpg_session_stats.csv")
SESSION_DATA_FILE = os.path.join(LOGS_DIR, "session_data.json")

log = logging.getLogger(__name__)


def setup_log_file():
    """Garante que o diretório e o arquivo de log CSV existam."""
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        log.info(f"Diretório de logs '{LOGS_DIR}' criado.")

    if not os.path.exists(STATS_LOG_FILE):
        with open(STATS_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # --- ALTERAÇÃO AQUI: Removida a coluna 'player_id' ---
            writer.writerow(['timestamp', 'guild_id', 'session_number', 'player_name', 'action', 'amount'])
        log.info(f"Arquivo de log de estatísticas criado em '{STATS_LOG_FILE}'.")


# --- VIEW PARA MOSTRAR ESTATÍSTICAS GERAIS DE UM JOGADOR ---

class StatsSelectorView(discord.ui.View):
    """Uma View para selecionar um jogador e mostrar suas estatísticas totais."""

    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)  # Timeout de 3 minutos
        self.author = author
        self.message = None

        players = self._get_players(author.guild)
        if not players:
            return

        options = [discord.SelectOption(label=player.display_name, value=str(player.id)) for player in players]
        player_select_menu = discord.ui.Select(placeholder="Selecione um jogador para ver as estatísticas...",
                                               options=options)
        player_select_menu.callback = self.player_select_callback
        self.add_item(player_select_menu)

    def _get_players(self, guild: discord.Guild) -> list[discord.Member]:
        player_role = discord.utils.find(lambda r: r.name.lower() == PLAYER_ROLE_NAME.lower(), guild.roles)
        if not player_role:
            return []
        return [member for member in guild.members if player_role in member.roles and not member.bot]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Apenas quem iniciou o comando pode interagir com ele.",
                                                    ephemeral=True)
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

        stats = defaultdict(int)
        try:
            with open(STATS_LOG_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # --- ALTERAÇÃO AQUI: Busca por nome em vez de ID ---
                    if row['guild_id'] == str(interaction.guild.id) and row['player_name'] == player.display_name:
                        stats[row['action']] += int(row['amount'])
        except FileNotFoundError:
            pass
        except Exception as e:
            log.error(f"Erro ao ler o arquivo de estatísticas: {e}")
            await interaction.followup.send("Ocorreu um erro ao ler as estatísticas.", ephemeral=True)
            return

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


# --- VIEW PARA MOSTRAR ESTATÍSTICAS DE UMA SESSÃO ---
# (Esta classe não precisa de alterações, pois já funciona com os dados da linha inteira)
class SessionStatsSelectorView(discord.ui.View):
    """Uma View para selecionar uma SESSÃO e mostrar suas estatísticas."""

    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)  # Timeout de 3 minutos
        self.author = author
        self.message = None

        sessions = self._get_available_sessions(author.guild.id)
        if not sessions:
            return

        options = [discord.SelectOption(label=f"Sessão {s}", value=str(s)) for s in sorted(sessions, reverse=True)]
        session_select_menu = discord.ui.Select(placeholder="Selecione uma sessão para ver os detalhes...",
                                                options=options)
        session_select_menu.callback = self.session_select_callback
        self.add_item(session_select_menu)

    def _get_available_sessions(self, guild_id: int) -> set:
        sessions = set()
        try:
            with open(STATS_LOG_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['guild_id'] == str(guild_id):
                        sessions.add(int(row['session_number']))
        except FileNotFoundError:
            pass
        return sessions

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Apenas quem iniciou o comando pode interagir com ele.",
                                                    ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    async def session_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_session = self.children[0].values[0]
        session_rows_for_graph = []

        try:
            with open(STATS_LOG_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('guild_id') == str(interaction.guild.id) and row.get(
                            'session_number') == selected_session:
                        session_rows_for_graph.append(row)
        except FileNotFoundError:
            await interaction.followup.send("Arquivo de estatísticas não encontrado.", ephemeral=True)
            return
        except Exception as e:
            log.error(f"Erro ao ler o arquivo de estatísticas para a sessão {selected_session}: {e}", exc_info=True)
            await interaction.followup.send("Ocorreu um erro ao ler as estatísticas.", ephemeral=True)
            return

        graph_filepath = None
        graph_file = None
        if GRAPHING_ENABLED and session_rows_for_graph:
            try:
                loop = asyncio.get_running_loop()
                graph_filepath = await loop.run_in_executor(
                    None, generate_session_graphs, session_rows_for_graph, int(selected_session)
                )
                if graph_filepath:
                    graph_file = discord.File(graph_filepath, filename=os.path.basename(graph_filepath))
            except Exception as e:
                log.error(f"Falha ao gerar o gráfico para a sessão {selected_session}: {e}", exc_info=True)

        embed = discord.Embed(title=f"Estatísticas da Sessão {selected_session}", color=discord.Color.purple())
        if graph_file:
            embed.set_image(url=f"attachment://{graph_file.filename}")
            await interaction.edit_original_response(embed=embed, attachments=[graph_file], view=None)
            if graph_filepath and os.path.exists(graph_filepath):
                os.remove(graph_filepath)
        else:
            embed.description = "Não foi possível gerar um gráfico para esta sessão (sem dados ou a biblioteca de gráficos está desativada)."
            await interaction.edit_original_response(embed=embed, view=None)


# --- VIEW PARA REGISTRAR EVENTOS ---
# (Esta classe não precisa de alterações, pois a lógica de salvar já foi alterada no _log_event)
class SessionTrackerView(discord.ui.View):
    """Uma View interativa para registrar eventos de sessão."""

    def __init__(self, author: discord.Member, bot: commands.Bot):
        super().__init__(timeout=180)  # Timeout de 3 minutos
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
        await interaction.response.edit_message(embed=final_embed, view=None)
        self.stop()


class SessionCog(commands.Cog, name="Estatísticas de Sessão"):
    """Cog para registrar e visualizar estatísticas de sessão de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_data = self._load_session_data()
        setup_log_file()

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

    def _log_event(self, guild_id: int, player: discord.Member, action: str, amount: int):
        timestamp = datetime.utcnow().isoformat()
        session_number = self.session_data.get(str(guild_id), 1)  # Padrão para sessão 1 se não definida

        # --- ALTERAÇÃO AQUI: Removido 'player.id' da lista ---
        log_entry = [timestamp, guild_id, session_number, player.display_name, action, amount]

        try:
            with open(STATS_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(log_entry)
            log.info(f"Estatística registrada: {log_entry}")
        except IOError as e:
            log.error(f"Falha ao escrever no arquivo de estatísticas '{STATS_LOG_FILE}': {e}")

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
        view = StatsSelectorView(author=ctx.author)
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
        view = SessionStatsSelectorView(author=ctx.author)
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
        """Compila todas as estatísticas do servidor e mostra os jogadores com os maiores recordes."""

        async with ctx.typing():
            # Estrutura para guardar os totais: {'PlayerName': {'action': total_amount}}
            all_player_stats = defaultdict(lambda: defaultdict(int))

            try:
                with open(STATS_LOG_FILE, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['guild_id'] == str(ctx.guild.id):
                            player_name = row['player_name']
                            action = row['action']
                            amount = int(row['amount'])
                            all_player_stats[player_name][action] += amount
            except FileNotFoundError:
                await ctx.reply("Ainda não há dados de sessão registrados para determinar os MVPs.")
                return

            if not all_player_stats:
                await ctx.reply("Ainda não há dados suficientes neste servidor para determinar os MVPs.")
                return

            # Dicionário para guardar os MVPs de cada categoria
            mvps = {}

            # Mapeia a 'action' para um título e descrição amigáveis
            action_map = {
                "causado": ("⚔️ Mão Pesada", "Maior Dano Causado"),
                "recebido": ("🛡️ Muralha de Carne", "Maior Dano Recebido"),
                "cura": ("❤️ Fonte de Vida", "Maior Cura Realizada"),
                "eliminacao": ("🎯 O Carrasco", "Mais Eliminações"),
                "jogador_caido": ("💀 Saco de Pancada", "Mais Vezes Caído"),
                "critico_sucesso": ("✨ O Sortudo", "Mais Acertos Críticos (20)"),
                "critico_falha": ("💥 O Azarado", "Mais Falhas Críticas (1)"),
            }

            # Encontra o jogador com o maior valor para cada ação
            for action, (title, desc) in action_map.items():
                top_player = None
                max_value = -1

                for player_name, stats in all_player_stats.items():
                    current_value = stats.get(action, 0)
                    if current_value > max_value:
                        max_value = current_value
                        top_player = player_name

                if top_player and max_value > 0:
                    mvps[action] = (top_player, max_value)

            # Cria o embed com os resultados
            embed = discord.Embed(
                title=f"🏆 Hall da Fama de {ctx.guild.name}",
                description="Os jogadores que deixaram sua marca na campanha!",
                color=discord.Color.gold()
            )

            for action, (title, desc) in action_map.items():
                if action in mvps:
                    player, value = mvps[action]
                    embed.add_field(
                        name=title,
                        value=f"**{player}** com um total de `{value}`\n*({desc})*",
                        inline=False
                    )
                else:
                    # Caso ninguém tenha registrado essa ação ainda
                    embed.add_field(
                        name=title,
                        value=f"Ninguém se destacou ainda.\n*({desc})*",
                        inline=False
                    )

            embed.set_footer(text="Estes são os recordes totais de todas as sessões.")
            await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(SessionCog(bot))