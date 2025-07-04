import discord
from discord.ext import commands
import logging
import os
import asyncio
import re

# --- Constantes ---
log = logging.getLogger(__name__)
RULES_FILE = 'src/rpg_books/compiled_rules.txt'
CONTEXT_WINDOW_SIZE = 400  # Caracteres antes e depois da palavra-chave para formar o contexto.
QUERY_TIMEOUT = 120  # Segundos de timeout para a resposta da IA.


class RpgCog(commands.Cog, name="Ferramentas de RPG"):
    """Cog para os comandos de RPG que utilizam IA, como consulta de regras e geração de NPCs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Acessa os modelos de IA inicializados no main.py
        self.rules_model = bot.gemini_pro_model
        self.keyword_model = bot.gemini_flash_model
        self.npc_model = bot.gemini_pro_model # Assuming you want to use the pro model for NPCs as well
        self.system_prompt_rules = (
            "Você é o Mestre Tatu, um mestre de Dungeons & Dragons 5e amigável e experiente. "
            "Sua tarefa é responder perguntas sobre as regras do jogo de forma clara, concisa e amigável para iniciantes. "
            "Use os trechos de regras fornecidos como base principal para sua resposta."
        )
        # Carrega as regras na memória uma única vez para otimizar o desempenho.
        self.rules_text = None
        # + Cria um Lock para evitar race conditions no carregamento do arquivo de regras.
        self._rules_lock = asyncio.Lock()

    async def _ensure_rules_loaded(self):
        """
        Garante que as regras foram carregadas, usando um Lock para ser seguro
        em ambientes com múltiplas chamadas concorrentes.
        """
        # + A verificação rápida acontece antes de adquirir o lock para máxima performance.
        if self.rules_text is not None:
            return

        # + Adquire o lock. Apenas uma corrotina pode passar daqui por vez.
        async with self._rules_lock:
            # + Verifica novamente, pois outra corrotina pode ter carregado o texto
            #   enquanto esta esperava pelo lock.
            if self.rules_text is None:
                log.info("Primeira chamada do comando .rpg, carregando regras na memória...")
                self.rules_text = self._load_rules()

    def _load_rules(self) -> str | None:
        """
        Carrega o arquivo de regras pré-processado na memória.
        Isso evita a leitura de arquivos em disco a cada comando, otimizando a performance.
        """
        if not os.path.exists(RULES_FILE):
            log.warning(f"Arquivo de regras '{RULES_FILE}' não encontrado. A busca local de regras está desativada.")
            log.warning("Lembre-se de executar o script 'src/utils/preprocess_pdfs.py' para gerar o arquivo de regras.")
            return "" # Retorna uma string vazia para evitar checagens de None repetidas.
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                log.info(f"Arquivo de regras '{RULES_FILE}' carregado com sucesso na memória.")
                return f.read()
        except Exception as e:
            log.error(f"Falha ao carregar o arquivo de regras '{RULES_FILE}': {e}", exc_info=True)
            return ""

    async def _extract_keyword(self, question: str) -> str:
        """Usa um modelo de IA mais rápido para extrair o termo principal da pergunta."""
        if not self.keyword_model:
            # Fallback para uma extração simples se a IA não estiver disponível.
            return question.strip().split()[0]

        prompt = (
            f"Extraia o termo ou conceito principal de D&D 5e da seguinte pergunta. "
            f"Responda apenas com o termo, em no máximo 3 palavras. Exemplo: 'Magias de Nível 1'.\n\n"
            f"Pergunta: \"{question}\"\n\nTermo principal:"
        )
        try:
            response = await self.keyword_model.generate_content_async(prompt)
            return response.text.strip().title()
        except Exception:
            log.error("Falha ao extrair palavra-chave com a IA. Usando fallback.", exc_info=True)
            # Em caso de erro, usa a primeira palavra como fallback.
            return question.strip().split()[0]

    def _search_rules_for_term(self, term: str) -> list[str]:
        """
        Busca o termo no texto de regras carregado em memória.
        Retorna uma lista de trechos de texto contendo o termo.
        """
        if not self.rules_text:
            return []

        excerpts = []
        # re.finditer é um iterador eficiente que não carrega todas as correspondências na memória de uma vez.
        try:
            # Limita o número de trechos para evitar sobrecarregar o prompt da IA
            for match in re.finditer(re.escape(term), self.rules_text, re.IGNORECASE):
                start_index = max(0, match.start() - CONTEXT_WINDOW_SIZE)
                end_index = min(len(self.rules_text), match.end() + CONTEXT_WINDOW_SIZE)
                snippet = self.rules_text[start_index:end_index]
                excerpts.append(f"...{snippet}...")
                if len(excerpts) >= 3: # Limita a 3 trechos para performance
                    break
            return excerpts
        except Exception as e:
            log.error(f"Erro ao buscar o termo '{term}' nas regras: {e}")
            return []

    @commands.command(name='rpg', help='Tira uma dúvida de D&D com o Mestre Tatu. Uso: .rpg sua pergunta')
    async def rpg_question(self, ctx: commands.Context, *, question: str = None):
        """Recebe uma pergunta de RPG, busca o termo chave no arquivo de regras e gera uma resposta contextualizada."""
        if not self.rules_model:
            await ctx.reply("Desculpe, minha conexão com os planos astrais (API do Gemini) não está funcionando.")
            return

        if not question:
            await ctx.reply("Por favor, faça uma pergunta após o comando. Ex: `.rpg Vantagem`")
            return

        async with ctx.typing():
            # Garante que as regras estão carregadas de forma segura
            await self._ensure_rules_loaded()
            try:
                # 1. Extrair o termo chave da pergunta
                search_term = await self._extract_keyword(question)
                log.info(f"Termo de busca extraído para a pergunta sobre '{question}': '{search_term}'")

                # 2. Buscar o termo no arquivo de regras pré-carregado
                context_excerpts = self._search_rules_for_term(search_term)
                source_text = "Conhecimento Geral da IA"

                prompt_to_send = [self.system_prompt_rules]

                if context_excerpts:
                    # 3. Se encontrou contexto, monta o prompt para RAG
                    log.info(f"Contexto encontrado para '{search_term}'. Usando modo RAG.")
                    full_context = "\n\n---\n\n".join(context_excerpts)
                    rag_prompt = (
                        f"Pergunta do Usuário: \"{question}\"\n\n"
                        f"Trechos Relevantes das Regras (sobre '{search_term}'):\n{full_context}\n\n"
                        "Sua Resposta (baseada nos trechos acima):"
                    )
                    prompt_to_send.append(rag_prompt)
                    source_text = "Livros de Regras (Busca Local)"
                else:
                    # 4. Se não encontrou, usa o conhecimento geral da IA
                    log.info(f"Nenhum contexto encontrado para '{search_term}'. Usando modo de conhecimento geral.")
                    prompt_to_send.append(question)

                # 5. Enviar para o Gemini e obter a resposta
                response = await asyncio.wait_for(
                    self.rules_model.generate_content_async(prompt_to_send),
                    timeout=QUERY_TIMEOUT
                )
                response_text = response.text
                embed_title = f"Mestre Tatu responde sobre: {question.title()}"

                # 6. Enviar a resposta, dividindo em múltiplos embeds se for longa
                if len(response_text) <= 4096:
                    embed = discord.Embed(title=embed_title, description=response_text, color=discord.Color.blue())
                    embed.set_footer(text=f"Fonte: {source_text}")
                    await ctx.reply(embed=embed)
                else:
                    chunks = [response_text[i:i + 4000] for i in range(0, len(response_text), 4000)]
                    for i, chunk in enumerate(chunks):
                        part_title = f"{embed_title} (Parte {i + 1}/{len(chunks)})"
                        embed = discord.Embed(title=part_title, description=chunk, color=discord.Color.blue())
                        embed.set_footer(text=f"Fonte: {source_text}")
                        await ctx.send(embed=embed)

            except asyncio.TimeoutError:
                await ctx.reply(f"A resposta demorou mais de {QUERY_TIMEOUT} segundos e foi cancelada. Tente novamente.")
            except Exception as e:
                log.error(f"Falha ao processar a pergunta de RPG '{question}'.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora.")

    @commands.command(name='npc', help='Gera um NPC com base em uma descrição. Ex: .npc taverneiro anão')
    async def generate_npc(self, ctx: commands.Context, *, description: str = None):
        if not self.npc_model:
            await ctx.reply("Desculpe, minha forja de almas (API do Gemini) parece estar fria no momento.")
            return

        if not description:
            await ctx.reply(
                "Por favor, me dê uma breve descrição do NPC que você quer criar. Ex: `.npc guarda de cidade elfo`")
            return

        async with ctx.typing():
            prompt = f"""
            Você é o Arquiteto de Almas, uma entidade cósmica que forja personagens para mundos de fantasia.
            Sua tarefa é criar um personagem memorável e inspirador com base na descrição fornecida. A resposta deve ser rica em detalhes, mas concisa.

            **Formato de Saída Obrigatório (use exatamente estes campos e esta ordem):**
            Nome: [Nome do Personagem]
            Idade: [Idade do personagem, pode ser um número ou descritiva como "Jovem Adulto", "Meia-idade", "Ancião"]
            Aparência: [Uma descrição física marcante e visual, focando em rosto, cabelo, roupas e postura.]
            Personalidade: [Dois ou três traços de como o personagem age, fala ou pensa.]
            Segredo/Objetivo: [Um segredo que ele esconde ou um objetivo que ele busca. Deve ser um gancho de aventura.]

            **Exemplo de Saída:**
            Input: "um velho mago que vive em uma torre"
            Output:
            Nome: Elara Vancroft
            Idade: Anciã (cerca de 250 anos)
            Aparência: Uma mulher de cabelos prateados presos em um coque frouxo, com olhos que brilham com uma luz violeta suave. Suas vestes, embora antigas, são impecavelmente limpas e bordadas com constelações. Anda com uma leve curvatura, apoiada em um cajado de carvalho retorcido.
            Personalidade: Fala em enigmas e parece perpetuamente distraída, como se estivesse ouvindo uma conversa em outro plano de existência. É paciente, mas severa com a ignorância.
            Segredo/Objetivo: Ela não está estudando magia, mas sim tentando contatar uma entidade presa em um artefato em sua torre, acreditando ser sua antiga mentora.

            **Descrição para Forjar:** "{description}"
            """
            try:
                log.info(f"[{ctx.guild.id}] Comando 'npc' recebido com a descrição: '{description}'")
                response = await asyncio.wait_for(
                    self.npc_model.generate_content_async(prompt),
                    timeout=QUERY_TIMEOUT
                )

                parts = response.text.strip().split('\n')
                if len(parts) < 5:
                    raise ValueError("A resposta da IA não seguiu o formato esperado de 5 partes.")

                npc_name = parts[0].replace("Nome:", "").strip()
                npc_age = parts[1].replace("Idade:", "").strip()
                npc_appearance = parts[2].replace("Aparência:", "").strip()
                npc_personality = parts[3].replace("Personalidade:", "").strip()
                npc_secret = parts[4].replace("Segredo/Objetivo:", "").strip()

                embed = discord.Embed(
                    title="👤 Personagem Forjado",
                    color=discord.Color.teal()
                )
                embed.add_field(name="Nome", value=npc_name, inline=False)
                embed.add_field(name="Idade", value=npc_age, inline=False)
                embed.add_field(name="Aparência", value=npc_appearance, inline=False)
                embed.add_field(name="Personalidade", value=npc_personality, inline=False)
                embed.add_field(name="Segredo / Objetivo", value=npc_secret, inline=False)
                embed.set_footer(text=f"Conceito: {description}")

                await ctx.reply(embed=embed)

            except asyncio.TimeoutError:
                log.warning(f"[{ctx.guild.id}] A geração do NPC excedeu o timeout de {QUERY_TIMEOUT}s.")
                await ctx.reply("A inspiração cósmica demorou demais... Tente forjar outra alma.")
            except Exception as e:
                log.error(f"[{ctx.guild.id}] Falha ao gerar o NPC.", exc_info=True)
                await ctx.reply(
                    "Ocorreu um erro na forja de almas. A descrição pode ter sido muito complexa ou um erro inesperado aconteceu.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(RpgCog(bot))