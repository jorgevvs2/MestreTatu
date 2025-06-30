# -*- coding: utf-8 -*-
import os
import discord
from discord.ext import commands
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

# --- Configuração Inicial ---
TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')


# --- Bot Class ---
class PinoBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize clients and options here to attach them to the bot instance
        try:
            self.spotify_client = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET)
            )
        except Exception as e:
            self.spotify_client = None
            print(f"Erro ao inicializar o cliente Spotify: {e}. Verifique as credenciais.")

        self.ydl_options = {
            'format': 'bestaudio/best', 'noplaylist': False, 'quiet': True,
            'default_search': 'auto', 'source_address': '0.0.0.0',
            'extractor_args': {'youtube': {'formats': 'missing_pot'}},
        }

        cookie_file_path = 'cookies.txt'
        if os.path.exists(cookie_file_path) and os.path.isfile(cookie_file_path):
            print("INFO: Arquivo de cookies encontrado. Usando para autenticação.")
            self.ydl_options['cookiefile'] = cookie_file_path
        else:
            print(f"AVISO: Arquivo de cookies '{cookie_file_path}' não encontrado ou é um diretório.")

        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

    async def setup_hook(self):
        """This is called when the bot logs in."""
        print("Carregando extensões (cogs)...")
        for filename in os.listdir('cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'  -> Cog {filename} carregado com sucesso.')
                except Exception as e:
                    print(f'  -> Falha ao carregar o cog {filename}: {e}')

    async def on_ready(self):
        """Event that is triggered when the bot is online and ready."""
        print('-----------------------------------------')
        print(f'Bot {self.user.name} está online e pronto!')
        print(f'ID do Bot: {self.user.id}')
        print('-----------------------------------------')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=".play"))


# --- Run the Bot ---
async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True

    bot = PinoBot(command_prefix='.', intents=intents, help_command=None)

    try:
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        print("ERRO: Token inválido. Verifique o token no seu arquivo .env.")
    except Exception as e:
        print(f"Ocorreu um erro ao iniciar o bot: {e}")


if __name__ == "__main__":
    asyncio.run(main())