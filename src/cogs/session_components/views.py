# src/cogs/session_components/views.py

import discord
from discord.ext import commands
import asyncio
import logging
from .data_manager import SessionDataManager

log = logging.getLogger(__name__)
# Esta constante agora é usada apenas pelo comando .stats, que ainda se baseia em cargos.
PLAYER_ROLE_NAME = "Aventureiro"


def get_players(guild: discord.Guild) -> list[discord.Member]:
    """Helper para pegar membros com o cargo de jogador para o comando .stats."""
    player_role = discord.utils.find(lambda r: r.name.lower() == PLAYER_ROLE_NAME.lower(), guild.roles)
    return [m for m in guild.members if player_role and player_role in m.roles and not m.bot] if player_role else []


class CampaignSelectorView(discord.ui.View):
    """Uma View para selecionar a campanha ativa."""

    def __init__(self, author: discord.Member, data_manager: SessionDataManager):
        super().__init__(timeout=180)
        self.author = author
        self.data_manager = data_manager
        self.message = None

        campaigns = self.data_manager.get_campaigns_for_guild(author.guild.id)
        if not campaigns:
            return

        options = []
        for campaign in campaigns:
            # Adiciona um emoji para indicar a campanha ativa no menu
            label = f"✅ {campaign['name']}" if campaign['is_active'] else campaign['name']
            options.append(
                discord.SelectOption(label=label, value=str(campaign['id']), description=f"ID: {campaign['id']}"))

        campaign_select_menu = discord.ui.Select(placeholder="Selecione a campanha a ser ativada...", options=options)
        campaign_select_menu.callback = self.campaign_select_callback
        self.add_item(campaign_select_menu)

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

    async def campaign_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_campaign_id = int(self.children[0].values[0])

        self.data_manager.set_active_campaign(interaction.guild.id, selected_campaign_id)

        # Encontra o nome da campanha para a mensagem de confirmação
        selected_campaign_name = ""
        for option in self.children[0].options:
            if int(option.value) == selected_campaign_id:
                selected_campaign_name = option.label.replace("✅ ", "")  # Remove o emoji
                break

        embed = discord.Embed(
            title="👑 Campanha Ativa Definida!",
            description=f"A campanha **{selected_campaign_name}** agora é a ativa.\nTodos os comandos (`.log`, `.stats`, etc.) usarão os dados desta campanha.",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=embed, view=None)


class StatsSelectorView(discord.ui.View):
    """Uma View para selecionar um jogador e mostrar suas estatísticas totais."""

    def __init__(self, author: discord.Member, data_manager: SessionDataManager):
        super().__init__(timeout=180)
        self.author = author
        self.data_manager = data_manager
        self.message = None

        players = get_players(author.guild)
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

        stats = self.data_manager.get_player_total_stats(interaction.guild.id, player.display_name)
        embed = discord.Embed(title=f"📊 Estatísticas de {player.display_name} na Campanha Ativa", color=player.color)
        embed.set_thumbnail(url=player.display_avatar.url)
        embed.add_field(name="⚔️ Dano Causado", value=f"`{stats['causado']}`", inline=True)
        embed.add_field(name="🛡️ Dano Recebido", value=f"`{stats['recebido']}`", inline=True)
        embed.add_field(name="❤️ Cura Realizada", value=f"`{stats['cura']}`", inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=False)
        embed.add_field(name="✨ Acertos Críticos", value=f"`{stats['critico_sucesso']}`", inline=True)
        embed.add_field(name="💥 Falhas Críticas", value=f"`{stats['critico_falha']}`", inline=True)
        embed.add_field(name="🎯 Eliminações", value=f"`{stats['eliminacao']}`", inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=False)
        embed.add_field(name="💀 Vezes Caído", value=f"`{stats['jogador_caido']}`", inline=True)
        await interaction.edit_original_response(embed=embed, view=None)


