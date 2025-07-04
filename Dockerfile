# Dockerfile

# Use an official, slim Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container to /app
WORKDIR /app

# --- CORREÇÃO: Instalar dependências do sistema (wget) ---
# Atualiza a lista de pacotes e instala o wget.
# O -y confirma automaticamente, e a limpeza no final reduz o tamanho da imagem.
RUN apt-get update && \
    apt-get install -y wget && \
    rm -rf /var/lib/apt/lists/* \

# Copy all project files from the current directory on the host
# to the /app directory in the container.
# This is the most robust way to ensure start.sh, requirements.txt,
# and the src/ folder are all included.
COPY . .

# Install the Python dependencies from requirements.txt
# The --no-cache-dir flag makes the final image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Make sure the start script is executable inside the container.
# This is a more reliable method than relying on Git permissions,
# as it happens during the image build itself.
RUN chmod +x ./start.sh

# Command to run when the container launches.
# There should only be ONE CMD instruction.
CMD ["./start.sh"]