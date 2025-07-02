# src/cogs/lookup_cog.py

import discord
from discord.ext import commands
import requests
import asyncio
import logging

log = logging.getLogger(__name__)

# URL base da API de D&D 5e
DND_API_BASE_URL = "https://www.dnd5eapi.co/api/"


def fetch_from_api_sync(endpoint: str, formatted_query: str):
    """
    Função síncrona para buscar dados da API.
    Retorna os dados em JSON ou None se não for encontrado (404).
    """
    url = f"{DND_API_BASE_URL}{endpoint}/{formatted_query}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 404:
            log.warning(f"API D&D retornou 404 para: {formatted_query}")
            return None  # Retorna None explicitamente em caso de 404
        else:
            log.error(f"Erro HTTP ao acessar a API D&D: {http_err}", exc_info=True)
            raise
    except requests.exceptions.RequestException as req_err:
        log.error(f"Erro de conexão com a API D&D: {req_err}", exc_info=True)
        raise


class LookupCog(commands.Cog, name="Consulta Rápida"):
    """
    Cog para consultar magias, itens e armas.
    Tenta primeiro a API de D&D 5e. Se falhar, usa o Gemini Pro como fallback.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Usaremos apenas o modelo Pro para o fallback
        self.gemini_pro_model = self.bot.gemini_pro_model
        log.info("LookupCog (Modo API com Fallback Gemini) inicializado.")

    def _format_api_spell_embed(self, data: dict) -> discord.Embed:
        """Cria um embed formatado para uma magia a partir dos dados da API."""
        embed = discord.Embed(
            title=f"✨ {data.get('name', 'Magia Desconhecida')}",
            description="\n\n".join(data.get('desc', [])),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Fonte: D&D 5e API")

        level = data.get('level', 0)
        school = data.get('school', {}).get('name', 'N/A')
        embed.add_field(name="Nível", value=f"{level} ({school})", inline=True)
        embed.add_field(name="Tempo de Conjuração", value=data.get('casting_time', 'N/A'), inline=True)
        embed.add_field(name="Alcance", value=data.get('range', 'N/A'), inline=True)
        components = ", ".join(data.get('components', []))
        embed.add_field(name="Componentes", value=components if components else "Nenhum", inline=True)
        embed.add_field(name="Duração", value=data.get('duration', 'N/A'), inline=True)
        if data.get('material'):
            embed.add_field(name="Material", value=data.get('material'), inline=False)
        return embed

    def _format_api_item_embed(self, data: dict) -> discord.Embed:
        """Cria um embed formatado para um item a partir dos dados da API."""
        embed = discord.Embed(
            title=f"💎 {data.get('name', 'Item Desconhecido')}",
            description="\n\n".join(data.get('desc', [])),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Fonte: D&D 5e API")
        rarity = data.get('rarity', {}).get('name', 'N/A')
        item_type = data.get('equipment_category', {}).get('name', 'N/A')
        embed.add_field(name="Tipo", value=item_type, inline=True)
        embed.add_field(name="Raridade", value=rarity, inline=True)
        return embed

    # --- NOVA FUNÇÃO ---
    def _format_api_weapon_embed(self, data: dict) -> discord.Embed:
        """Cria um embed formatado para uma arma a partir dos dados da API."""
        embed = discord.Embed(
            title=f"⚔️ {data.get('name', 'Arma Desconhecida')}",
            color=discord.Color.light_grey()
        )
        embed.set_footer(text="Fonte: D&D 5e API")

        category = data.get('equipment_category', {}).get('name', 'N/A')
        embed.add_field(name="Categoria", value=category, inline=True)

        cost = data.get('cost', {})
        cost_str = f"{cost.get('quantity', 0)} {cost.get('unit', 'gp')}"
        embed.add_field(name="Custo", value=cost_str, inline=True)

        damage = data.get('damage', {})
        damage_dice = damage.get('damage_dice', 'N/A')
        damage_type = damage.get('damage_type', {}).get('name', 'N/A')
        embed.add_field(name="Dano", value=f"{damage_dice} ({damage_type})", inline=True)

        weight = data.get('weight', 0)
        embed.add_field(name="Peso", value=f"{weight} lb.", inline=True)

        properties = data.get('properties', [])
        prop_names = [prop.get('name', '') for prop in properties]
        prop_str = ", ".join(prop_names) if prop_names else "Nenhuma"
        embed.add_field(name="Propriedades", value=prop_str, inline=False)

        return embed

    async def _ask_gemini_fallback(self, ctx: commands.Context, query: str, category: str):
        """
        Função de fallback que pergunta ao Gemini Pro sobre o tópico quando a API falha.
        """
        if not self.gemini_pro_model:
            await ctx.reply("A API de D&D não encontrou o item e meu assistente de IA (Gemini) está indisponível.")
            return

        log.info(f"API D&D falhou. Usando Gemini Pro como fallback para a query: '{query}'")
        await ctx.send(f"Não encontrei `{query}` na base de dados principal. Consultando o Mestre Tatu (IA)...", delete_after=10)

        # --- PROMPT ATUALIZADO para incluir armas ---
        prompt = f"""
        Você é o Mestre Tatu, uma enciclopédia viva de Dungeons & Dragons 5ª Edição.
        Sua tarefa é fornecer uma descrição concisa e estruturada para o termo "{query}", que é um(a) {category[:-1]}.

        **REGRAS ESTRITAS:**
        1.  Baseie-se estritamente nas regras e lore oficiais de D&D 5e.
        2.  Use o formato markdown `**Campo:** Valor` para todos os dados.
        3.  **NÃO** inclua saudações, explicações ou qualquer texto que não seja a ficha de dados. Sua resposta deve começar diretamente com `**Nome:**`.
        4.  Se o termo for uma **magia**, inclua os seguintes campos: Nome, Nível, Escola, Tempo de Conjuração, Alcance, Componentes, Duração e Descrição.
        5.  Se o termo for um **item**, inclua os seguintes campos: Nome, Tipo, Raridade e Descrição.
        6.  Se o termo for uma **arma**, inclua os seguintes campos: Nome, Categoria, Custo, Dano, Peso e Propriedades.
        7.  Se o termo "{query}" não for encontrado ou não pertencer a D&D 5e, sua única resposta deve ser: "Não encontrei informações sobre '{query}' nos meus tomos."
        """

        try:
            response = await asyncio.wait_for(
                self.gemini_pro_model.generate_content_async(prompt),
                timeout=45
            )
            embed = discord.Embed(
                title=f"📜 Consulta do Mestre Tatu sobre: {query.title()}",
                description=response.text,
                color=discord.Color.purple()  # Cor diferente para indicar que é da IA
            )
            embed.set_footer(text="Fonte: Mestre Tatu (IA Gemini Pro)")
            await ctx.reply(embed=embed)
        except Exception as e:
            log.error(f"Erro no fallback do Gemini para '{query}'.", exc_info=True)
            await ctx.reply("O Mestre Tatu tentou ajudar, mas se perdeu nos planos astrais. Tente novamente.")

    async def _perform_lookup(self, ctx: commands.Context, endpoint: str, category: str, query: str, embed_formatter):
        """
        Fluxo de busca: Tenta a API D&D primeiro, depois usa o Gemini como fallback.
        """
        async with ctx.typing():
            # Formata a query para o padrão da API (ex: "fire ball" -> "fire-ball")
            api_query = query.lower().strip().replace(" ", "-")

            # Passo 1: Tentar a API de D&D
            data = await asyncio.to_thread(fetch_from_api_sync, endpoint, api_query)

            if data:
                # Sucesso! Formata e envia a resposta da API.
                log.info(f"Encontrado '{query}' na API D&D.")
                embed = embed_formatter(data)
                await ctx.reply(embed=embed)
                return

            # Passo 2: A API falhou (404), usar o Gemini como fallback.
            # Usamos a query original do usuário, não a formatada.
            await self._ask_gemini_fallback(ctx, query, category)

    @commands.command(name='spell', aliases=['magia'],
                      help='Busca uma magia. Tenta a API, depois a IA. Ex: .spell fireball')
    async def spell(self, ctx: commands.Context, *, spell_name: str):
        await self._perform_lookup(ctx, "spells", "spells", spell_name, self._format_api_spell_embed)

    @commands.command(name='item', aliases=['itemmágico'],
                      help='Busca um item. Tenta a API, depois a IA. Ex: .item ring-of-protection')
    async def item(self, ctx: commands.Context, *, item_name: str):
        await self._perform_lookup(ctx, "magic-items", "items", item_name, self._format_api_item_embed)

    # --- NOVO COMANDO ---
    @commands.command(name='weapon', aliases=['arma'],
                      help='Busca uma arma. Tenta a API, depois a IA. Ex: .weapon longsword')
    async def weapon(self, ctx: commands.Context, *, weapon_name: str):
        await self._perform_lookup(ctx, "weapons", "weapons", weapon_name, self._format_api_weapon_embed)


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(LookupCog(bot))