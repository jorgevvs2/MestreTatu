# populate_db.py

import sqlite3
import os
import random
from datetime import datetime
# Importa a função de setup do banco de dados
from src.cogs.session_components.database_setup import setup_database

# --- Configuração ---
# O caminho agora aponta para a pasta 'data', que é o volume do Docker
DATA_DIR = 'src/logs/data'
DB_PATH = os.path.join(DATA_DIR, 'stats.db')
GUILD_ID = "1328755999582195772"  # ID de servidor de exemplo. Mude se quiser.
CAMPAIGN_NAME = "Maldição de Strahd"
NUM_SESSIONS = 6  # O número de sessões para espalhar os dados

# Mapeamento dos nomes das estatísticas para os nomes no banco de dados
STATS_MAP = {
    "dano_causado": "causado",
    "dano_recebido": "recebido",
    "cura_realizada": "cura",
    "abates": "eliminacao",
    "quedas": "jogador_caido",
    "falhas_criticas": "critico_falha",  # 1 rolls
    "sucessos_criticos": "critico_sucesso"  # 20 rolls
}

# Dados totais fornecidos
PLAYER_DATA = {
    "Will": {
        "dano_recebido": 122, "dano_causado": 197, "cura_realizada": 10,
        "abates": 6, "quedas": 2, "falhas_criticas": 6, "sucessos_criticos": 7
    },
    "Ambrael": {
        "dano_recebido": 100, "dano_causado": 78, "cura_realizada": 153,
        "abates": 7, "quedas": 2, "falhas_criticas": 1, "sucessos_criticos": 0
    },
    "Kairos": {
        "dano_recebido": 90, "dano_causado": 367, "cura_realizada": 11,
        "abates": 5, "quedas": 2, "falhas_criticas": 6, "sucessos_criticos": 11
    },
    "Mordrek": {
        "dano_recebido": 131, "dano_causado": 129, "cura_realizada": 33,
        "abates": 3, "quedas": 4, "falhas_criticas": 6, "sucessos_criticos": 1
    },
    "Frederick": {
        "dano_recebido": 195, "dano_causado": 145, "cura_realizada": 0,
        "abates": 3, "quedas": 4, "falhas_criticas": 6, "sucessos_criticos": 8
    }
}

# --- NOVO: Resumos das Sessões ---
SESSION_SUMMARIES = {
    1: {
        "title": "Adentrando as Brumas",
        "description": "Os aventureiros ao cumprirem uma missão dada pela Duquesa da cidade de Vau da Adaga, dão de cara com estranhos coloridos que com um convite suspeito acaba com a noite de todos."
    },
    2: {
        "title": "A Casa da Morte",
        "description": "Ao acordar em um local envolto de brumas e sem boa parte de seus pertences, nossos aventureiros exploram as terras frias e escuras da Baróvia, encontrando um casarão sombrio."
    },
    3: {
        "title": "O Fim da Maldição",
        "description": "Investigando a sombria mansão e passando por diversos encontros arrepiantes, nossos heróis encontram um ritual sangrento e acabam com ele definitivamente. Em uma fuga emocionante, a casa da morte se despedaça com sua maldição desfeita, restando apenas o pó e o desanso das almas que sofreram naquele lugar."
    },
    4: {
        "title": "O Vilarejo Amaldiçoado",
        "description": "Após presenciarem o fim da mansão, os aventureiros seguem seu rumo pelas estradas frias da Baróvia, encontrando uma vila triste e sem vida. Sob a sombra do grande castelo a cima da monte, nossos heróis conhecem o filho do burgomestre local, auxiliam no enterro de seu pai, recém falecido e tem uma pequena visitinha a noite..."
    },
    5: {
        "title": "Rumo a Valaki",
        "description": "Com uma missão dada por Ismark, filho do burgomestre, nossos heróis avançam destino a Valaki, a cidade mais segura da Baróvia, com o objetivo de proteger Ireena, irmã mais nova de Ismark. No caminho, ao passar por um mal presságio em um pequeno cemitério à beira da estrada, dão de cara com um grupo de estrangeiros coloridos e recebem uma profecia lida nas cartas de Tarokka. Após um tempo encontram o velho moinho na estrada."
    },
    6: {
        "title": "O Moinho de Vento",
        "description": "Apesar dos repetidos avisos agourentos de um corvo pousado no moinho, nossos heróis decidiram retornar ao local. Eles concluíram que seria mais seguro enfrentar o desconhecido dentro de um abrigo, do que se aventurar pela floresta escura e perigosa durante a noite. Ao chegarem, tiveram um encontro inesperado com um grupo de senhoras que pareciam ser padeiras. Contudo, a descoberta de que elas, na verdade, eram bruxas que usavam crianças em suas receitas, revelou um perigo muito maior do que imaginavam."
    }
}


