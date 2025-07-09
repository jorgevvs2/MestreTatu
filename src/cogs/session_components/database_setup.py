# src/cogs/session_components/database_setup.py

import sqlite3
import logging
import os

log = logging.getLogger(__name__)

# As constantes de caminho foram movidas para dentro da função para permitir
# que ela seja usada com caminhos diferentes fora do container.

def setup_database(base_dir: str | None = None):
    """
    Garante que o diretório de dados e as tabelas do banco de dados existam.
    Pode receber um diretório base para ser usado fora do container (ex: para scripts).
    """
    # Define o diretório de dados. Usa o padrão do container se nenhum for fornecido.
    data_dir = base_dir if base_dir is not None else '/app/data'
    db_file = os.path.join(data_dir, 'stats.db')

    try:
        os.makedirs(data_dir, exist_ok=True)

        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()

            # Habilita foreign keys para garantir a integridade dos dados (ex: ON DELETE CASCADE)
            cursor.execute("PRAGMA foreign_keys = ON;")

            # --- TABELA DE CAMPANHAS SIMPLIFICADA ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0, -- 1 para True, 0 para False
                    UNIQUE(guild_id, name)
                )
            ''')

            # --- TABELA MODIFICADA: session_stats ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    session_number INTEGER NOT NULL,
                    player_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')

            # --- TABELA MODIFICADA: sessions ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    guild_id TEXT NOT NULL,
                    session_number INTEGER NOT NULL,
                    title TEXT,
                    description TEXT,
                    end_timestamp TEXT NOT NULL,
                    UNIQUE(guild_id, campaign_id, session_number),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')

        log.info(f"Banco de dados '{db_file}' verificado/criado com suporte a múltiplas campanhas.")
    except Exception as e:
        log.error(f"Falha ao inicializar o banco de dados em '{db_file}': {e}", exc_info=True)
