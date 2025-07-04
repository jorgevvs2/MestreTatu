import os
import random
import discord
from discord.ext import commands, tasks
import asyncio
from dotenv import load_dotenv
import logging
from threading import Thread
from flask import Flask
from waitress import serve
import google.generativeai as genai

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração inicial do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# --- Servidor Web para Health Check ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "MestreTatu health check OK.", 200

def run_web_server():
    """Executa o servidor Flask em uma thread separada usando Waitress."""
    # Render define a porta pela variável de ambiente PORT.
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor web de produção (Waitress) na porta {port}...")
    serve(app, host='0.0.0.0', port=port)

# --- Classe Principal do Bot ---
class TatuBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Inicializando o TatuBot...")
        self.initialize_services()

    def initialize_services(self):
        """Inicializa serviços externos como Gemini."""
        try:
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                log.warning("GEMINI_API_KEY não encontrada. Funcionalidades de IA serão desativadas.")
                self.gemini_pro_model = None
                self.gemini_flash_model = None
            else:
                genai.configure(api_key=gemini_api_key)
                # Usando nomes de modelo válidos e consistentes.
                self.gemini_pro_model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    generation_config={"temperature": 0.2}
                )
                log.info("Modelo Gemini PRO (gemini-2.5-pro) inicializado com sucesso.")
                self.gemini_flash_model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    generation_config={"temperature": 0.0}
                )
                log.info("Modelo Gemini FLASH (gemini-2.5-flash) inicializado com sucesso.")
        except Exception:
            log.error("Falha ao inicializar os modelos Gemini.", exc_info=True)
            self.gemini_pro_model = None
            self.gemini_flash_model = None

    async def setup_hook(self):
        """Hook executado para carregar as extensões (cogs) antes do bot conectar."""
        log.info("Carregando extensões (cogs)...")
        cogs_to_load = [
            'message_cog', 'help_cog', 'rpg_cog',
            'dice_cog', 'lookup_cog', 'logging_cog', 'session_cog', 'initiative_cog'
        ]
        for cog_name in cogs_to_load:
            try:
                await self.load_extension(f'cogs.{cog_name}')
                log.info(f'-> Cog {cog_name}.py carregado com sucesso.')
            except commands.ExtensionNotFound:
                log.warning(f'-> AVISO: Cog {cog_name}.py não encontrado.')
            except Exception:
                log.error(f'-> FALHA ao carregar o cog {cog_name}.py.', exc_info=True)

    async def on_ready(self):
        """Evento executado quando o bot está pronto e online."""
        log.info(f'Logado como {self.user.name} (ID: {self.user.id})')
        log.info('------')
        if not self.change_status.is_running():
            self.change_status.start()

    @tasks.loop(minutes=15)
    async def change_status(self):
        """Muda o status do bot periodicamente para refletir suas várias funções."""
        status_list = [
            "Ouvindo as dúvidas dos aventureiros.",
            "Registrando os feitos da campanha.",
            "Forjando um novo NPC...",
            "Organizando a iniciativa do combate.",
            "Rolando um d20 decisivo..."
        ]
        new_status = random.choice(status_list)
        # Usando discord.Game para uma melhor apresentação do status.
        await self.change_presence(activity=discord.Game(name=new_status))

# --- Função Principal de Execução ---
async def main():
    """Função principal que configura e inicia o bot."""
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        log.critical("ERRO FATAL: DISCORD_TOKEN não foi encontrado. O bot não pode iniciar.")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True
    intents.members = True

    bot = TatuBot(command_prefix='.', intents=intents, help_command=None)

    # --- MELHORIA: Lógica de Retry com Exponential Backoff ---
    # Isso torna o bot mais resiliente a problemas de rede temporários ou rate limits no início.
    max_retries = 5
    retry_delay = 5  # segundos

    for attempt in range(max_retries):
        try:
            # Tenta iniciar o bot. Se for bem-sucedido, o loop é interrompido.
            if attempt > 0:
                log.info(f"Tentando reconectar... (Tentativa {attempt + 1}/{max_retries})")
            await bot.start(TOKEN)
            # Se bot.start() retornar, significa que foi desligado corretamente (ex: por um comando de shutdown).
            # Então, saímos do loop de retry.
            break
        except discord.errors.HTTPException as e:
            # Foco em erros de rede/API como 429 (Too Many Requests) ou 5xx (Server Error)
            if e.status == 429 or e.status >= 500:
                if attempt < max_retries - 1:
                    log.warning(f"Falha ao conectar (HTTP {e.status}). Tentando novamente em {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Aumenta o tempo de espera
                else:
                    log.critical(f"Falha ao conectar após {max_retries} tentativas. Desistindo.", exc_info=True)
                    # Sai do loop após a última tentativa
                    break
            else:
                # Para outros erros HTTP (como 401/403 Login Failure), falha imediatamente.
                log.critical("Erro HTTP não recuperável durante o login.", exc_info=True)
                break
        except discord.errors.LoginFailure:
            log.critical("ERRO DE LOGIN: O token do Discord fornecido é inválido.")
            # Não adianta tentar novamente com um token inválido.
            break
        except Exception as e:
            # Captura outras exceções inesperadas (ex: problemas de rede)
            log.error(f"Ocorreu um erro inesperado ao iniciar o bot: {e}", exc_info=True)
            if attempt < max_retries - 1:
                log.warning(f"Tentando novamente em {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                log.critical(f"Falha ao iniciar após {max_retries} tentativas. Desistindo.")
                break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot desligado pelo usuário.")
