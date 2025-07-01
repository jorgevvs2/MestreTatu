# Dockerfile

# --- Estágio 1: Builder ---
# Usamos um nome "builder" para este estágio. Ele terá as ferramentas
# necessárias para instalar as dependências do Python.
FROM python:3.10-slim as builder

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências de sistema necessárias para a compilação de alguns pacotes Python.
# Embora não sejam estritamente necessárias para as suas dependências atuais,
# é uma boa prática para garantir a compatibilidade.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# Cria um ambiente virtual. Isso isola as dependências da aplicação
# do Python do sistema, tornando o pacote final mais limpo e portátil.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copia apenas o arquivo de requisitos para aproveitar o cache do Docker.
# A instalação só será refeita se este arquivo mudar.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Estágio 2: Final ---
# Começamos de uma imagem limpa e nova. Isso garante que nenhuma
# ferramenta de compilação (como build-essential) chegue à imagem final.
FROM python:3.10-slim

# Força o Python a não usar buffer, garantindo que os logs apareçam em tempo real.
ENV PYTHONUNBUFFERED=1

# Define o diretório de trabalho
WORKDIR /app

# Instala APENAS as dependências de sistema necessárias para a EXECUÇÃO.
# libopus0 é a biblioteca de runtime, mais leve que a libopus-dev do estágio de build.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 procps && \
    rm -rf /var/lib/apt/lists/*

# Cria um usuário não-root para a aplicação. Rodar como root é uma má prática de segurança.
RUN useradd --system --create-home appuser
USER appuser

# Copia o ambiente virtual com as dependências já instaladas do estágio "builder".
COPY --from=builder /opt/venv /opt/venv

# Copia o código da aplicação e os livros.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser rpg_books/ ./rpg_books/

# --- MUDANÇAS PARA PERFORMANCE ---
# Copia o script de entrypoint e o torna executável.
COPY --chown=appuser:appuser entrypoint.sh .
RUN chmod +x ./entrypoint.sh

# Define o PATH para usar o Python do nosso ambiente virtual.
ENV PATH="/opt/venv/bin:$PATH"

# Define o entrypoint para o nosso script de prioridade.
ENTRYPOINT ["./entrypoint.sh"]

# Define o comando PADRÃO que será passado para o entrypoint.
CMD ["python", "src/main.py"]