class SessionStatsSelectorView(discord.ui.View):
    """Uma View para selecionar uma sessão e mostrar seus detalhes."""

    def __init__(self, author: discord.Member, data_manager: SessionDataManager):
        super().__init__(timeout=180)
        self.author = author
        self.data_manager = data_manager
        self.message = None

        sessions_data = self.data_manager.get_available_sessions(author.guild.id)
        if not sessions_data:
            return

        options = []
        for s_num, title in sessions_data:
            label = f"Sessão {s_num}"
            if title:
                truncated_title = (title[:80] + '...') if len(title) > 80 else title
                label += f": {truncated_title}"
            options.append(discord.SelectOption(label=label, value=str(s_num)))

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

        session_info = self.data_manager.get_session_info(interaction.guild.id, selected_session)
        session_stats = self.data_manager.get_session_stats(interaction.guild.id, selected_session)

        title = session_info.get('title')
        description = session_info.get('description', "Nenhum resumo adicionado para esta sessão.")
        embed_title = f"📜 Sessão {selected_session}: {title}" if title else f"📜 Resumo da Sessão {selected_session}"
        embed = discord.Embed(title=embed_title, description=description, color=discord.Color.purple())

        if not session_stats:
            embed.add_field(name="\u200b", value="Nenhuma estatística registrada para esta sessão.")
        else:
            action_names = {
                "causado": "Dano Causado", "recebido": "Dano Recebido", "cura": "Cura",
                "eliminacao": "Abates", "jogador_caido": "Quedas",
                "critico_sucesso": "Críticos (20)", "critico_falha": "Falhas (1)"
            }
            for player, stats in sorted(session_stats.items()):
                player_lines = [f"• {friendly_name}: `{stats[action]}`" for action, friendly_name in
                                action_names.items() if stats.get(action, 0) > 0]
                player_summary = "\n".join(player_lines) if player_lines else "Nenhuma atividade registrada."
                embed.add_field(name=f"👤 {player}", value=player_summary, inline=False)

        await interaction.edit_original_response(embed=embed, view=None)


