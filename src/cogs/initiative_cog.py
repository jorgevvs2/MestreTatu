import discord
from discord.ext import commands
from typing import Dict, Any, Optional

# --- Modals for User Input ---

class AddCharacterModal(discord.ui.Modal, title="Adicionar Personagem"):
    """Um formulário para adicionar um personagem à iniciativa."""
    def __init__(self, cog_instance):
        super().__init__()
        self.cog = cog_instance

    initiative_input = discord.ui.TextInput(
        label="Iniciativa",
        placeholder="Digite o valor da iniciativa (ex: 18)",
        required=True,
        style=discord.TextStyle.short
    )

    name_input = discord.ui.TextInput(
        label="Nome do Personagem (Opcional)",
        placeholder="Deixe em branco para usar seu nick",
        required=False,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        tracker = self.cog._get_tracker(interaction.channel.id)
        if not tracker:
            await interaction.response.send_message("O combate neste canal já foi encerrado.", ephemeral=True)
            return

        try:
            initiative = int(self.initiative_input.value)
        except ValueError:
            await interaction.response.send_message("O valor da iniciativa deve ser um número.", ephemeral=True)
            return

        character_name = self.name_input.value.strip() if self.name_input.value else interaction.user.display_name

        if any(p['name'].lower() == character_name.lower() for p in tracker['participants']):
            await interaction.response.send_message(f"O personagem '{character_name}' já está na iniciativa.", ephemeral=True)
            return

        tracker["participants"].append({"name": character_name, "initiative": initiative})
        tracker["participants"].sort(key=lambda x: x["initiative"], reverse=True)

        await self.cog._update_tracker_message(interaction, tracker)
        await interaction.response.send_message(f"✅ Personagem '{character_name}' adicionado com iniciativa {initiative}.", ephemeral=True, delete_after=5)

class RemoveCharacterModal(discord.ui.Modal, title="Remover Personagem"):
    """Um formulário para remover um personagem da iniciativa."""
    def __init__(self, cog_instance):
        super().__init__()
        self.cog = cog_instance

    name_input = discord.ui.TextInput(
        label="Nome do Personagem a ser Removido",
        placeholder="Digite o nome exato do personagem",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        tracker = self.cog._get_tracker(interaction.channel.id)
        if not tracker:
            await interaction.response.send_message("O combate neste canal já foi encerrado.", ephemeral=True)
            return

        name_to_remove = self.name_input.value.strip()
        name_lower = name_to_remove.lower()

        participant_to_remove = next((p for p in tracker["participants"] if p["name"].lower() == name_lower), None)

        if participant_to_remove:
            current_participant_name = tracker["participants"][tracker["current_turn"]]["name"]
            tracker["participants"].remove(participant_to_remove)

            if participant_to_remove["name"] != current_participant_name:
                try:
                    tracker["current_turn"] = [p["name"] for p in tracker["participants"]].index(current_participant_name)
                except ValueError:
                    tracker["current_turn"] = 0

            if tracker["participants"] and tracker["current_turn"] >= len(tracker["participants"]):
                tracker["current_turn"] = 0

            await self.cog._update_tracker_message(interaction, tracker)
            await interaction.response.send_message(f"✅ Personagem '{name_to_remove}' removido.", ephemeral=True, delete_after=5)
        else:
            await interaction.response.send_message(f"❌ Personagem '{name_to_remove}' não encontrado.", ephemeral=True)

# --- The Main View with Buttons ---

class InitiativeView(discord.ui.View):
    """A View que contém todos os botões para gerenciar a iniciativa."""
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    async def _handle_turn_change(self, interaction: discord.Interaction, direction: str):
        tracker = self.cog._get_tracker(interaction.channel.id)
        if not tracker or not tracker.get("participants"):
            await interaction.response.send_message("O combate não foi iniciado ou não há participantes.", ephemeral=True)
            return

        if direction == 'next':
            tracker["current_turn"] += 1
            if tracker["current_turn"] >= len(tracker["participants"]):
                tracker["current_turn"] = 0
                tracker["round"] += 1
                await interaction.channel.send(f"**--- Rodada {tracker['round']} ---**", delete_after=10)
        elif direction == 'prev':
            tracker["current_turn"] -= 1
            if tracker["current_turn"] < 0:
                if tracker["round"] > 1:
                    tracker["current_turn"] = len(tracker["participants"]) - 1
                    tracker["round"] -= 1
                else:
                    tracker["current_turn"] = 0

        await self.cog._update_tracker_message(interaction, tracker)
        if not interaction.response.is_done():
            await interaction.response.defer()

    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.green, custom_id="init_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_turn_change(interaction, 'next')

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary, custom_id="init_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_turn_change(interaction, 'prev')

    @discord.ui.button(label="Adicionar", style=discord.ButtonStyle.primary, custom_id="init_add")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCharacterModal(self.cog))

    @discord.ui.button(label="Remover", style=discord.ButtonStyle.gray, custom_id="init_remove")
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RemoveCharacterModal(self.cog))

    @discord.ui.button(label="Encerrar", style=discord.ButtonStyle.danger, custom_id="init_end")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        tracker = self.cog._get_tracker(interaction.channel.id)
        if not tracker:
            await interaction.response.send_message("O combate já foi encerrado.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        embed = self.cog._generate_embed(tracker)
        embed.title = f"⚔️ Combate Encerrado (Rodada {tracker['round']})"
        embed.color = discord.Color.light_grey()
        embed.set_footer(text="Use .init para um novo combate.")

        await interaction.response.edit_message(embed=embed, view=self)
        del self.cog.trackers[interaction.channel.id]

# --- The Cog itself ---

class InitiativeCog(commands.Cog, name="Rastreador de Iniciativa"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.trackers: Dict[int, Dict[str, Any]] = {}
        self.bot.add_view(InitiativeView(self))

    def _get_tracker(self, channel_id: int) -> Optional[Dict[str, Any]]:
        return self.trackers.get(channel_id)

    async def _update_tracker_message(self, interaction: discord.Interaction, tracker: Dict[str, Any]):
        embed = self._generate_embed(tracker)
        try:
            await interaction.message.edit(embed=embed)
        except discord.NotFound:
            await interaction.channel.send("A mensagem de iniciativa original foi perdida. Por favor, inicie um novo combate com `.init`.", ephemeral=True)
        except discord.Forbidden:
            await interaction.channel.send("Não tenho permissão para editar a mensagem de iniciativa.", ephemeral=True)

    def _generate_embed(self, tracker: Dict[str, Any]) -> discord.Embed:
        title = f"⚔️ Ordem de Iniciativa - Rodada {tracker['round']}"
        if not tracker["participants"]:
            description = "Nenhum participante na iniciativa.\nUse o botão `Adicionar` para começar."
            return discord.Embed(title=title, description=description, color=discord.Color.orange())

        description_lines = []
        for i, p in enumerate(tracker["participants"]):
            if i == tracker["current_turn"]:
                description_lines.append(f"▶️ **`{p['initiative']:>2}` | {p['name']}** 👈")
            else:
                description_lines.append(f"➖ `{p['initiative']:>2}` | {p['name']}")

        embed = discord.Embed(title=title, description="\n".join(description_lines), color=discord.Color.dark_red())
        embed.set_footer(text="Use os botões abaixo para gerenciar o combate.")
        return embed

    @commands.command(name='init', help="Inicia um novo painel de iniciativa no canal.")
    @commands.guild_only()
    async def init(self, ctx: commands.Context):
        if self._get_tracker(ctx.channel.id):
            await ctx.reply("Já existe um combate em andamento neste canal. Use o botão `Encerrar` no painel de iniciativa.", delete_after=10)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            return

        tracker = {
            "participants": [],
            "current_turn": 0,
            "round": 1
        }

        view = InitiativeView(self)
        embed = self._generate_embed(tracker)
        await ctx.send(embed=embed, view=view)
        self.trackers[ctx.channel.id] = tracker

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(InitiativeCog(bot))