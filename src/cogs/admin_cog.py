# src/cogs/admin_cog.py

import discord
from discord.ext import commands
import sqlite3
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

# Define os caminhos do banco de dados de forma consistente
DATA_DIR = '/app/data'
DB_FILE = os.path.join(DATA_DIR, 'stats.db')


class AdminCog(commands.Cog, name="Administração"):
    """Comandos para o gerenciamento do bot e seus dados."""

    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_FILE

    @commands.command(name='sessionlogs', help='Lista os logs de uma sessão da campanha ativa. (Dono do bot)')
    @commands.is_owner()
    async def session_logs(self, ctx: commands.Context, session_id: int):
        """
        Busca e exibe todas as entradas de log associadas a um ID de sessão
        da campanha atualmente ativa.
        """
        if not os.path.exists(self.db_path):
            await ctx.send(f"❌ Erro: O arquivo de banco de dados não foi encontrado em `{self.db_path}`.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # --- CORREÇÃO AQUI: Buscar o ID da campanha ativa primeiro ---
            cursor.execute(
                "SELECT id FROM campaigns WHERE guild_id = ? AND is_active = 1",
                (str(ctx.guild.id),)
            )
            active_campaign_row = cursor.fetchone()

            if not active_campaign_row:
                await ctx.send("⚠️ Nenhuma campanha ativa! Use `.setcampaign` para definir uma antes de ver os logs.")
                return

            active_campaign_id = active_campaign_row['id']

            # --- CORREÇÃO AQUI: Adicionar o filtro de campaign_id na query ---
            cursor.execute(
                "SELECT id, timestamp, player_name, action, amount FROM session_stats WHERE guild_id = ? AND campaign_id = ? AND session_number = ? ORDER BY id ASC",
                (str(ctx.guild.id), active_campaign_id, session_id)
            )
            logs_data = cursor.fetchall()

            if not logs_data:
                await ctx.send(
                    f"Nenhum log encontrado para a sessão `{session_id}` na campanha ativa. Verifique se o ID da sessão está correto.")
                return

            paginator = commands.Paginator(prefix='', suffix='', max_size=2000)
            paginator.add_line(f"**📜 Logs da Sessão `{session_id}` (Campanha Ativa)**\n---")

            for row in logs_data:
                action_text = row['action'].replace('_', ' ').title()
                ts_obj = datetime.fromisoformat(row['timestamp'])
                formatted_ts = ts_obj.strftime('%d/%m %H:%M')

                log_line = (
                    f"**ID do Log: `{row['id']}`** | `{formatted_ts}` | "
                    f"**{row['player_name']}** - `{action_text}: {row['amount']}`"
                )
                paginator.add_line(log_line)

            for page in paginator.pages:
                await ctx.send(page)

        except sqlite3.Error as e:
            log.error(f"Erro de banco de dados no comando sessionlogs: {e}", exc_info=True)
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
            log.error(f"Erro de banco de dados no comando dellog: {e}", exc_info=True)
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