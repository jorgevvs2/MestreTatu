# src/cogs/admin_cog.py

import discord
from discord.ext import commands
import sqlite3
import logging
from datetime import datetime

log = logging.getLogger(__name__)

class AdminCog(commands.Cog, name="Administração"):
    """Comandos para o gerenciamento do bot e seus dados."""

    def __init__(self, bot):
        self.bot = bot
        # --- CORREÇÃO: Usar o caminho absoluto para o volume ---
        self.db_path = '/data/stats.db'

    @commands.command(name='sessionlogs', help='Lista todos os logs de uma sessão específica. (Dono do bot)')
    @commands.is_owner()
    async def session_logs(self, ctx: commands.Context, session_id: int):
        """
        Busca e exibe todas as entradas de log associadas a um ID de sessão.
        Cada entrada terá um ID único para permitir a sua exclusão.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
            cursor = conn.cursor()

            # Busca os logs da sessão, ordenados pelo ID de inserção (ordem cronológica)
            cursor.execute(
                "SELECT id, timestamp, player_name, action, amount FROM session_stats WHERE guild_id = ? AND session_number = ? ORDER BY id ASC",
                (str(ctx.guild.id), session_id)
            )
            logs_data = cursor.fetchall()

            if not logs_data:
                await ctx.send(f"Nenhum log encontrado para a sessão `{session_id}`. Verifique se o ID da sessão está correto.")
                return

            # Usa o paginador do discord.py para lidar com listas longas de forma limpa
            paginator = commands.Paginator(prefix='', suffix='', max_size=2000)
            paginator.add_line(f"**📜 Logs da Sessão `{session_id}`**\n---")

            for row in logs_data:
                action_text = row['action'].replace('_', ' ').title()
                ts_obj = datetime.fromisoformat(row['timestamp'])
                formatted_ts = ts_obj.strftime('%d/%m %H:%M')

                log_line = (
                    f"**ID do Log: `{row['id']}`** | `{formatted_ts}` | "
                    f"**{row['player_name']}** - `{action_text}: {row['amount']}`"
                )
                paginator.add_line(log_line)

            # Envia as páginas para o usuário
            for page in paginator.pages:
                await ctx.send(page)

        except sqlite3.Error as e:
            log.error(f"Erro de banco de dados no comando sessionlogs: {e}")
            await ctx.send(f"🔥 Ocorreu um erro no banco de dados: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    @commands.command(name='dellog', help='Deleta uma entrada de log específica pelo seu ID. (Dono do bot)')
    @commands.is_owner()
    async def delete_log(self, ctx: commands.Context, log_id: int):
        """
        Deleta uma única entrada de log do banco de dados 'session_stats'.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verifica se o log existe antes de deletar para dar um feedback melhor
            cursor.execute("SELECT id FROM session_stats WHERE id = ?", (log_id,))
            if not cursor.fetchone():
                await ctx.send(f"❌ Erro: Nenhuma entrada de log encontrada com o ID `{log_id}`.")
                return

            # Deleta o log
            cursor.execute("DELETE FROM session_stats WHERE id = ?", (log_id,))
            conn.commit()

            await ctx.send(f"✅ Sucesso! A entrada de log com ID `{log_id}` foi permanentemente deletada.")

        except sqlite3.Error as e:
            log.error(f"Erro de banco de dados no comando dellog: {e}")
            await ctx.send(f"🔥 Ocorreu um erro no banco de dados: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Trata erros comuns para os comandos deste cog."""
        if isinstance(error, commands.NotOwner):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"🤔 Comando incompleto. Use `.help {ctx.command.name}` para ver como usar.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("🤔 O ID fornecido deve ser um número inteiro.")
        else:
            log.error(f"Erro inesperado no cog Admin: {error}", exc_info=True)
            await ctx.send("🔥 Ocorreu um erro inesperado ao processar o comando.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(AdminCog(bot))