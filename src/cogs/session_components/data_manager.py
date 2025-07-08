# src/cogs/session_components/data_manager.py

import sqlite3
import json
import logging
from datetime import datetime
from collections import defaultdict
import discord

log = logging.getLogger(__name__)


class SessionDataManager:
    """Gerencia toda a interação com o banco de dados e arquivos de sessão, agora com suporte a múltiplas campanhas."""

    def __init__(self, db_path: str, session_file_path: str):
        self.db_path = db_path
        self.session_file_path = session_file_path
        # O JSON agora guarda o número da sessão ativa POR CAMPANHA
        self.session_data = self._load_session_data()

    # --- Gerenciamento de Campanha ---

    def create_campaign(self, guild_id: int, name: str| None = None):
        """Cria uma nova campanha no banco de dados para um servidor."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO campaigns (guild_id, name, description) VALUES (?, ?, ?)",
                (str(guild_id), name)
            )

    def get_campaigns_for_guild(self, guild_id: int) -> list[sqlite3.Row]:
        """Busca todas as campanhas de um servidor."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, is_active FROM campaigns WHERE guild_id = ? ORDER BY name",
                           (str(guild_id),))
            return cursor.fetchall()

    def set_active_campaign(self, guild_id: int, campaign_id: int):
        """Define uma campanha como ativa para um servidor, desativando as outras."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Desativa todas as outras campanhas do servidor
            cursor.execute("UPDATE campaigns SET is_active = 0 WHERE guild_id = ?", (str(guild_id),))
            # Ativa a campanha escolhida
            cursor.execute("UPDATE campaigns SET is_active = 1 WHERE id = ? AND guild_id = ?",
                           (campaign_id, str(guild_id)))

    def get_active_campaign_id(self, guild_id: int) -> int | None:
        """Pega o ID da campanha ativa para um servidor."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM campaigns WHERE guild_id = ? AND is_active = 1", (str(guild_id),))
            result = cursor.fetchone()
            return result[0] if result else None

    # --- Gerenciamento de Sessão (JSON) ---

    def _load_session_data(self) -> dict:
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_session_data(self):
        with open(self.session_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.session_data, f, indent=4)

    def get_active_session_num(self, guild_id: int, campaign_id: int) -> int:
        """Retorna o número da sessão ativa para uma campanha específica."""
        return self.session_data.get(str(guild_id), {}).get(str(campaign_id), 1)

    def set_active_session_num(self, guild_id: int, campaign_id: int, session_number: int):
        """Define o número da sessão ativa para uma campanha específica."""
        guild_data = self.session_data.get(str(guild_id), {})
        guild_data[str(campaign_id)] = session_number
        self.session_data[str(guild_id)] = guild_data
        self._save_session_data()

    # --- Lógica de Eventos (Agora filtrada por Campanha Ativa) ---

    def log_event(self, guild_id: int, player: discord.Member, action: str, amount: int):
        active_campaign_id = self.get_active_campaign_id(guild_id)
        if not active_campaign_id:
            raise ValueError("Nenhuma campanha ativa definida para este servidor.")

        session_number = self.get_active_session_num(guild_id, active_campaign_id)
        timestamp = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_stats (campaign_id, timestamp, guild_id, session_number, player_name, action, amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (active_campaign_id, timestamp, str(guild_id), session_number, player.display_name, action, amount)
            )
        log.info(f"Log registrado para Campanha {active_campaign_id} por {player.display_name}: {action} - {amount}")

    def get_player_total_stats(self, guild_id: int, player_name: str) -> defaultdict:
        active_campaign_id = self.get_active_campaign_id(guild_id)
        if not active_campaign_id: return defaultdict(int)

        stats = defaultdict(int)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, SUM(amount) FROM session_stats WHERE guild_id = ? AND campaign_id = ? AND player_name = ? GROUP BY action",
                (str(guild_id), active_campaign_id, player_name)
            )
            for action, total_amount in cursor.fetchall():
                stats[action] = total_amount
        return stats

    def get_available_sessions(self, guild_id: int) -> list[tuple[int, str | None]]:
        active_campaign_id = self.get_active_campaign_id(guild_id)
        if not active_campaign_id: return []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT DISTINCT s.session_number, ses.title
                           FROM session_stats s
                                    LEFT JOIN sessions ses
                                              ON s.guild_id = ses.guild_id AND s.campaign_id = ses.campaign_id AND
                                                 s.session_number = ses.session_number
                           WHERE s.guild_id = ?
                             AND s.campaign_id = ?
                           ORDER BY s.session_number DESC
                           """, (str(guild_id), active_campaign_id))
            return cursor.fetchall()

    def get_mvps(self, guild_id: int) -> dict[str, list]:
        active_campaign_id = self.get_active_campaign_id(guild_id)
        if not active_campaign_id: return {}

        mvps = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            actions = ["causado", "recebido", "cura", "eliminacao", "jogador_caido", "critico_sucesso", "critico_falha"]
            for action in actions:
                cursor.execute("""
                               SELECT player_name, SUM(amount) as total
                               FROM session_stats
                               WHERE guild_id = ?
                                 AND campaign_id = ?
                                 AND action = ?
                               GROUP BY player_name
                               ORDER BY total DESC
                               """, (str(guild_id), active_campaign_id, action))
                results = cursor.fetchall()
                if results and results[0][1] > 0:
                    top_score = results[0][1]
                    mvps[action] = ([row[0] for row in results if row[1] == top_score], top_score)
        return mvps

    def end_session(self, guild_id: int, title: str, description: str):
        active_campaign_id = self.get_active_campaign_id(guild_id)
        if not active_campaign_id:
            raise ValueError("Nenhuma campanha ativa definida para este servidor.")

        session_number = self.get_active_session_num(guild_id, active_campaign_id)
        timestamp = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (campaign_id, guild_id, session_number, title, description, end_timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (active_campaign_id, str(guild_id), session_number, title, description, timestamp))

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