def distribute_value(total: int, num_parts: int) -> list[int]:
    """Divide um valor total em N partes de forma aleatória."""
    if total == 0:
        return [0] * num_parts

    parts = [0] * num_parts
    for _ in range(total):
        parts[random.randint(0, num_parts - 1)] += 1
    return parts


def populate_database():
    """Popula o banco de dados com dados de exemplo, distribuídos em várias sessões."""
    try:
        # --- 1. Garantir que o DB e as tabelas existam ---
        print("Verificando e preparando o banco de dados...")
        # Chama a função de setup, passando o diretório local 'data'
        setup_database(base_dir=DATA_DIR)
        print("Banco de dados pronto.")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print(f"Conectado ao banco de dados: {DB_PATH}")

        # --- 2. Criar/Limpar a Campanha ---
        print(f"Verificando/Criando a campanha '{CAMPAIGN_NAME}'...")
        cursor.execute("SELECT id FROM campaigns WHERE guild_id = ? AND name = ?", (GUILD_ID, CAMPAIGN_NAME))
        campaign = cursor.fetchone()

        if campaign:
            campaign_id = campaign[0]
            print(f"Campanha '{CAMPAIGN_NAME}' já existe com ID: {campaign_id}. Limpando dados antigos...")
            # Limpa logs e resumos antigos para evitar duplicatas
            cursor.execute("DELETE FROM session_stats WHERE campaign_id = ?", (campaign_id,))
            cursor.execute("DELETE FROM sessions WHERE campaign_id = ?", (campaign_id,))
        else:
            cursor.execute("INSERT INTO campaigns (guild_id, name) VALUES (?, ?)", (GUILD_ID, CAMPAIGN_NAME))
            campaign_id = cursor.lastrowid
            print(f"Campanha '{CAMPAIGN_NAME}' criada com ID: {campaign_id}")

        # --- 3. Inserir os Resumos das Sessões ---
        print("Inserindo resumos das sessões...")
        for session_number, data in SESSION_SUMMARIES.items():
            cursor.execute(
                """
                INSERT INTO sessions (campaign_id, guild_id, session_number, title, description, end_timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (campaign_id, GUILD_ID, session_number, data['title'], data['description'], datetime.utcnow().isoformat())
            )
        print(f"{len(SESSION_SUMMARIES)} resumos de sessão inseridos.")


        # --- 4. Inserir os Dados de Estatísticas Distribuídos ---
        print(f"Inserindo estatísticas dos jogadores distribuídas em {NUM_SESSIONS} sessões...")
        total_entries = 0
        for player_name, stats in PLAYER_DATA.items():
            print(f"  - Processando {player_name}...")
            for stat_key, total_amount in stats.items():
                action = STATS_MAP[stat_key]

                # Distribui o valor total entre as sessões
                distributed_amounts = distribute_value(total_amount, NUM_SESSIONS)

                for i, amount_for_session in enumerate(distributed_amounts):
                    session_number = i + 1

                    # Só insere se o valor para a sessão for maior que zero
                    if amount_for_session > 0:
                        timestamp = datetime.utcnow().isoformat()
                        cursor.execute(
                            """
                            INSERT INTO session_stats
                            (campaign_id, timestamp, guild_id, session_number, player_name, action, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (campaign_id, timestamp, GUILD_ID, session_number, player_name, action, amount_for_session)
                        )
                        total_entries += 1

        conn.commit()
        print(f"\n✅ Sucesso! {total_entries} entradas de estatísticas foram inseridas no banco de dados.")

    except sqlite3.Error as e:
        print(f"🔥 Erro de SQLite: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
    except Exception as e:
        print(f"🔥 Ocorreu um erro inesperado: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")


if __name__ == "__main__":
    populate_database()