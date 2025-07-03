import os
import discord
import fitz
from discord.ext import commands
import asyncio
import logging
import google.generativeai as genai

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)
QUERY_TIMEOUT = 60  # Aumentamos um pouco o timeout para acomodar a busca
RPG_BOOKS_PATH = "src/rpg_books"  # Caminho para a pasta com os PDFs


class RPGCog(commands.Cog, name="Mestre de RPG"):
    """Cog que usa o Gemini Pro para responder dúvidas e gerar conteúdo de RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Modelos para diferentes tarefas
        self.rules_model = self.bot.gemini_pro_model
        self.keyword_extractor_model = self.bot.gemini_flash_model  # Usamos o Flash para extrair keywords
        self.npc_model = None

        if self.rules_model:
            try:
                creative_config = genai.types.GenerationConfig(temperature=0.9)
                self.npc_model = genai.GenerativeModel(
                    model_name="gemini-1.5-pro-latest",
                    generation_config=creative_config
                )
                log.info("RPGCog: Modelo Gemini para NPCs (criativo) inicializado com sucesso.")
            except Exception as e:
                log.error("RPGCog: Falha ao inicializar o modelo Gemini para NPCs.", exc_info=True)
                self.npc_model = None

        self.system_prompt_rules = """
        Você é o Mestre Tatu, um mestre de Dungeons & Dragons (D&D) extremamente conhecedor das regras.
        Sua principal função é responder a perguntas sobre as regras de D&D 5ª Edição, incluindo as regras revisadas de 2024 (às vezes chamadas de 5.5e).
        Baseie suas respostas nos livros oficiais, priorizando o Player's Handbook de 2024, o Dungeon Master's Guide de 2024 e o Monster Manual de 2025 quando aplicável.
        Se uma regra for diferente entre a versão de 2014 e a de 2024, mencione ambas, mas dê destaque à versão mais recente.
        Seja preciso, objetivo e evite respostas criativas ou narrativas; foque em ser um guia de regras confiável e direto ao ponto.
        """
        log.info("RPGCog (modo Gemini Pro - Regras D&D) inicializado.")

    # --- FUNÇÃO DE BUSCA COM LOGS DE DIAGNÓSTICO ---
    async def _search_books_for_term(self, term: str) -> list[str]:
        """Busca um termo em todos os PDFs, com logs detalhados para diagnóstico."""
        log.info(f"Iniciando busca nos livros pelo termo: '{term}'")

        # LOG 1: Verificar o caminho absoluto que o contêiner está usando.
        absolute_path = os.path.abspath(RPG_BOOKS_PATH)
        log.info(f"Verificando a existência da pasta de livros em: '{absolute_path}'")

        excerpts = []
        try:
            if not os.path.exists(RPG_BOOKS_PATH):
                log.warning(f"A pasta de livros '{RPG_BOOKS_PATH}' não foi encontrada. A busca será abortada.")
                return []

            # LOG 2: Listar os arquivos encontrados no diretório.
            try:
                files_in_dir = os.listdir(RPG_BOOKS_PATH)
                log.info(f"Arquivos encontrados na pasta '{RPG_BOOKS_PATH}': {files_in_dir}")
                if not any(f.lower().endswith('.pdf') for f in files_in_dir):
                    log.warning("Nenhum arquivo .pdf foi encontrado na pasta de livros.")
            except Exception as e:
                log.error(f"Não foi possível listar os arquivos em '{RPG_BOOKS_PATH}'. Erro: {e}")
                return []

            def search_task():
                found_excerpts = []
                for filename in os.listdir(RPG_BOOKS_PATH):
                    if filename.lower().endswith('.pdf'):
                        filepath = os.path.join(RPG_BOOKS_PATH, filename)

                        # LOG 3: Informar qual arquivo está sendo processado.
                        log.info(f"Processando arquivo: '{filepath}'...")

                        try:
                            with fitz.open(filepath) as doc:
                                # LOG 4: Checagem rápida para PDF de imagem.
                                if doc.page_count > 0 and not doc[0].get_text("text"):
                                    log.warning(
                                        f"O arquivo '{filename}' parece ser um PDF de imagem ou está vazio, pois a primeira página não contém texto extraível.")

                                for page_num, page in enumerate(doc):
                                    blocks = page.get_text("blocks")
                                    log.debug(
                                        f"Página {page_num + 1} de '{filename}' contém {len(blocks)} blocos de texto.")

                                    for i, block in enumerate(blocks):
                                        block_text = block[4]
                                        if term.lower() in block_text.lower():
                                            # LOG 5: Sucesso! O termo foi encontrado.
                                            log.info(
                                                f"Termo '{term}' ENCONTRADO na página {page_num + 1} do arquivo '{filename}'.")

                                            context_window = []
                                            if i > 0:
                                                context_window.append(blocks[i - 1][4].strip())
                                            context_window.append(block_text.strip())
                                            if i < len(blocks) - 1:
                                                context_window.append(blocks[i + 1][4].strip())

                                            full_context_snippet = "\n\n".join(context_window)
                                            found_excerpts.append(
                                                f"Fonte: {filename}, Página: {page_num + 1}\n\n{full_context_snippet}")
                        except Exception as e:
                            log.error(f"Erro ao processar o PDF '{filename}': {e}")

                return list(dict.fromkeys(found_excerpts))

            excerpts = await asyncio.to_thread(search_task)
            log.info(f"Busca concluída. Encontrados {len(excerpts)} trechos relevantes para '{term}'.")
            return excerpts
        except Exception as e:
            log.error(f"Erro geral na busca de livros por '{term}'.", exc_info=True)
            return []

    # --- NOVA FUNÇÃO PARA EXTRAIR KEYWORD ---
    async def _extract_keyword(self, question: str) -> str:
        """Usa o Gemini Flash para extrair o termo de regra principal de uma pergunta."""
        if not self.keyword_extractor_model:
            # Fallback simples: usa a primeira palavra capitalizada ou a pergunta inteira
            return next((word.strip("?,.") for word in question.split() if word.istitle()), question)

        prompt = f"""
        Analise a seguinte pergunta sobre regras de D&D 5e e extraia o termo ou conceito de regra principal.
        Responda APENAS com o termo, em português.

        Exemplos:
        - Pergunta: "como funciona a condição Agarrado?" -> Resposta: "Agarrado"
        - Pergunta: "o que é uma Ação Bônus" -> Resposta: "Ação Bônus"
        - Pergunta: "me explique a magia Mísseis Mágicos" -> Resposta: "Mísseis Mágicos"
        - Pergunta: "qual o deslocamento de um anão" -> Resposta: "deslocamento"

        Pergunta: "{question}"
        Resposta:
        """
        try:
            response = await asyncio.wait_for(
                self.keyword_extractor_model.generate_content_async(prompt),
                timeout=10
            )
            keyword = response.text.strip()
            log.info(f"Keyword extraída da pergunta '{question}': '{keyword}'")
            return keyword
        except Exception as e:
            log.error(f"Falha ao extrair keyword da pergunta: '{question}'", exc_info=True)
            return question  # Retorna a pergunta original em caso de erro

    @commands.command(name='rpg', help='Tira uma dúvida de D&D com o Mestre Tatu. Uso: .rpg sua pergunta')
    async def rpg_question(self, ctx: commands.Context, *, question: str = None):
        """Recebe uma pergunta de RPG, extrai o termo chave, busca nos PDFs e gera uma resposta contextualizada."""
        if not self.rules_model:
            await ctx.reply("Desculpe, a minha conexão com os planos astrais (API do Gemini) não está funcionando.")
            return

        if not question:
            await ctx.reply("Por favor, faça uma pergunta após o comando. Ex: `.rpg Vantagem`")
            return

        async with ctx.typing():
            try:
                prompt_to_send = []
                source_text = ""

                # --- LÓGICA DE OTIMIZAÇÃO ADICIONADA AQUI ---
                # Se a pergunta for longa (> 4 palavras), pula a busca local e vai direto para a IA.
                if len(question.split()) > 4:
                    log.info(
                        f"Pergunta longa detectada ('{question[:30]}...'). Pulando busca local e enviando direto para a IA.")
                    prompt_to_send = [self.system_prompt_rules, question]
                    source_text = "Conhecimento Geral da IA"
                else:
                    # Lógica original para perguntas curtas (provavelmente termos de regra)
                    log.info(f"Pergunta curta detectada. Iniciando processo de busca local para: '{question}'")
                    search_term = await self._extract_keyword(question)
                    context_excerpts = await self._search_books_for_term(search_term)

                    if context_excerpts:
                        # Modo RAG: Encontramos contexto nos livros!
                        log.info(f"Usando modo RAG para a pergunta: '{question}' com o termo '{search_term}'")
                        full_context = "\n\n---\n\n".join(
                            context_excerpts[:3])  # Limita a 3 janelas de contexto para não exceder o prompt

                        rag_prompt = f"""
                        Você é o Mestre Tatu, um especialista em regras de D&D 5.5e.
                        Sua tarefa é responder à pergunta do usuário baseando-se **EXCLUSIVAMENTE** nos trechos de texto fornecidos abaixo, que foram extraídos diretamente dos livros de regras.
                        Explique o significado e a mecânica por trás do termo da pergunta. Se os trechos não forem claros o suficiente, afirme que a informação encontrada é limitada, mas explique o que foi possível extrair. Não invente informações.

                        **PERGUNTA DO USUÁRIO:**
                        {question}

                        **TRECHOS RELEVANTES DOS LIVROS (sobre '{search_term}'):**
                        {full_context}

                        **SUA RESPOSTA (baseada nos trechos acima):**
                        """
                        prompt_to_send.append(rag_prompt)
                        source_text = "Livros de Regras (Busca Local)"
                    else:
                        # Modo Fallback: Não encontramos nada, usamos o prompt antigo
                        log.info(f"Nenhum contexto encontrado para '{search_term}'. Usando modo de conhecimento geral.")
                        prompt_to_send.append(self.system_prompt_rules)
                        prompt_to_send.append(question)
                        source_text = "Conhecimento Geral da IA"

                # Passo Final: Enviar para o Gemini e obter a resposta
                response = await asyncio.wait_for(
                    self.rules_model.generate_content_async(prompt_to_send),
                    timeout=QUERY_TIMEOUT
                )

                response_text = response.text
                embed_title = f"Mestre Tatu responde sobre: {question.title()}"

                # --- LÓGICA DE DIVISÃO DE RESPOSTA ATUALIZADA ---
                if len(response_text) <= 4096:
                    # A resposta cabe em um único embed
                    embed = discord.Embed(
                        title=embed_title,
                        description=response_text,
                        color=discord.Color.from_rgb(114, 137, 218)
                    )
                    embed.set_footer(text=f"Fonte: {source_text}")
                    await ctx.reply(embed=embed)
                else:
                    # A resposta é muito longa e precisa ser dividida
                    log.warning(
                        f"A resposta da IA excedeu 4096 caracteres ({len(response_text)}). A resposta será dividida.")

                    # Divide o texto em pedaços de 4000 caracteres para caber na descrição do embed
                    chunks = [response_text[i:i + 4000] for i in range(0, len(response_text), 4000)]

                    # Envia o primeiro embed
                    first_embed = discord.Embed(
                        title=f"{embed_title} (Parte 1 de {len(chunks)})",
                        description=chunks[0] + "\n\n*(Continua...)*",
                        color=discord.Color.from_rgb(114, 137, 218)
                    )
                    first_embed.set_footer(text=f"Fonte: {source_text}")
                    await ctx.reply(embed=first_embed)

                    # --- ALTERAÇÃO AQUI: Envia o resto das partes como embeds também ---
                    for i, chunk in enumerate(chunks[1:], start=2):
                        follow_up_embed = discord.Embed(
                            title=f"{embed_title} (Parte {i} de {len(chunks)})",
                            description=chunk,
                            color=discord.Color.from_rgb(114, 137, 218)
                        )
                        follow_up_embed.set_footer(text=f"Fonte: {source_text}")
                        await ctx.send(embed=follow_up_embed)

            except asyncio.TimeoutError:
                await ctx.reply(
                    f"A resposta demorou mais de {QUERY_TIMEOUT} segundos e foi cancelada. Tente novamente.")
            except Exception as e:
                log.error(f"Falha ao processar a pergunta de RPG '{question}'.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora.")
            except Exception as e:
                log.error(f"Falha ao processar a pergunta de RPG '{question}'.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora.")

    # (O comando .npc e o resto da classe continuam aqui, sem alterações)
    @commands.command(name='npc', help='Gera um NPC com base em uma descrição. Ex: .npc taverneiro anão')
    async def generate_npc(self, ctx: commands.Context, *, description: str = None):
        # ... (código do gerador de NPC permanece o mesmo)
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
    await bot.add_cog(RPGCog(bot))