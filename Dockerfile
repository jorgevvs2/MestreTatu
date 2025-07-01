# Dockerfile otimizado para desenvolvimento local com Docker Desktop

# --- CORREÇÃO: Usando a base 'bookworm' para obter um FFmpeg mais recente ---
# Usamos a imagem completa do Python para ter um ambiente mais robusto
# e com mais ferramentas de build e depuração disponíveis.
FROM python:3.10.13-bookworm

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# Garante que os logs do Python apareçam em tempo real.
ENV PYTHONUNBUFFERED=1

# Instala as dependências de sistema necessárias (FFmpeg, etc.).
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências para dentro do contêiner.
# A imagem só será reconstruída se este arquivo mudar.
COPY requirements.txt .

# Instala as dependências do Python.
RUN pip install --no-cache-dir -r requirements.txt

# Cria um usuário não-root para rodar a aplicação (boa prática de segurança).
RUN useradd --system --create-home appuser
USER appuser

# O código-fonte será montado como um volume, então não usamos COPY src/ aqui.
# O CMD inicia o bot quando o contêiner é executado.
CMD ["python", "src/main.py"]