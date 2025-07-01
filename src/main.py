# D:/Codes/TatuBeats/src/main.py

# -*- coding: utf-8 -*-
import os
import discord
from discord.ext import commands
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import logging
from threading import Thread # Importe a classe Thread
from flask import Flask # Importe o Flask

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração Inicial ---
TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Configura um logger para o bot principal
log = logging.getLogger(__name__)

# --- LÓGICA DO SERVIDOR WEB (PARA CLOUD RUN) ---
# Cria uma instância simples do Flask
app = Flask(__name__)

@app.route('/')
def health_check():
    """Endpoint que o Cloud Run usará para verificar se o contêiner está vivo."""
    return "TatuBeats health check OK.", 200

def run_web_server():
    """Função que será executada na thread secundária."""
    # O Cloud Run define a variável de ambiente PORT.
    # O servidor deve escutar em 0.0.0.0 para ser acessível de fora do contêiner.
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor web para health checks na porta {port}...")
    app.run(host='0.0.0.0', port=port)

# --- Bot Class (sem alterações) ---
class TatuBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Inicializando o TatuBot...")

        # ... (o resto do seu __init__ permanece exatamente o mesmo) ...
        try:
            self.spotify_client = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET)
            )
            log.info("Cliente Spotify inicializado com sucesso.")
        except Exception as e:
            self.spotify_client = None
            log.error(f"Erro ao inicializar o cliente Spotify: {e}. Verifique as credenciais.", exc_info=True)

        self.ydl_options = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'quiet': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'ignoreerrors': True,
            'force_ipv4': True,
        }
        log.debug(f"Opções do YDL configuradas: {self.ydl_options}")

        cookie_file_path = 'cookies.txt'
        if os.path.exists(cookie_file_path) and os.path.isfile(cookie_file_path):
            log.info("Arquivo de cookies encontrado. Usando para autenticação.")
            self.ydl_options['cookiefile'] = cookie_file_path
        else:
            log.info(f"Arquivo de cookies '{cookie_file_path}' não encontrado. Continuando sem autenticação de cookies.")

        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -loglevel error -nostats',
        }
        log.debug(f"Opções do FFmpeg configuradas: {self.ffmpeg_options}")


    async def setup_hook(self):
        """Chamado quando o bot faz login, para carregar as extensões."""
        log.info("Carregando extensões (cogs)...")
        cogs_to_load = ['message_cog', 'help_cog', 'music_cog', 'rpg_cog']
        for cog_name in cogs_to_load:
            try:
                await self.load_extension(f'cogs.{cog_name}')
                log.info(f'-> Cog {cog_name}.py carregado com sucesso.')
            except commands.ExtensionNotFound:
                log.warning(f'-> AVISO: Cog {cog_name}.py não encontrado.')
            except Exception as e:
                log.error(f'-> FALHA ao carregar o cog {cog_name}.py.', exc_info=True)

    async def on_ready(self):
        """Evento acionado quando o bot está online e pronto."""
        log.info('-----------------------------------------')
        log.info(f'Bot {self.user.name} está online e pronto!')
        log.info(f'ID do Bot: {self.user.id}')
        log.info('-----------------------------------------')
        await self.change_presence(activity=discord.Game(name="a vida fora..."))


# --- Executa o Bot ---
async def main():
    # Configuração do logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- INICIA A THREAD DO SERVIDOR WEB ---
    # A thread é 'daemon' para que ela termine automaticamente quando o bot principal parar.
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True

    bot = TatuBot(command_prefix='.', intents=intents, help_command=None)

    try:
        # O bot inicia e roda na thread principal
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        log.critical("ERRO DE LOGIN: Token inválido. Verifique o token no seu arquivo .env.")
    except Exception as e:
        log.critical("Ocorreu um erro fatal ao iniciar o bot.", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())