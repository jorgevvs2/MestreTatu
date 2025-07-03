# src/cogs/logging_cog.py

import logging
import os  # Importe o módulo 'os'
from discord.ext import commands

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)

# --- ALTERAÇÃO AQUI: Define o diretório e o caminho do arquivo ---
LOGS_DIR = "src/logs"
RPG_LOG_FILE = os.path.join(LOGS_DIR, "rpg_questions_log.txt")


class LoggingCog(commands.Cog):
    """
    Um cog dedicado a registrar os inputs de comandos específicos,
    especialmente os direcionados ao Mestre de RPG.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_file = RPG_LOG_FILE

        # --- ADIÇÃO AQUI: Garante que o diretório de logs exista ---
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)
            log.info(f"Diretório de logs '{LOGS_DIR}' criado.")

        log.info("LoggingCog carregado e pronto para registrar comandos do RPG.")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        """
        Este evento é acionado sempre que um comando é executado com sucesso.
        """
        if not ctx.cog or ctx.cog.qualified_name != "Mestre de RPG":
            return

        timestamp = ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        user = f"{ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
        guild = ctx.guild.name if ctx.guild else "Direct Message"
        full_command = ctx.message.content

        log_entry = f"[{timestamp}] | Guild: {guild} | User: {user} | Input: {full_command}\n"

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except IOError as e:
            log.error(f"Falha ao escrever no arquivo de log '{self.log_file}': {e}")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(LoggingCog(bot))