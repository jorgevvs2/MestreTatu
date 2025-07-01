import os
import discord
from discord.ext import commands
import google.generativeai as genai
import re
import asyncio
import json
import fitz  # PyMuPDF
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)

# --- Configuração ---
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    log.critical("Não foi possível configurar a API do Gemini. Verifique a GEMINI_API_KEY.", exc_info=True)

# Caminhos relativos ao diretório de trabalho /app definido no Dockerfile.
BOOKS_DIR = "rpg_books"
CACHE_FILE = "rpg_embeddings_cache.json"
QUERY_TIMEOUT = 45  # Segundos


def _chunk_text(text, chunk_size=2000, chunk_overlap=200):
    """Quebra um texto longo em pedaços menores com sobreposição."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


class RPGCog(commands.Cog):
    """Cog que usa RAG com busca semântica para responder dúvidas de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.knowledge_base = {}

        # Prompt para quando um livro é especificado (RAG)
        self.rag_system_prompt = """
        Você é um assistente de regras de RPG. Sua tarefa é responder à pergunta do usuário
        baseando-se estritamente no CONTEXTO fornecido. O CONTEXTO contém os trechos mais
        relevantes de um livro de regras. Não use nenhum conhecimento externo. Se a resposta
        não estiver no CONTEXTO, afirme que não encontrou a informação nos trechos relevantes.
        """

        # NOVO: Prompt para perguntas gerais, sem livro de referência.
        self.general_system_prompt = """
        Você é o Mestre Tatu, um mestre de RPG sábio, criativo e amigável.
        Responda às perguntas dos usuários sobre RPG de forma clara, prestativa e, se apropriado,
        com um toque de criatividade de um mestre de jogo experiente.
        """

        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config={"temperature": 0.2}  # Um pouco mais de criatividade para o modo geral
        )
        log.info("RPGCog inicializado.")

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self, cache_data):
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)

    async def cog_load(self):
        """Processa os PDFs, cria embeddings e os armazena em cache."""
        log.info("[RPGCog] Iniciando verificação e indexação de livros...")
        if not os.path.exists(BOOKS_DIR):
            os.makedirs(BOOKS_DIR)
            return

        cache = self._load_cache()
        updated_cache = {}

        for filename in os.listdir(BOOKS_DIR):
            if not filename.lower().endswith('.pdf'):
                continue

            file_path = os.path.join(BOOKS_DIR, filename)
            file_key = os.path.splitext(filename.lower())[0]
            file_mod_time = str(os.path.getmtime(file_path))

            if file_key in cache and cache[file_key]['mod_time'] == file_mod_time:
                log.info(f"[RPGCog] Carregando '{file_key}' do cache.")
                self.knowledge_base[file_key] = {
                    'chunks': cache[file_key]['chunks'],
                    'embeddings': np.array(cache[file_key]['embeddings'])
                }
                updated_cache[file_key] = cache[file_key]
            else:
                log.info(f"[RPGCog] Processando e criando embeddings para '{filename}'...")
                try:
                    doc = fitz.open(file_path)
                    full_text = "".join(page.get_text() for page in doc)
                    doc.close()

                    text_chunks = _chunk_text(full_text)

                    result = await genai.embed_content_async(
                        model="models/text-embedding-004",
                        content=text_chunks,
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                    embeddings = result['embedding']

                    self.knowledge_base[file_key] = {
                        'chunks': text_chunks,
                        'embeddings': np.array(embeddings)
                    }
                    updated_cache[file_key] = {
                        'mod_time': file_mod_time,
                        'chunks': text_chunks,
                        'embeddings': np.array(embeddings).tolist()
                    }
                    log.info(f"[RPGCog] Livro '{file_key}' processado e salvo no cache.")
                except Exception as e:
                    log.error(f"[RPGCog] Falha ao processar '{filename}'.", exc_info=True)

        self._save_cache(updated_cache)
        log.info(f"[RPGCog] Indexação concluída. Livros disponíveis: {list(self.knowledge_base.keys())}")

    async def _find_top_chunks(self, book_key, question, top_k=3):
        """Encontra os chunks de texto mais relevantes para uma pergunta."""
        if book_key not in self.knowledge_base:
            return None

        result = await genai.embed_content_async(
            model="models/text-embedding-004",
            content=question,
            task_type="RETRIEVAL_QUERY"
        )

        if not result.get('embedding'):
            log.warning(f"A API não retornou um embedding para a pergunta: '{question}'")
            return None

        question_embedding = np.array(result['embedding']).reshape(1, -1)
        book_data = self.knowledge_base[book_key]
        similarities = cosine_similarity(question_embedding, book_data['embeddings'])[0]
        top_indices = similarities.argsort()[-top_k:][::-1]

        return [book_data['chunks'][i] for i in top_indices]

    # AJUDA DO COMANDO ATUALIZADA
    @commands.command(name='rpg', help='Tira uma dúvida de RPG. Use: .rpg ["livro"] pergunta')
    async def rpg_question(self, ctx: commands.Context, *, query: str):
        # REGEX ATUALIZADA: Torna o grupo do livro opcional.
        # Captura (livro, pergunta) ou (None, pergunta).
        match = re.match(r'(?:["\'](.*?)["\']\s+)?(.*)', query, re.DOTALL)

        if not match or not match.group(2).strip():
            available_books = ", ".join(f"`{key}`" for key in self.knowledge_base.keys())
            await ctx.reply(f'Formato inválido! Use: `.rpg ["nome_do_livro"] sua pergunta`\n'
                            f'Livros disponíveis: {available_books or "Nenhum livro indexado."}')
            return

        book_key, question = match.groups()

        async with ctx.typing():
            try:
                # --- CAMINHO 1: PERGUNTA COM LIVRO (RAG) ---
                if book_key:
                    book_key = book_key.lower()
                    log.info(f"[{ctx.guild.id}] Comando 'rpg' com livro: '{book_key}', pergunta: '{question[:30]}...'")

                    if book_key not in self.knowledge_base:
                        available_books = ", ".join(f"`{key}`" for key in self.knowledge_base.keys())
                        await ctx.reply(f'O livro "{book_key}" não foi encontrado. \n'
                                        f'Livros disponíveis: {available_books or "Nenhum livro indexado."}')
                        return

                    log.debug(f"[{ctx.guild.id}] Buscando chunks relevantes...")
                    relevant_chunks = await self._find_top_chunks(book_key, question)
                    if not relevant_chunks:
                        await ctx.reply("Não foi possível encontrar trechos relevantes para sua busca nesse livro.")
                        return

                    context = "\n---\n".join(relevant_chunks)
                    final_prompt = f"CONTEXTO:\n{context}\n\nPERGUNTA:\n{question}"

                    log.debug(f"[{ctx.guild.id}] Gerando resposta com base no contexto encontrado...")
                    response = await asyncio.wait_for(
                        self.model.generate_content_async([self.rag_system_prompt, final_prompt]),
                        timeout=QUERY_TIMEOUT
                    )

                    embed = discord.Embed(
                        title=f"Mestre Tatu responde sobre: {book_key.title()}",
                        color=discord.Color.from_rgb(79, 84, 166)
                    )
                    embed.set_footer(text=f"Fonte: {book_key}.pdf | Dúvida de: {ctx.author.display_name}")

                # --- CAMINHO 2: PERGUNTA GERAL (DIRETO AO GEMINI) ---
                else:
                    log.info(f"[{ctx.guild.id}] Comando 'rpg' geral, pergunta: '{question[:30]}...'")

                    log.debug(f"[{ctx.guild.id}] Enviando pergunta geral para o Gemini...")
                    response = await asyncio.wait_for(
                        self.model.generate_content_async([self.general_system_prompt, question]),
                        timeout=QUERY_TIMEOUT
                    )

                    embed = discord.Embed(
                        title="Mestre Tatu responde:",
                        color=discord.Color.from_rgb(114, 137, 218)  # Cor diferente para o modo geral
                    )
                    embed.set_footer(text=f"Conhecimento geral | Dúvida de: {ctx.author.display_name}")

                # --- Envio da Resposta (Comum aos dois caminhos) ---
                embed.description = response.text
                await ctx.reply(embed=embed)
                log.info(f"[{ctx.guild.id}] Resposta para a pergunta de RPG gerada e enviada com sucesso.")

            except asyncio.TimeoutError:
                log.warning(f"[{ctx.guild.id}] A geração da resposta de RPG excedeu o timeout de {QUERY_TIMEOUT}s.")
                await ctx.reply(f"A geração da resposta demorou mais de {QUERY_TIMEOUT} segundos e foi cancelada.")
            except Exception as e:
                log.error(f"[{ctx.guild.id}] Falha ao processar a pergunta de RPG.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora.")


async def setup(bot: commands.Bot):
    await bot.add_cog(RPGCog(bot))