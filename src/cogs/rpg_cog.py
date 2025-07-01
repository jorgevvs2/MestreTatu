import os
import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import logging

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)

# --- Configuração ---
try:
    # A API Key é lida das variáveis de ambiente, o que é uma boa prática.
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    log.critical("Não foi possível configurar a API do Gemini. Verifique a GEMINI_API_KEY.", exc_info=True)

# Timeout para a resposta da API, para evitar que o bot fique travado.
QUERY_TIMEOUT = 45  # Segundos


class RPGCog(commands.Cog):
    """Cog que usa o Gemini para responder dúvidas gerais de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Define a "personalidade" do bot para as respostas de RPG.
        self.system_prompt = """
        Você é o Mestre Tatu, um mestre de RPG sábio, criativo e amigável.
        Responda às perguntas dos usuários sobre RPG de forma clara, prestativa e, se apropriado,
        com um toque de criatividade de um mestre de jogo experiente.
        """

        # Configura o modelo do Gemini a ser usado.
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config={"temperature": 0.4} # Temperatura levemente aumentada para respostas mais criativas.
        )
        log.info("RPGCog (modo Gemini direto) inicializado.")

    @commands.command(name='rpg', help='Tira uma dúvida de RPG diretamente com o Mestre Tatu. Uso: .rpg sua pergunta')
    async def rpg_question(self, ctx: commands.Context, *, question: str = None):
        """Recebe uma pergunta de RPG e a envia diretamente para o modelo Gemini."""

        if not question:
            await ctx.reply("Por favor, faça uma pergunta após o comando. Ex: `.rpg como criar um bom vilão?`")
            return

        # Informa ao usuário que o bot está "pensando".
        async with ctx.typing():
            try:
                log.info(f"[{ctx.guild.id}] Comando 'rpg' recebido com a pergunta: '{question[:50]}...'")

                # Envia a pergunta para a API do Gemini, combinando a personalidade e a pergunta do usuário.
                response = await asyncio.wait_for(
                    self.model.generate_content_async([self.system_prompt, question]),
                    timeout=QUERY_TIMEOUT
                )

                # Cria uma resposta bonita (embed) para o Discord.
                embed = discord.Embed(
                    title="Mestre Tatu responde:",
                    description=response.text,
                    color=discord.Color.from_rgb(114, 137, 218) # Azul do Discord
                )
                embed.set_footer(text=f"Dúvida de: {ctx.author.display_name}")

                await ctx.reply(embed=embed)
                log.info(f"[{ctx.guild.id}] Resposta para a pergunta de RPG gerada e enviada com sucesso.")

            except asyncio.TimeoutError:
                log.warning(f"[{ctx.guild.id}] A geração da resposta de RPG excedeu o timeout de {QUERY_TIMEOUT}s.")
                await ctx.reply(f"A geração da resposta demorou mais de {QUERY_TIMEOUT} segundos e foi cancelada. Tente novamente.")
            except Exception as e:
                log.error(f"[{ctx.guild.id}] Falha ao processar a pergunta de RPG.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora. Tente novamente mais tarde.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(RPGCog(bot))