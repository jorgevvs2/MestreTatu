# D:/Codes/TatuBeats/src/cogs/music_cog.py

import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import re
import logging
import spotipy

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)


# --- FUNÇÕES HELPER SÍNCRONAS ---
# (These helper functions are correct and do not need changes)
def ydl_extract_info_sync(ydl_options, query, download=False):
    """Helper síncrono para rodar yt-dlp sem bloquear o loop de eventos."""
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        return ydl.extract_info(query, download=download)


def spotify_get_playlist_tracks_sync(spotify_client: spotipy.Spotify, playlist_id: str):
    """Helper síncrono para buscar todas as faixas de uma playlist do Spotify."""
    all_tracks = []
    results = spotify_client.playlist_tracks(playlist_id)
    all_tracks.extend(results['items'])
    while results['next']:
        results = spotify_client.next(results)
        all_tracks.extend(results['items'])
    return all_tracks


class MusicCog(commands.Cog, name="Música"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spotify_client = bot.spotify_client
        self.ydl_options = bot.ydl_options
        self.ffmpeg_options = bot.ffmpeg_options
        self.music_queues = {}
        self.last_ctx = {}
        # --- CHANGE 1: Use a private variable for the cached cog instance ---
        self._message_cog_instance = None
        log.info("MusicCog inicializado.")

    # --- CHANGE 2: Create a property to lazy-load the MessageCog ---
    @property
    def message_cog(self):
        """
        Property to get and cache the MessageCog instance on-demand.
        This is a robust way to handle inter-cog dependencies.
        """
        if self._message_cog_instance is None:
            self._message_cog_instance = self.bot.get_cog('MessageCog')
            if self._message_cog_instance is None:
                log.critical("CRITICAL: MusicCog could not find the MessageCog. It might not be loaded.")
        return self._message_cog_instance

    async def cog_before_invoke(self, ctx: commands.Context):
        """Garante que temos uma referência ao contexto mais recente."""
        self.last_ctx[ctx.guild.id] = ctx
        # --- CHANGE 3: The logic to get message_cog is no longer needed here ---
        # It is now handled by the @property.

    def handle_after_play(self, error, ctx):
        """Função de callback segura chamada após uma música terminar."""
        if error:
            log.error(f"[{ctx.guild.id}] Erro no callback 'after' da música: {error}", exc_info=True)
        else:
            log.info(f"[{ctx.guild.id}] Música terminou normalmente. Chamando próximo da fila.")

        # Chama a próxima música de forma segura a partir de um thread síncrono.
        asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

    async def play_next(self, ctx):
        """Pega a próxima música da fila e a toca."""
        guild_id = ctx.guild.id
        log.info(f"[{guild_id}] Chamando play_next.")

        if guild_id in self.music_queues and self.music_queues[guild_id]:
            song_request = self.music_queues[guild_id].pop(0)
            log.info(f"[{guild_id}] Próxima música da fila: {song_request['title']}")

            try:
                log.debug(f"[{guild_id}] Agendando extração com yt-dlp para: {song_request['query']}")

                info = await asyncio.to_thread(
                    ydl_extract_info_sync, self.ydl_options, song_request['query']
                )

                if not info or 'entries' not in info or not info['entries']:
                    log.warning(f"[{guild_id}] yt-dlp não retornou 'entries' para: {song_request['title']}")
                    # No change needed here, self.message_cog will now work via the property
                    embed = self.message_cog.create_embed(
                        f"Não consegui encontrar ou o vídeo está indisponível: `{song_request['title']}`. Pulando.",
                        type="error")
                    await self.message_cog.send_message(ctx, embed)
                    await self.play_next(ctx)
                    return

                video_info = info['entries'][0]
                url = video_info['url']
                title = video_info.get('title', song_request['title'])
                log.info(f"[{guild_id}] URL do stream extraída com sucesso.")

                source = discord.FFmpegPCMAudio(url, **self.ffmpeg_options)
                ctx.voice_client.play(source, after=lambda err: self.handle_after_play(err, ctx))

                embed = self.message_cog.create_embed(
                    f"Tocando agora: **{title}**\n(Pedido por: {song_request['requester']})")
                await self.message_cog.send_message(ctx, embed)

            except Exception as e:
                log.error(f"[{guild_id}] Erro GERAL em play_next para '{song_request['title']}'", exc_info=True)
                embed = self.message_cog.create_embed(
                    f"Ocorreu um erro crítico ao tentar tocar: `{song_request['title']}`. Pulando.", type="error")
                await self.message_cog.send_message(ctx, embed)
                await self.play_next(ctx)
        else:
            log.info(f"[{guild_id}] Fila de músicas terminada.")
            embed = self.message_cog.create_embed("Fila de músicas terminada.")
            await self.message_cog.send_message(ctx, embed)

    @commands.command(name='play', aliases=['p', 'tocar'],
                      help='Toca uma música ou playlist. Playlists são embaralhadas automaticamente.')
    async def play(self, ctx, *, search: str):
        guild_id = ctx.guild.id
        log.info(f"[{guild_id}] Comando 'play' recebido de {ctx.author} com a busca: '{search}'")

        if not ctx.author.voice:
            embed = self.message_cog.create_embed("Você precisa estar em um canal de voz para usar este comando!",
                                                  type="error")
            await self.message_cog.send_message(ctx, embed)
            return

        voice_channel = ctx.author.voice.channel
        if not ctx.voice_client:
            try:
                await voice_channel.connect()
            except Exception as e:
                log.error(f"[{guild_id}] Falha ao conectar ao canal de voz.", exc_info=True)
                embed = self.message_cog.create_embed("Não consegui me conectar ao seu canal de voz.", type="error")
                await self.message_cog.send_message(ctx, embed)
                return

        spotify_playlist_pattern = r"open\.spotify\.com/playlist/"
        youtube_playlist_pattern = r"(youtube\.com/playlist\?list=|music\.youtube\.com/playlist\?list=)"

        async with ctx.typing():
            # --- Lógica para Playlists do Spotify ---
            if re.search(spotify_playlist_pattern, search):
                if not self.spotify_client:
                    embed = self.message_cog.create_embed("Desculpe, a integração com o Spotify não está configurada.",
                                                          type="error")
                    await self.message_cog.send_message(ctx, embed)
                    return
                try:
                    playlist_id = search.split("/")[-1].split("?")[0]
                    # --- CORREÇÃO: Executa a chamada bloqueante em uma thread separada ---
                    all_tracks = await asyncio.to_thread(
                        spotify_get_playlist_tracks_sync, self.spotify_client, playlist_id
                    )
                    tracks_to_add = [item for item in all_tracks if item.get('track')]
                    if not tracks_to_add:
                        await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                            "Essa playlist parece estar vazia ou é privada.", type="error"))
                        return

                    random.shuffle(tracks_to_add)
                    if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                    for item in tracks_to_add:
                        track = item['track']
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        self.music_queues[guild_id].append({'type': 'search', 'query': query,
                                                            'title': f"{track['name']} - {track['artists'][0]['name']}",
                                                            'requester': ctx.author.mention})

                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        f"Playlist do Spotify encontrada! Adicionando e embaralhando **{len(tracks_to_add)}** músicas à fila...",
                        type="success"))
                except Exception as e:
                    log.error(f"[{guild_id}] Erro ao processar playlist do Spotify.", exc_info=True)
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Ocorreu um erro ao buscar a playlist do Spotify. Verifique o link.", type="error"))
                    return

            # --- Lógica para Playlists do YouTube ---
            elif re.search(youtube_playlist_pattern, search):
                try:
                    # --- CORREÇÃO: Executa a chamada bloqueante em uma thread separada ---
                    info = await asyncio.to_thread(ydl_extract_info_sync, self.ydl_options, search)
                    if 'entries' not in info or not info['entries']:
                        await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                            "Não encontrei vídeos nesta playlist.", type="error"))
                        return

                    tracks_to_add = [entry for entry in info['entries'] if entry and entry.get('webpage_url')]
                    if not tracks_to_add:
                        await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                            "Não encontrei vídeos válidos nesta playlist.", type="error"))
                        return

                    random.shuffle(tracks_to_add)
                    if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                    for entry in tracks_to_add:
                        self.music_queues[guild_id].append({'type': 'search', 'query': entry['webpage_url'],
                                                            'title': entry.get('title', 'Título desconhecido'),
                                                            'requester': ctx.author.mention})

                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        f"Playlist do YouTube encontrada! Adicionando e embaralhando **{len(tracks_to_add)}** músicas à fila...",
                        type="success"))
                except Exception as e:
                    log.error(f"[{guild_id}] Erro ao processar playlist do YouTube.", exc_info=True)
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Ocorreu um erro ao buscar a playlist do YouTube. Verifique o link.", type="error"))
                    return

            # --- Lógica para Músicas Individuais ou Termos de Busca ---
            else:
                song_info = {'type': 'search', 'query': f"ytsearch:{search}", 'title': search,
                             'requester': ctx.author.mention}
                if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                self.music_queues[guild_id].append(song_info)
                await self.message_cog.send_message(ctx,
                                                    self.message_cog.create_embed(f"Adicionado à fila: **{search}**",
                                                                                  type="success"))

        # --- Inicia o Player se ele não estiver ativo ---
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            log.info(f"[{guild_id}] Player não está ativo. Iniciando play_next a partir do comando play.")
            await self.play_next(ctx)

    @commands.command(name='skip', aliases=['pular'], help='Pula para a próxima música da fila.')
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()  # Aciona o callback 'after' que chama play_next()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música pulada!", type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Não há nenhuma música tocando para pular.", type="error"))

    @commands.command(name='queue', aliases=['q', 'fila'], help='Mostra as próximas 10 músicas na fila.')
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.music_queues or not self.music_queues[guild_id]:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("A fila de músicas está vazia!"))
            return

        queue_list = ""
        for i, song in enumerate(self.music_queues[guild_id][:10]):
            queue_list += f"`{i + 1}.` {song['title']}\n"

        embed = self.message_cog.create_embed(queue_list, title="🎵 Fila de Músicas")
        embed.set_footer(text=f"Total de {len(self.music_queues[guild_id])} músicas na fila.")
        await self.message_cog.send_message(ctx, embed)

    @commands.command(name='pause', aliases=['pausar'], help='Pausa a música que está tocando no momento.')
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música pausada."))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Não há música tocando para pausar.",
                                                                                   type="error"))

    @commands.command(name='resume', aliases=['continuar'], help='Retoma a música que estava pausada.')
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música retomada."))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("A música não está pausada.",
                                                                                   type="error"))

    @commands.command(name='join', aliases=['entrar'], help='Faz o bot entrar no seu canal de voz atual.')
    async def join(self, ctx):
        if not ctx.author.voice:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Você precisa estar em um canal de voz para eu poder entrar!", type="error"))
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
        await self.message_cog.send_message(ctx,
                                            self.message_cog.create_embed(f"Entrei no canal: **{voice_channel.name}**"))

    @commands.command(name='stop', aliases=['parar'], help='Para a música completamente e limpa a fila de reprodução.')
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            if guild_id in self.music_queues: self.music_queues[guild_id] = []
            ctx.voice_client.stop()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música parada e fila limpa!",
                                                                                   type="success"))

    @commands.command(name='clear', aliases=['limpar'],
                      help='Limpa todas as músicas da fila, mas não para a música atual.')
    async def clear(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            self.music_queues[guild_id] = []
            await self.message_cog.send_message(ctx,
                                                self.message_cog.create_embed("Fila de músicas limpa!", type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("A fila já está vazia."))

    @commands.command(name='shuffle', aliases=['misturar', 'embaralhar'],
                      help='Embaralha a ordem das músicas que já estão na fila.')
    async def shuffle(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and len(self.music_queues[guild_id]) > 1:
            random.shuffle(self.music_queues[guild_id])
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "A fila de músicas foi embaralhada com sucesso!", type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Não há músicas suficientes na fila para embaralhar."))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Listener para desconectar o bot quando ele fica sozinho no canal."""
        if member.id == self.bot.user.id: return

        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.is_connected(): return

        # Se o bot for o único membro restante no canal de voz
        if len(voice_client.channel.members) == 1:
            guild_id = member.guild.id
            log.info(f"[{guild_id}] Bot ficou sozinho no canal de voz. Agendando desconexão.")

            # Limpa a fila e para a música
            if guild_id in self.music_queues: self.music_queues[guild_id] = []
            if voice_client.is_playing() or voice_client.is_paused(): voice_client.stop()

            # Envia uma mensagem de despedida se tiver um contexto recente
            if guild_id in self.last_ctx:
                ctx = self.last_ctx[guild_id]
                embed = self.message_cog.create_embed("Fui deixado sozinho, então estou saindo. A fila foi limpa!")
                await self.message_cog.send_message(ctx, embed)

            await asyncio.sleep(5)  # Pequena espera antes de desconectar
            if voice_client.is_connected():
                await voice_client.disconnect()
                log.info(f"[{guild_id}] Bot desconectado de {member.guild.name} por ficar sozinho.")


async def setup(bot: commands.Bot):
    """Função que o discord.py chama para carregar a cog."""
    await bot.add_cog(MusicCog(bot))