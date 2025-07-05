# src/cogs/session_components/database_setup.py

import sqlite3
import logging
import os

log = logging.getLogger(__name__)

# Define os caminhos para os arquivos persistentes aqui
DATA_DIR = '/app/src/logs'  # Usando o diretório de volume do Docker
DB_FILE = os.path.join(DATA_DIR, 'stats.db')
SESSION_DATA_FILE = os.path.join(DATA_DIR, 'session_data.json')

def setup_database():
    """Garante que o diretório de dados e as tabelas do banco de dados existam."""
    try:
        # Garante que o diretório de dados exista
        os.makedirs(DATA_DIR, exist_ok=True)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    session_number INTEGER NOT NULL,
                    player_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    session_number INTEGER NOT NULL,
                    title TEXT,
                    description TEXT,
                    end_timestamp TEXT NOT NULL,
                    UNIQUE(guild_id, session_number)
                )
            ''')
        log.info(f"Banco de dados '{DB_FILE}' verificado/criado com sucesso.")
    except Exception as e:
        log.error(f"Falha ao inicializar o banco de dados em '{DB_FILE}': {e}", exc_info=True)