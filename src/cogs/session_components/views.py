# src/cogs/session_components/views.py

import discord
from discord.ext import commands
import asyncio
from .data_manager import SessionDataManager

PLAYER_ROLE_NAME = "Aventureiro"  # Mantemos a constante aqui para as Views

def get_players(guild: discord.Guild) -> list[discord.Member]:
    """Helper para pegar membros com o cargo de jogador."""
    player_role = discord.utils.find(lambda r: r.name.lower() == PLAYER_ROLE_NAME.lower(), guild.roles)
    return [m for m in guild.members if player_role and player_role in m.roles and not m.bot] if player_role else []

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
        embed = discord.Embed(title=f"📊 Estatísticas Totais de {player.display_name}", color=player.color)
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
                player_lines = [f"• {friendly_name}: `{stats[action]}`" for action, friendly_name in action_names.items() if stats.get(action, 0) > 0]
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
        players = get_players(interaction.guild)
        if not players:
            error_embed = self._create_embed(
                f"⚠️ **Cargo não encontrado!**\n\nNão encontrei nenhum membro com o cargo **'{PLAYER_ROLE_NAME}'**.\n\nCrie o cargo e atribua-o aos jogadores para continuar.",
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

    @discord.ui.button(label="Dano Causado", style=discord.ButtonStyle.green, row=0, emoji="⚔️")
    async def damage_dealt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "causado"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **causado**. Agora, selecione o jogador:")

    @discord.ui.button(label="Dano Recebido", style=discord.ButtonStyle.red, row=0, emoji="🛡️")
    async def damage_taken_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "recebido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Dano **recebido**. Agora, selecione o jogador:")

    @discord.ui.button(label="Cura Realizada", style=discord.ButtonStyle.primary, row=0, emoji="❤️")
    async def healing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "cura"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Cura **realizada**. Agora, selecione o jogador:")

    @discord.ui.button(label="Crítico (Sucesso)", style=discord.ButtonStyle.success, row=1, emoji="✨")
    async def crit_success_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_sucesso"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um **sucesso crítico**! Selecione o jogador:")

    @discord.ui.button(label="Crítico (Falha)", style=discord.ButtonStyle.danger, row=1, emoji="💥")
    async def crit_fail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "critico_falha"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Uma **falha crítica**! Selecione o jogador:")

    @discord.ui.button(label="Jogador Caído", style=discord.ButtonStyle.secondary, row=2, emoji="💀")
    async def player_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "jogador_caido"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um jogador **caiu em combate** (HP 0). Selecione o jogador:")

    @discord.ui.button(label="Eliminação", style=discord.ButtonStyle.secondary, row=2, emoji="🎯")
    async def elimination_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action_type = "eliminacao"
        self._disable_all_buttons()
        await self._prompt_for_player(interaction, "Um inimigo foi **eliminado**. Selecione o jogador responsável:")

    async def _finalize_log(self, interaction: discord.Interaction, player: discord.Member, action_text: str):
        """Helper para criar a mensagem final de confirmação."""
        final_embed = discord.Embed(
            title="✅ Evento Registrado!",
            description=f"A seguinte ação foi registrada para **{player.display_name}**:",
            color=discord.Color.green()
        )
        final_embed.add_field(name="Ação", value=action_text, inline=False)
        await interaction.edit_original_response(embed=final_embed, view=None)
        self.stop()

    async def player_select_amount_callback(self, interaction: discord.Interaction):
        self.player_select_menu.disabled = True
        player_id = int(self.player_select_menu.values[0])
        player = interaction.guild.get_member(player_id)

        prompt_message = f"Qual foi o valor de **{self.action_type}** para **{player.display_name}**?\n\nDigite apenas o número no chat."
        embed = self._create_embed(prompt_message)
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            message = await self.bot.wait_for(
                "message", timeout=60.0,
                check=lambda m: m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. O registro foi cancelado.", ephemeral=True)
            self.stop()
            return

        amount = int(message.content)
        self.data_manager.log_event(interaction.guild.id, player, self.action_type, amount)

        action_text_map = {
            "causado": f"⚔️ Dano Causado: `{amount}`",
            "recebido": f"🛡️ Dano Recebido: `{amount}`",
            "cura": f"❤️ Cura Realizada: `{amount}`"
        }
        action_text = action_text_map.get(self.action_type, f"{self.action_type.replace('_', ' ').title()}: {amount}")

        await self._finalize_log(interaction, player, action_text)

        try:
            await message.delete()
        except discord.HTTPException:
            pass

    async def player_select_event_callback(self, interaction: discord.Interaction):
        self.player_select_menu.disabled = True
        player_id = int(self.player_select_menu.values[0])
        player = interaction.guild.get_member(player_id)

        self.data_manager.log_event(interaction.guild.id, player, self.action_type, 1)

        action_text_map = {
            "critico_sucesso": "✨ Acerto Crítico (20)",
            "critico_falha": "💥 Falha Crítica (1)",
            "jogador_caido": "💀 Jogador Caído",
            "eliminacao": "🎯 Eliminação"
        }
        action_text = action_text_map.get(self.action_type, self.action_type.replace('_', ' ').title())

        await self._finalize_log(interaction, player, action_text)