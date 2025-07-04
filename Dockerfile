# --- Estágio 1: Builder ---
# Usamos uma imagem completa para ter as ferramentas de build necessárias para o pip.
FROM python:3.10 as builder

# Define o diretório de trabalho
WORKDIR /app

# Instala as dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt

# Copia o resto do código da aplicação
COPY src/ ./src/


# --- Estágio 2: Final ---
# Usamos a imagem 'slim' que é muito menor, pois não precisamos mais das ferramentas de build.
FROM python:3.10-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia apenas as dependências já instaladas do estágio 'builder'
COPY --from=builder /install /usr/local

# Copia apenas o código-fonte necessário do estágio 'builder'
COPY --from=builder /app/src ./src

# Expõe a porta para o health check
EXPOSE 8080

# Define o comando para rodar a aplicação
CMD ["python", "src/main.py"]