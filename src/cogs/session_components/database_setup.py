# src/cogs/session_components/database_setup.py

import sqlite3
import logging
import os

log = logging.getLogger(__name__)

# O caminho para o volume do Docker permanece o mesmo
DATA_DIR = '/app/data'
DB_FILE = os.path.join(DATA_DIR, 'stats.db')
SESSION_DATA_FILE = os.path.join(DATA_DIR, 'session_data.json') # Agora vai guardar a campanha ativa

def setup_database():
    """Garante que o diretório de dados e as tabelas do banco de dados existam."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # --- NOVA TABELA: Campaigns ---
            # Armazena todas as campanhas e qual está ativa por servidor.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0, -- 1 para True, 0 para False
                    UNIQUE(guild_id, name)
                )
            ''')

            # --- TABELA MODIFICADA: session_stats ---
            # Adicionamos a coluna campaign_id para vincular cada log a uma campanha.
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
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')

            # --- TABELA MODIFICADA: sessions ---
            # Adicionamos a coluna campaign_id para vincular cada resumo de sessão a uma campanha.
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
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
        log.info(f"Banco de dados '{DB_FILE}' verificado/criado com suporte a múltiplas campanhas.")
    except Exception as e:
        log.error(f"Falha ao inicializar o banco de dados em '{DB_FILE}': {e}", exc_info=True)