class SessionTrackerView(discord.ui.View):
    """Uma View interativa para registrar eventos de sessão."""

    def __init__(self, author: discord.Member, bot: commands.Bot, data_manager: SessionDataManager):
        super().__init__(timeout=180)
        self.author = author
        self.bot = bot
        self.data_manager = data_manager
        self.action_type = None
        self.player_select_menu = None
        self.message = None

    def _create_embed(self, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        return discord.Embed(title="📝 Registro de Evento de Sessão", description=description, color=color)

    async def on_timeout(self):
        if self.message:
            timeout_embed = self._create_embed("Este menu de registro de evento expirou.", color=discord.Color.orange())
            await self.message.edit(embed=timeout_embed, view=None)

    def _disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def _prompt_for_player(self, interaction: discord.Interaction, prompt_text: str):
        # Busca a lista de personagens da campanha ativa.
        players = self.data_manager.get_players_for_campaign(interaction.guild.id)

        if not players:
            error_embed = self._create_embed(
                f"⚠️ **Nenhum Personagem Encontrado!**\n\nNão encontrei personagens registrados para a campanha ativa.\n\nUse o comando `.addplayer <nome do personagem>` para adicioná-los.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
            self.stop()
            return

        # O valor do 'option' agora é o próprio nome do personagem.
        options = [discord.SelectOption(label=name, value=name) for name in players]
        self.player_select_menu = discord.ui.Select(placeholder="Selecione o personagem...", options=options)

        if self.action_type in ["causado", "recebido", "cura"]:
            self.player_select_menu.callback = self.player_select_amount_callback
        else:
            self.player_select_menu.callback = self.player_select_event_callback

        self.add_item(self.player_select_menu)
        embed = self._create_embed(prompt_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Dano Causado", style=discord.ButtonStyle.green, row=0, emoji="⚔️")
    async def damage_dealt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "causado"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **causado**. Agora, selecione o personagem:")

    @discord.ui.button(label="Dano Recebido", style=discord.ButtonStyle.red, row=0, emoji="🛡️")
    async def damage_taken_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "recebido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **recebido**. Agora, selecione o personagem:")

    @discord.ui.button(label="Cura Realizada", style=discord.ButtonStyle.primary, row=0, emoji="❤️")
    async def healing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "cura"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Cura **realizada**. Agora, selecione o personagem:")

    @discord.ui.button(label="Crítico (Sucesso)", style=discord.ButtonStyle.success, row=1, emoji="✨")
    async def crit_success_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_sucesso"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um **sucesso crítico**! Selecione o personagem:")

    @discord.ui.button(label="Crítico (Falha)", style=discord.ButtonStyle.danger, row=1, emoji="💥")
    async def crit_fail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_falha"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Uma **falha crítica**! Selecione o personagem:")

    @discord.ui.button(label="Jogador Caído", style=discord.ButtonStyle.secondary, row=2, emoji="💀")
    async def player_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "jogador_caido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um personagem **caiu em combate** (HP 0). Selecione-o:")

    @discord.ui.button(label="Eliminação", style=discord.ButtonStyle.secondary, row=2, emoji="🎯")
    async def elimination_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "eliminacao"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um inimigo foi **eliminado**. Selecione o personagem responsável:")

    async def _prompt_for_player(self, interaction: discord.Interaction, prompt_text: str):
        # Busca a lista de personagens da campanha ativa.
        players = self.data_manager.get_players_for_campaign(interaction.guild.id)

        if not players:
            error_embed = self._create_embed(
                f"⚠️ **Nenhum Personagem Encontrado!**\n\nNão encontrei personagens registrados para a campanha ativa.\n\nUse o comando `.addplayer <nome do personagem>` para adicioná-los.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
            self.stop()
            return

        # O valor do 'option' agora é o próprio nome do personagem.
        options = [discord.SelectOption(label=name, value=name) for name in players]
        self.player_select_menu = discord.ui.Select(placeholder="Selecione o personagem...", options=options)

        # CORREÇÃO: A lógica agora diferencia corretamente os dois tipos de callback.
        if self.action_type in ["causado", "recebido", "cura"]:
            self.player_select_menu.callback = self.player_select_amount_callback
        else:
            self.player_select_menu.callback = self.player_select_event_callback

        self.add_item(self.player_select_menu)
        embed = self._create_embed(prompt_text)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _finalize_log(self, interaction: discord.Interaction, player_name: str, action_text: str):
        """Helper para criar a mensagem final de confirmação, agora recebendo player_name (str)."""
        # CORREÇÃO: A descrição agora usa 'player_name' diretamente, pois é uma string.
        final_embed = discord.Embed(
            title="✅ Evento Registrado!",
            description=f"A seguinte ação foi registrada para **{player_name}** na campanha ativa:",
            color=discord.Color.green()
        )
        final_embed.add_field(name="Ação", value=action_text, inline=False)

        try:
            # Tenta editar a resposta original, que é o comportamento padrão.
            await interaction.edit_original_response(embed=final_embed, view=None)
        except discord.errors.NotFound:
            # Se o token da interação expirou, enviamos uma nova mensagem no canal.
            log.warning(
                f"Token de interação para o log de {interaction.user} expirou. Enviando uma nova mensagem no canal.")
            try:
                # Envia uma nova mensagem no canal, mencionando o usuário para garantir que ele veja.
                await interaction.channel.send(
                    content=f"✅ {interaction.user.mention}, seu registro foi salvo com sucesso, mas o menu original expirou.",
                    embed=final_embed
                )
            except discord.HTTPException as e:
                log.error(f"Falha ao enviar mensagem de confirmação no canal após interação expirada: {e}")
        finally:
            # Garante que a view seja parada para não aceitar mais interações.
            self.stop()

    async def player_select_amount_callback(self, interaction: discord.Interaction):
        """Callback para eventos que requerem um valor numérico (dano, cura)."""
        self.player_select_menu.disabled = True
        # O valor selecionado é o nome do personagem, não um ID.
        character_name = self.player_select_menu.values[0]

        prompt_message = f"Qual foi o valor de **{self.action_type.replace('_', ' ')}** para **{character_name}**?\n\nDigite apenas o número no chat."
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
        try:
            # Passa o nome do personagem (string) diretamente para o data_manager.
            self.data_manager.log_event(interaction.guild.id, character_name, self.action_type, amount)
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ Erro: {e}", embed=None, view=None)
            return

        action_text_map = {
            "causado": f"⚔️ Dano Causado: `{amount}`",
            "recebido": f"🛡️ Dano Recebido: `{amount}`",
            "cura": f"❤️ Cura Realizada: `{amount}`"
        }
        action_text = action_text_map.get(self.action_type, f"{self.action_type.replace('_', ' ').title()}: {amount}")

        # CORREÇÃO: Passa o nome do personagem (string) para a função de finalização.
        await self._finalize_log(interaction, character_name, action_text)

        try:
            await message.delete()
        except discord.HTTPException:
            pass

    async def player_select_event_callback(self, interaction: discord.Interaction):
        """Callback para eventos que não requerem um valor (críticos, quedas, etc.)."""
        self.player_select_menu.disabled = True
        # O valor selecionado é o nome do personagem, não um ID.
        character_name = self.player_select_menu.values[0]

        try:
            # Passa o nome do personagem (string) diretamente para o data_manager com valor 1.
            self.data_manager.log_event(interaction.guild.id, character_name, self.action_type, 1)
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ Erro: {e}", embed=None, view=None)
            return

        action_text_map = {
            "critico_sucesso": "✨ Acerto Crítico (20)",
            "critico_falha": "💥 Falha Crítica (1)",
            "jogador_caido": "💀 Personagem Caído",
            "eliminacao": "🎯 Eliminação"
        }
        action_text = action_text_map.get(self.action_type, self.action_type.replace('_', ' ').title())

        # CORREÇÃO: Passa o nome do personagem (string) para a função de finalização.
        await self._finalize_log(interaction, character_name, action_text)