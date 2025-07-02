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
from waitress import serve
import google.generativeai as genai


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
    serve(app, host='0.0.0.0', port=port)

class TatuBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Inicializando o TatuBot...")

        try:
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                log.warning("GEMINI_API_KEY não encontrada. Funcionalidades de IA serão desativadas.")
                self.gemini_pro_model = None
                self.gemini_flash_model = None
            else:
                genai.configure(api_key=gemini_api_key)

                # --- CORREÇÃO: Usando nomes de modelo válidos e estáveis ---
                # Modelo PRO para tarefas complexas (RPG)
                self.gemini_pro_model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    generation_config={"temperature": 0.2}
                )
                log.info("Modelo Gemini PRO (gemini-2.5-pro-latest) inicializado com sucesso.")

                # Modelo FLASH para tarefas rápidas (Extração de Keyword)
                self.gemini_flash_model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    generation_config={"temperature": 0.0}
                )
                log.info("Modelo Gemini FLASH (gemini-2.5-flash-latest) inicializado com sucesso.")

        except Exception as e:
            log.error("Falha ao inicializar os modelos Gemini.", exc_info=True)
            self.gemini_pro_model = None
            self.gemini_flash_model = None

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
            'extractor_retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
            }
        }
        log.debug(f"Opções do YDL configuradas: {self.ydl_options}")

        cookie_file_path = 'cookies.txt'
        if os.path.exists(cookie_file_path) and os.path.isfile(cookie_file_path):
            log.info("Arquivo de cookies encontrado. Usando para autenticação.")
            self.ydl_options['cookiefile'] = cookie_file_path
        else:
            log.info(
                f"Arquivo de cookies '{cookie_file_path}' não encontrado. Continuando sem autenticação de cookies.")

        self.ffmpeg_options = {
            'before_options': (
                '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 '
                '-reconnect_on_http_error 4xx,5xx '
                '-reconnect_delay_max 15'
            ),
            'options': '-vn -loglevel warning -nostats',
        }
        log.debug(f"Opções do FFmpeg configuradas: {self.ffmpeg_options}")


    async def setup_hook(self):
        """Chamado quando o bot faz login, para carregar as extensões."""
        log.info("Carregando extensões (cogs)...")
        cogs_to_load = ['message_cog', 'help_cog', 'music_cog', 'rpg_cog', 'stations_cog', 'dice_cog', 'lookup_cog']
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
        await self.change_presence(activity=discord.CustomActivity(name="Comendo cu de curioso..."))

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

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