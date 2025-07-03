import os
import discord
from discord.ext import commands
import logging
import asyncio

log = logging.getLogger(__name__)

class StationsCog(commands.Cog, name="Estações"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("StationsCog (Estações de Rádio) inicializado.")

    async def _play_station(self, ctx: commands.Context, station_env_var: str, station_name: str):
        music_cog = self.bot.get_cog('Música')
        if not music_cog:
            await ctx.reply("O módulo de música parece estar desativado. Não consigo tocar a estação.")
            return

        if not ctx.author.voice:
            await ctx.reply("Você precisa estar em um canal de voz para iniciar uma estação!")
            return

        playlist_url = os.getenv(station_env_var)
        if not playlist_url:
            log.error(f"A variável de ambiente '{station_env_var}' não foi encontrada!")
            await ctx.reply(f"Desculpe, a estação '{station_name}' não está configurada corretamente.")
            return

        log.info(f"[{ctx.guild.id}] Trocando para a estação: '{station_name}'")
        await ctx.reply(f"Sintonizando na estação **{station_name}**! Limpando a fila e iniciando a playlist...")

        stop_command = self.bot.get_command('stop')
        await ctx.invoke(stop_command)

        await asyncio.sleep(1.5)

        play_command = self.bot.get_command('play')
        await ctx.invoke(play_command, search=playlist_url)

    @commands.command(name='ds', help='Toca a estação de rádio Dark Souls.')
    async def ds(self, ctx: commands.Context):
        await self._play_station(ctx, 'DS_PLAYLIST', 'Dark Souls')

    @commands.command(name='lofi', help='Toca a estação de rádio Lo-fi del Cornos.')
    async def lofi(self, ctx: commands.Context):
        await self._play_station(ctx, 'LF_DEL_CORNOS', 'Lo-fi del Cornos')

    @commands.command(name='xama', help='Toca a estação de rádio do Xamã.')
    async def xama(self, ctx: commands.Context):
        await self._play_station(ctx, 'XAMA_PLAYLIST', 'Xamã')

    @commands.command(name='wicked', help='Toca a estação de rádio Wicked.')
    async def wicked(self, ctx: commands.Context):
        await self._play_station(ctx, 'WICKED_PLAYLIST', 'Wicked')


async def setup(bot: commands.Bot):
    await bot.add_cog(StationsCog(bot))