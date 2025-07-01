# Dockerfile Otimizado para Google Cloud Run

# --- Estágio 1: Builder ---
# Esta parte permanece a mesma, pois é uma excelente prática.
FROM python:3.10-slim as builder

WORKDIR /app

# Copia apenas o requirements.txt para aproveitar o cache do Docker.
COPY requirements.txt .

# Instala as dependências em um ambiente virtual.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt


# --- Estágio 2: Final ---
# A imagem base é a mesma, garantindo um ambiente enxuto.
FROM python:3.10-slim

# Garante que os logs apareçam em tempo real.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala APENAS as dependências de sistema estritamente necessárias para a EXECUÇÃO.
# 'procps' (que continha o 'nice') foi removido por ser desnecessário no Cloud Run.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 && \
    rm -rf /var/lib/apt/lists/*

# Cria um usuário não-root para segurança.
RUN useradd --system --create-home appuser
USER appuser

# Copia o ambiente virtual com as dependências já instaladas do estágio "builder".
COPY --from=builder /opt/venv /opt/venv

# Copia apenas o código-fonte da aplicação.
# A pasta 'rpg_books' foi removida, pois não é mais utilizada.
COPY --chown=appuser:appuser src/ ./src/

# Define o PATH para usar o Python do nosso ambiente virtual.
ENV PATH="/opt/venv/bin:$PATH"

# Define o comando que será executado quando o contêiner iniciar.
# Removemos a referência ao 'entrypoint.sh' para simplificar.
CMD ["python", "src/main.py"]