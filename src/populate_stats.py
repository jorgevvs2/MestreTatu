import csv
import random
from datetime import datetime

# --- DADOS TOTAIS (COPIADOS DA SUA MENSAGEM) ---
total_data = {
    "Dano tomado": {"W": 122, "A": 100, "K": 90, "M": 131, "F": 195},
    "Dano causado": {"W": 197, "A": 78, "K": 367, "M": 129, "F": 145},
    "Dano curado": {"W": 10, "A": 153, "K": 11, "M": 33, "F": 0},
    "Abates": {"W": 6, "A": 7, "K": 5, "M": 3, "F": 3},
    "Quedas": {"W": 2, "A": 2, "K": 2, "M": 4, "F": 4},
    "1 rolls": {"W": 6, "A": 1, "K": 6, "M": 6, "F": 6},
    "20 rolls": {"W": 7, "A": 0, "K": 11, "M": 1, "F": 8}
}

# --- CONFIGURAÇÕES (MODIFIQUE AQUI) ---
NUMBER_OF_SESSIONS = 6

# Defina o ID do seu servidor do Discord.
# (Clique com o botão direito no nome do servidor -> "Copiar ID do Servidor")
GUILD_ID = 1328755999582195772  # !!! SUBSTITUA PELO SEU ID REAL !!!

# Nome do arquivo CSV que será gerado.
OUTPUT_CSV_FILE = "logs/rpg_session_stats.csv"

# --- MAPEAMENTOS (NÃO PRECISA MUDAR) ---
name_map = {
    "W": "Will", "A": "Ambrael", "K": "Kairos", "M": "Mordrek", "F": "Fred"
}

action_map = {
    "Dano tomado": "recebido",
    "Dano causado": "causado",
    "Dano curado": "cura",
    "Abates": "eliminacao",
    "Quedas": "jogador_caido",
    "1 rolls": "critico_falha",
    "20 rolls": "critico_sucesso"
}


# --- LÓGICA DO SCRIPT ---

def split_integer_randomly(total: int, parts: int) -> list[int]:
    """Divide um número inteiro em N partes aleatórias que somam o total."""
    if total == 0:
        return [0] * parts
    if parts == 1:
        return [total]

    # Gera N-1 pontos de corte aleatórios
    cuts = sorted([random.randint(0, total) for _ in range(parts - 1)])

    # Adiciona 0 no início e o total no final para criar os intervalos
    all_points = [0] + cuts + [total]

    # Calcula a diferença entre os pontos de corte para obter as partes
    result = [all_points[i + 1] - all_points[i] for i in range(parts)]

    return result


def generate_distributed_csv():
    """Gera o arquivo CSV com os dados distribuídos aleatoriamente."""
    all_csv_rows = []

    print("Iniciando distribuição de estatísticas...")

    # Itera sobre cada categoria (ex: "Dano tomado")
    for category, player_stats in total_data.items():
        action_name = action_map.get(category)
        if not action_name:
            continue

        # Itera sobre cada jogador dentro da categoria (ex: "W": 122)
        for initial, total_amount in player_stats.items():
            player_name = name_map.get(initial)
            if not player_name:
                continue

            # Divide o valor total do jogador em N partes aleatórias
            distributed_amounts = split_integer_randomly(total_amount, NUMBER_OF_SESSIONS)

            # Para cada parte, cria uma linha no CSV para a sessão correspondente
            for i, amount_for_session in enumerate(distributed_amounts):
                session_number = i + 1

                # Só adiciona a linha se o valor for maior que zero, para manter o CSV limpo
                if amount_for_session > 0:
                    row = {
                        'timestamp': datetime.now().isoformat(),
                        'guild_id': GUILD_ID,
                        'session_number': session_number,
                        'player_id': 0,  # Placeholder, não é essencial para os gráficos
                        'player_name': player_name,
                        'action': action_name,
                        'amount': amount_for_session
                    }
                    all_csv_rows.append(row)

    # Escreve todas as linhas geradas no arquivo CSV
    try:
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            header = ['timestamp', 'guild_id', 'session_number', 'player_id', 'player_name', 'action', 'amount']
            writer = csv.DictWriter(f, fieldnames=header)

            writer.writeheader()
            writer.writerows(all_csv_rows)

        print(f"\n✅ Sucesso! O arquivo '{OUTPUT_CSV_FILE}' foi criado com {len(all_csv_rows)} registros.")
        print("Os dados foram distribuídos aleatoriamente entre as sessões 1 e 6.")

    except IOError as e:
        print(f"\n❌ Erro ao escrever o arquivo: {e}")


# Executa a função principal
if __name__ == "__main__":
    generate_distributed_csv()