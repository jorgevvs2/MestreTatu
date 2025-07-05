# src/cogs/lookup_cog.py

import discord
from discord.ext import commands
import logging
import os
import asyncio
import re

log = logging.getLogger(__name__)
RULES_FILE = 'src/rpg_books/compiled_rules.txt'
QUERY_TIMEOUT = 120  # Segundos de timeout para a resposta da IA.


class LookupCog(commands.Cog, name="Consultas Rápidas"):
    """
    Cog para consultas rápidas de regras, magias, itens e monstros
    diretamente do arquivo de regras local, com explicações geradas por IA.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rules_text = None
        self._rules_lock = asyncio.Lock()
        # Acessa o modelo de IA para gerar as explicações
        self.rules_model = bot.gemini_pro_model
        # --- PROMPT APRIMORADO ---
        # Instruções mais naturais, tratando o texto como uma fonte de verdade, não algo a ser comentado.
        self.system_prompt_lookup = (
            "Você é o Mestre Tatu, um mestre de D&D 5e experiente e amigável. Sua tarefa é dar uma explicação clara e completa sobre um termo de D&D (magia, item, monstro, etc.).\n\n"
            "**Instruções:**\n"
            "1. **Fonte de Verdade:** Um trecho das regras será fornecido como referência para garantir a precisão. Use-o como a base principal para sua explicação.\n"
            "2. **Enriqueça a Resposta:** Sinta-se à vontade para complementar a explicação com seu conhecimento geral de D&D, adicionando dicas de uso, sinergias ou curiosidades que tornem a resposta mais útil. Você pode introduzir essa parte com 'Dica do Mestre:' ou algo similar.\n"
            "3. **Seja Natural:** Explique o conceito diretamente. Não é necessário mencionar que você está se baseando em um trecho de texto (por exemplo, evite frases como 'De acordo com o texto...').\n"
            "4. **Formato e Idioma:** Use markdown do Discord para uma boa legibilidade e responda sempre em português."
        )

    async def _ensure_rules_loaded(self):
        """
        Garante que as regras foram carregadas, usando um Lock para ser seguro
        em ambientes com múltiplas chamadas concorrentes.
        """
        if self.rules_text is not None:
            return

        async with self._rules_lock:
            if self.rules_text is None:
                log.info("LookupCog: Carregando arquivo de regras na memória...")
                self.rules_text = self._load_rules()

    def _load_rules(self) -> str:
        """
        Carrega o arquivo de regras pré-processado na memória.
        """
        if not os.path.exists(RULES_FILE):
            log.error(f"LookupCog: Arquivo de regras '{RULES_FILE}' não encontrado!")
            return ""
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                log.info(f"LookupCog: Arquivo de regras '{RULES_FILE}' carregado com sucesso.")
                return f.read()
        except Exception as e:
            log.error(f"LookupCog: Falha ao carregar o arquivo de regras '{RULES_FILE}': {e}", exc_info=True)
            return ""

    def _find_entry_text(self, term: str) -> str | None:
        """
        Encontra uma entrada completa no texto de regras.
        Assume que cada entrada (magia, item, etc.) começa com seu nome em uma nova linha
        e é separada da próxima por duas ou mais linhas em branco.
        """
        if not self.rules_text:
            return None

        # Regex para encontrar o termo no início de uma linha e capturar tudo
        # até a próxima ocorrência de duas ou mais linhas em branco, ou o fim do arquivo.
        pattern = re.compile(
            r"(^" + re.escape(term) + r".*?)(?=\n\s*\n\s*\n|\Z)",
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        match = pattern.search(self.rules_text)
        if match:
            return match.group(1).strip()
        return None

    async def _lookup_and_reply(self, ctx: commands.Context, term: str, entry_type: str, icon: str):
        """Função genérica para buscar um termo, enviar para a IA e responder."""
        if not self.rules_model:
            await ctx.reply("Desculpe, minha conexão com os planos astrais (API do Gemini) não está funcionando.")
            return

        await self._ensure_rules_loaded()

        if not self.rules_text:
            await ctx.reply(f"Desculpe, a base de dados de regras (`{RULES_FILE}`) não está disponível.")
            return

        async with ctx.typing():
            context_text = self._find_entry_text(term)

            if not context_text:
                await ctx.reply(f"Não consegui encontrar nenhuma entrada para '{term}' no meu livro de regras.")
                return

            # Constrói o prompt para a IA, fornecendo o contexto encontrado
            prompt_to_send = [
                self.system_prompt_lookup,
                (
                    f"Com base no texto de regras abaixo, explique detalhadamente o que é e como funciona o seguinte {entry_type.lower()}: **{term}**\n\n"
                    f"**Texto de Referência:**\n---\n{context_text}\n---"
                )
            ]

            try:
                # Envia para a IA e aguarda a resposta
                response = await asyncio.wait_for(
                    self.rules_model.generate_content_async(prompt_to_send),
                    timeout=QUERY_TIMEOUT
                )
                response_text = response.text
            except asyncio.TimeoutError:
                await ctx.reply(f"A resposta da IA demorou mais de {QUERY_TIMEOUT} segundos e foi cancelada. Tente novamente.")
                return
            except Exception as e:
                log.error(f"Falha ao processar a consulta de lookup para '{term}'.", exc_info=True)
                await ctx.reply("Desculpe, o Mestre Tatu parece estar meditando e não pôde responder agora.")
                return

            embed_title = f"{icon} {term.title()}"

            # Paginação para a resposta gerada pela IA
            if len(response_text) <= 4096:
                embed = discord.Embed(title=embed_title, description=response_text, color=discord.Color.dark_gold())
                embed.set_footer(text="Fonte: Livros de Regras (Busca Local com IA)")
                await ctx.reply(embed=embed)
            else:
                chunks = [response_text[i:i + 4000] for i in range(0, len(response_text), 4000)]
                for i, chunk in enumerate(chunks):
                    part_title = f"{embed_title} (Parte {i + 1}/{len(chunks)})"
                    embed = discord.Embed(title=part_title, description=chunk, color=discord.Color.dark_gold())
                    embed.set_footer(text="Fonte: Livros de Regras (Busca Local com IA)")
                    if i == 0:
                        await ctx.reply(embed=embed)
                    else:
                        await ctx.send(embed=embed)

    @commands.command(name='spell', aliases=['magia'],
                      help="Busca uma magia no livro de regras. Ex: .spell bola de fogo")
    async def spell(self, ctx: commands.Context, *, spell_name: str):
        """Busca por uma magia específica no arquivo de regras local."""
        await self._lookup_and_reply(ctx, spell_name.strip(), "Magia", "✨")

    @commands.command(name='item', help="Busca um item no livro de regras. Ex: .item poção de cura")
    async def item(self, ctx: commands.Context, *, item_name: str):
        """Busca por um item específico no arquivo de regras local."""
        await self._lookup_and_reply(ctx, item_name.strip(), "Item", "🎒")

    @commands.command(name='monster', aliases=['monstro'],
                      help="Busca um monstro no livro de regras. Ex: .monster goblin")
    async def monster(self, ctx: commands.Context, *, monster_name: str):
        """Busca por um monstro específico no arquivo de regras local."""
        await self._lookup_and_reply(ctx, monster_name.strip(), "Monstro", "👹")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(LookupCog(bot))