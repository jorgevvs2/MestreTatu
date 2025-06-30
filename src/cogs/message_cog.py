import discord
from discord.ext import commands


class MessageCog(commands.Cog):
    """
    Um Cog dedicado para gerenciar a criação e o envio de mensagens padronizadas (Embeds).
    Isso centraliza a aparência do bot e permite a reutilização em outros cogs.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.transient_messages = {}  # Rastreia mensagens 'carregando...'
        self.last_info_messages = {}  # Rastreia a última mensagem de informação por servidor

    def create_embed(self, description: str, type: str = "info", title: str = None) -> discord.Embed:
        """
        Cria um embed padronizado para as mensagens do bot.
        Tipos: 'success', 'error', 'info'.
        """
        embed_configs = {
            "success": {"color": discord.Color.green(), "default_title": "✅ Sucesso"},
            "error": {"color": discord.Color.red(), "default_title": "❌ Erro"},
            "info": {"color": discord.Color.blue(), "default_title": "🎶 Informação"}
        }

        config = embed_configs.get(type, embed_configs["info"])
        embed_title = title if title else config["default_title"]

        embed = discord.Embed(
            title=embed_title,
            description=description,
            color=config["color"]
        )
        return embed

    async def send_message(self, ctx: commands.Context, embed: discord.Embed, transient: bool = False):
        """
        Envia uma mensagem, limpando mensagens anteriores para manter o canal limpo.
        - Mensagens 'transient' (como 'Buscando...') são sempre limpas.
        - Mensagens de 'info' consecutivas são substituídas.
        """
        guild_id = ctx.guild.id
        # Inferimos o tipo da mensagem pela cor, para não alterar a API do método.
        is_info_message = embed.color == discord.Color.blue()

        # Prioridade 1: Limpar a mensagem transitória anterior (ex: 'Buscando...')
        if guild_id in self.transient_messages:
            try:
                old_message = self.transient_messages.pop(guild_id)
                await old_message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
        # Prioridade 2: Se não houver mensagem transitória, limpa a última mensagem de 'info'
        # se a nova mensagem também for de 'info'.
        elif is_info_message and guild_id in self.last_info_messages:
            try:
                old_message = self.last_info_messages.pop(guild_id)
                await old_message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass

        message = await ctx.send(embed=embed)

        # Rastreia a mensagem para a próxima limpeza, se necessário
        if transient:
            self.transient_messages[guild_id] = message

        if is_info_message:
            self.last_info_messages[guild_id] = message
        # Se uma mensagem de sucesso/erro for enviada, ela quebra a sequência de 'info'
        elif guild_id in self.last_info_messages:
            del self.last_info_messages[guild_id]


async def setup(bot: commands.Bot):
    """Função de setup para carregar o Cog."""
    await bot.add_cog(MessageCog(bot))