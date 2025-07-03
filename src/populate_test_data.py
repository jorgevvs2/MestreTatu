import csv
import os
import random
from faker import Faker

OUTPUT_FILE = os.path.join("logs", "rpg_session_stats.csv")

NUM_RECORDS = 500

GUILD_ID = "1328755999582195772"

fake = Faker()
player_names = ["Frederick", "Will", "Kairos", "Ambrael", "Modrek"]

PLAYERS = [
    {"id": fake.unique.random_number(digits=18), "name": name}
    for name in player_names
]

SESSIONS = [1, 2, 3, 4, 5]

ACTIONS = {
    "causado": (5, 40),
    "recebido": (2, 30),
    "cura": (4, 25),
    "critico_sucesso": (1, 1),
    "critico_falha": (1, 1),
    "jogador_caido": (1, 1),
    "eliminacao": (1, 1)
}

def generate_fake_data():
    print(f"Gerando {NUM_RECORDS} registros de teste para o servidor ID: {GUILD_ID}...")
    print("Usando os seguintes jogadores de teste:")
    for p in PLAYERS:
        print(f"- {p['name']} (ID: {p['id']})")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    header = ['timestamp', 'guild_id', 'session_number', 'player_id', 'player_name', 'action', 'amount']

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for i in range(NUM_RECORDS):
            player = random.choice(PLAYERS)
            session = random.choice(SESSIONS)
            action = random.choice(list(ACTIONS.keys()))
            amount_range = ACTIONS[action]
            amount = random.randint(amount_range[0], amount_range[1])

            timestamp = fake.date_time_between(start_date="-30d", end_date="now").strftime('%Y-%m-%d %H:%M:%S')

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