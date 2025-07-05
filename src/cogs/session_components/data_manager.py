# src/cogs/session_components/data_manager.py

import sqlite3
import json
import logging
from datetime import datetime
from collections import defaultdict
import discord

log = logging.getLogger(__name__)

class SessionDataManager:
    """Gerencia toda a interação com o banco de dados e arquivos de sessão."""

    def __init__(self, db_path: str, session_file_path: str):
        self.db_path = db_path
        self.session_file_path = session_file_path
        self.session_data = self._load_session_data()

    def _load_session_data(self) -> dict:
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_session_data(self):
        try:
            with open(self.session_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=4)
        except IOError as e:
            log.error(f"Falha ao salvar os dados da sessão: {e}")

    def get_active_session(self, guild_id: int) -> int:
        """Retorna o número da sessão ativa, padrão 1."""
        return self.session_data.get(str(guild_id), 1)

    def set_active_session(self, guild_id: int, session_number: int):
        """Define o número da sessão ativa."""
        self.session_data[str(guild_id)] = session_number
        self.save_session_data()

    def log_event(self, guild_id: int, player: discord.Member, action: str, amount: int):
        """Registra um evento no banco de dados SQLite."""
        timestamp = datetime.utcnow().isoformat()
        session_number = self.get_active_session(guild_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO session_stats (timestamp, guild_id, session_number, player_name, action, amount) VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp, str(guild_id), session_number, player.display_name, action, amount)
                )
            log.info(f"Estatística registrada para {player.display_name}: {action} - {amount}")
        except Exception as e:
            log.error(f"Falha ao escrever no banco de dados: {e}", exc_info=True)

    def get_player_total_stats(self, guild_id: int, player_name: str) -> defaultdict:
        """Busca as estatísticas totais de um jogador no banco de dados."""
        stats = defaultdict(int)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT action, SUM(amount) FROM session_stats WHERE guild_id = ? AND player_name = ? GROUP BY action",
                    (str(guild_id), player_name)
                )
                for action, total_amount in cursor.fetchall():
                    stats[action] = total_amount
        except Exception as e:
            log.error(f"Erro ao buscar estatísticas de {player_name}: {e}", exc_info=True)
        return stats

    def get_available_sessions(self, guild_id: int) -> list[tuple[int, str | None]]:
        """Retorna uma lista de tuplas (número_da_sessão, título) do banco de dados."""
        sessions_data = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT s.session_number, ses.title
                    FROM session_stats s
                    LEFT JOIN sessions ses ON s.guild_id = ses.guild_id AND s.session_number = ses.session_number
                    WHERE s.guild_id = ?
                    ORDER BY s.session_number DESC
                """, (str(guild_id),))
                sessions_data = cursor.fetchall()
        except Exception as e:
            log.error(f"Erro ao buscar sessões disponíveis: {e}", exc_info=True)
        return sessions_data

    def get_session_stats(self, guild_id: int, session_number: int) -> defaultdict:
        """Busca as estatísticas de uma sessão específica do banco de dados."""
        session_stats = defaultdict(lambda: defaultdict(int))
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT player_name, action, SUM(amount) FROM session_stats WHERE guild_id = ? AND session_number = ? GROUP BY player_name, action",
                    (str(guild_id), session_number)
                )
                for player_name, action, total_amount in cursor.fetchall():
                    session_stats[player_name][action] = total_amount
        except Exception as e:
            log.error(f"Erro ao buscar estatísticas da sessão {session_number}: {e}", exc_info=True)
        return session_stats

    def get_session_info(self, guild_id: int, session_number: int) -> dict:
        """Busca o título e a descrição de uma sessão específica."""
        info = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT title, description FROM sessions WHERE guild_id = ? AND session_number = ?",
                    (str(guild_id), session_number)
                )
                row = cursor.fetchone()
                if row:
                    info = dict(row)
        except Exception as e:
            log.error(f"Erro ao buscar informações da sessão {session_number}: {e}", exc_info=True)
        return info

    def get_mvps(self, guild_id: int) -> dict[str, list]:
        """Compila estatísticas do banco de dados e retorna os recordistas."""
        mvps = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                actions = ["causado", "recebido", "cura", "eliminacao", "jogador_caido", "critico_sucesso", "critico_falha"]
                for action in actions:
                    cursor.execute("""
                        SELECT player_name, SUM(amount) as total
                        FROM session_stats
                        WHERE guild_id = ? AND action = ?
                        GROUP BY player_name
                        ORDER BY total DESC
                    """, (str(guild_id), action))
                    results = cursor.fetchall()
                    if results and results[0][1] > 0:
                        top_score = results[0][1]
                        mvps[action] = ([row[0] for row in results if row[1] == top_score], top_score)
        except Exception as e:
            log.error(f"Erro ao gerar MVPs: {e}", exc_info=True)
        return mvps

    def end_session(self, guild_id: int, session_number: int, title: str, description: str):
        """Salva um resumo da sessão atual no banco de dados."""
        timestamp = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sessions (guild_id, session_number, title, description, end_timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(guild_id), session_number, title, description, timestamp))
        except Exception as e:
            log.error(f"Erro ao finalizar a sessão {session_number}: {e}", exc_info=True)
            raise  # Re-levanta a exceção para ser tratada no cog