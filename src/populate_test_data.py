import csv
import os
import random
from datetime import datetime, timedelta
from faker import Faker

# --- CONFIGURAÇÃO DO SCRIPT ---

# --- CORREÇÃO AQUI: O caminho agora inclui a pasta 'src' ---
# Caminho para o arquivo CSV que será gerado. Deve ser o mesmo usado no seu cog.
OUTPUT_FILE = os.path.join("logs", "rpg_session_stats.csv")

# Quantidade de registros de eventos que você quer criar.
NUM_RECORDS = 500

# ID do seu servidor do Discord.
# Para obter: Ative o Modo Desenvolvedor no Discord (Configurações > Avançado),
# depois clique com o botão direito no ícone do seu servidor e "Copiar ID do Servidor".
GUILD_ID = "1328755999582195772"  # <-- SUBSTITUA PELO ID REAL DO SEU SERVIDOR

# --- Usando os nomes de jogadores que você pediu ---
fake = Faker() # Usado apenas para gerar IDs únicos
player_names = ["Frederick", "Will", "Kairos", "Ambrael", "Modrek"]

PLAYERS = [
    {"id": fake.unique.random_number(digits=18), "name": name}
    for name in player_names
]

# Sessões que serão usadas nos registros.
SESSIONS = [1, 2, 3, 4, 5]

# Ações possíveis e o range de valores para cada uma.
# Para eventos (como críticos), o valor será sempre 1.
ACTIONS = {
    "causado": (5, 40),
    "recebido": (2, 30),
    "cura": (4, 25),
    "critico_sucesso": (1, 1),
    "critico_falha": (1, 1),
    "jogador_caido": (1, 1),
    "eliminacao": (1, 1)
}

# --- LÓGICA DE GERAÇÃO ---

def generate_fake_data():
    """Gera os dados e escreve no arquivo CSV."""
    print(f"Gerando {NUM_RECORDS} registros de teste para o servidor ID: {GUILD_ID}...")
    print("Usando os seguintes jogadores de teste:")
    for p in PLAYERS:
        print(f"- {p['name']} (ID: {p['id']})")

    # Garante que o diretório de logs exista
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    header = ['timestamp', 'guild_id', 'session_number', 'player_id', 'player_name', 'action', 'amount']

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header) # Escreve o cabeçalho

        for i in range(NUM_RECORDS):
            # Escolhe dados aleatórios baseados na configuração
            player = random.choice(PLAYERS)
            session = random.choice(SESSIONS)
            action = random.choice(list(ACTIONS.keys()))
            amount_range = ACTIONS[action]
            amount = random.randint(amount_range[0], amount_range[1])

            # Gera um timestamp aleatório nos últimos 30 dias
            timestamp = fake.date_time_between(start_date="-30d", end_date="now").strftime('%Y-%m-%d %H:%M:%S')

            # Monta a linha do CSV
            row = [
                timestamp,
                GUILD_ID,
                session,
                player['id'],
                player['name'],
                action,
                amount
            ]
            writer.writerow(row)

    print(f"\n✅ Sucesso! O arquivo '{OUTPUT_FILE}' foi populado com {NUM_RECORDS} registros.")
    print("Agora você pode usar os comandos .stats e .sessionstats no seu servidor para testar.")

if __name__ == "__main__":
    if GUILD_ID == "123456789012345678":
        print("⚠️ ATENÇÃO: Por favor, edite o script e substitua o valor da variável GUILD_ID pelo ID do seu servidor.")
    else:
        generate_fake_data()