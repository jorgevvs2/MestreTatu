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
from threading import Thread
from flask import Flask
from waitress import serve # <--- ADD THIS LINE

# Carrega as variáveis de ambiente do arquivo .env (this is fine for local testing)
load_dotenv()

# Configura um logger para o bot principal
log = logging.getLogger(__name__)

# --- LÓGICA DO SERVIDOR WEB (PARA CLOUD RUN) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    """Endpoint que o Cloud Run usará para verificar se o contêiner está vivo."""
    return "TatuBeats health check OK.", 200

def run_web_server():
    """Função que será executada na thread secundária."""
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor web de produção (Waitress) na porta {port}...")
    # Agora a função 'serve' está definida e funcionará corretamente.
    serve(app, host='0.0.0.0', port=port)

# --- Bot Class ---
class TatuBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Inicializando o TatuBot...")

        # --- CORREÇÃO: Obtenha as variáveis de ambiente AQUI, no momento da inicialização ---
        try:
            spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
            spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

            if not spotify_id or not spotify_secret:
                log.warning("Credenciais do Spotify não encontradas. A funcionalidade de playlist do Spotify será desativada.")
                self.spotify_client = None
            else:
                self.spotify_client = spotipy.Spotify(
                    auth_manager=SpotifyClientCredentials(
                        client_id=spotify_id,
                        client_secret=spotify_secret
                    )
                )
                # Test the credentials to ensure they are valid
                self.spotify_client.search(q='test', type='track', limit=1)
                log.info("Cliente Spotify inicializado e autenticado com sucesso.")

        except Exception as e:
            self.spotify_client = None
            log.error(f"Erro ao inicializar o cliente Spotify. Verifique as credenciais ou a API.", exc_info=True)

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
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    # --- CORREÇÃO: Obtenha o token do bot aqui ---
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        log.critical("ERRO FATAL: DISCORD_TOKEN não foi encontrado nas variáveis de ambiente. O bot não pode iniciar.")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True

    bot = TatuBot(command_prefix='.', intents=intents, help_command=None)

    try:
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        log.critical("ERRO DE LOGIN: O token do Discord fornecido é inválido.")
    except Exception as e:
        log.critical("Ocorreu um erro fatal ao iniciar o bot.", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())