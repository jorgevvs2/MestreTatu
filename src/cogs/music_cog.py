# D:/Codes/TatuBeats/src/cogs/music_cog.py

import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import re
import logging

# Obtém um logger específico para este módulo.
log = logging.getLogger(__name__)


class MusicCog(commands.Cog, name="Música"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spotify_client = bot.spotify_client
        self.ydl_options = bot.ydl_options
        self.ffmpeg_options = bot.ffmpeg_options
        self.music_queues = {}
        self.last_ctx = {}
        self.message_cog = None
        log.info("MusicCog inicializado.")

    async def cog_before_invoke(self, ctx: commands.Context):
        self.last_ctx[ctx.guild.id] = ctx
        if not self.message_cog:
            self.message_cog = self.bot.get_cog('MessageCog')
            if not self.message_cog:
                log.critical("AVISO CRÍTICO: [MusicCog] não conseguiu encontrar o MessageCog.")

    def handle_after_play(self, error, ctx):
        """Função de callback segura chamada após uma música terminar."""
        if error:
            log.error(f"[{ctx.guild.id}] Erro no callback 'after' da música: {error}", exc_info=True)
        else:
            log.info(f"[{ctx.guild.id}] Música terminou normalmente. Chamando próximo da fila.")

        # Chama a próxima música de forma segura a partir de um thread síncrono.
        asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        log.info(f"[{guild_id}] Chamando play_next.")

        if guild_id in self.music_queues and self.music_queues[guild_id]:
            song_request = self.music_queues[guild_id].pop(0)
            log.info(f"[{guild_id}] Próxima música da fila: {song_request['title']}")

            try:
                log.debug(f"[{guild_id}] Iniciando extração com yt-dlp para: {song_request['query']}")
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    info = ydl.extract_info(song_request['query'], download=False)

                if not info or 'entries' not in info or not info['entries']:
                    log.warning(f"[{guild_id}] yt-dlp não retornou 'entries' para: {song_request['title']}")
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
                log.debug(f"[{guild_id}] URL: {url[:70]}...")

                log.debug(f"[{guild_id}] Criando source com FFmpegPCMAudio.")
                source = discord.FFmpegPCMAudio(url, **self.ffmpeg_options)

                log.info(f"[{guild_id}] Chamando voice_client.play() para tocar '{title}'.")
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
            log.warning(f"[{guild_id}] Usuário {ctx.author} tentou usar 'play' sem estar em um canal de voz.")
            embed = self.message_cog.create_embed("Você precisa estar em um canal de voz para usar este comando!",
                                                  type="error")
            await self.message_cog.send_message(ctx, embed)
            return

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if not voice_client:
            log.info(f"[{guild_id}] Bot não está no canal de voz. Conectando a '{voice_channel.name}'.")
            try:
                voice_client = await voice_channel.connect()
                log.info(f"[{guild_id}] Conectado com sucesso.")
            except Exception as e:
                log.error(f"[{guild_id}] Falha ao conectar ao canal de voz.", exc_info=True)
                embed = self.message_cog.create_embed("Não consegui me conectar ao seu canal de voz.", type="error")
                await self.message_cog.send_message(ctx, embed)
                return

        log.debug(f"[{guild_id}] Voice client está pronto.")

        spotify_playlist_pattern = r"open\.spotify\.com/playlist/"
        youtube_playlist_pattern = r"(youtube\.com/playlist\?list=|music\.youtube\.com/playlist\?list=)"

        # --- Lógica para Playlists do Spotify ---
        if re.search(spotify_playlist_pattern, search):
            if not self.spotify_client:
                log.error(f"[{guild_id}] Tentativa de usar playlist do Spotify, mas o cliente não está configurado.")
                embed = self.message_cog.create_embed(
                    "Desculpe, a integração com o Spotify não está configurada corretamente.", type="error")
                await self.message_cog.send_message(ctx, embed)
                return

            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Analisando playlist do Spotify... Isso pode levar um momento."), transient=True)
            try:
                playlist_id = search.split("/")[-1].split("?")[0]
                all_tracks = []
                results = self.spotify_client.playlist_tracks(playlist_id)
                all_tracks.extend(results['items'])
                while results['next']:
                    results = self.spotify_client.next(results)
                    all_tracks.extend(results['items'])

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
                    song_info = {'type': 'search', 'query': query,
                                 'title': f"{track['name']} - {track['artists'][0]['name']}",
                                 'requester': ctx.author.mention}
                    self.music_queues[guild_id].append(song_info)

                log.info(
                    f"[{guild_id}] Adicionadas {len(tracks_to_add)} músicas da playlist do Spotify. Tamanho da fila agora: {len(self.music_queues[guild_id])}")
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
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Analisando playlist do YouTube... Isso pode levar um momento."), transient=True)
            try:
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    info = ydl.extract_info(search, download=False)

                if 'entries' not in info or not info['entries']:
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Não encontrei vídeos nesta playlist, o link é inválido ou a playlist está vazia.",
                        type="error"))
                    return

                tracks_to_add = [entry for entry in info['entries'] if entry and entry.get('webpage_url')]

                if not tracks_to_add:
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Não encontrei vídeos válidos nesta playlist.", type="error"))
                    return

                random.shuffle(tracks_to_add)

                if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                for entry in tracks_to_add:
                    song_info = {'type': 'search', 'query': entry['webpage_url'],
                                 'title': entry.get('title', 'Título desconhecido'), 'requester': ctx.author.mention}
                    self.music_queues[guild_id].append(song_info)

                log.info(
                    f"[{guild_id}] Adicionadas {len(tracks_to_add)} músicas da playlist do YouTube. Tamanho da fila agora: {len(self.music_queues[guild_id])}")
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
            log.info(
                f"[{guild_id}] Adicionado à fila: '{search}'. Tamanho da fila agora: {len(self.music_queues[guild_id])}")
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(f"Adicionado à fila: **{search}**",
                                                                                   type="success"))

        # --- Inicia o Player ---
        log.debug(
            f"[{guild_id}] Verificando estado do player: is_playing={voice_client.is_playing()}, is_paused={voice_client.is_paused()}")
        if not voice_client.is_playing() and not voice_client.is_paused():
            log.info(f"[{guild_id}] Player não está ativo. Iniciando play_next a partir do comando play.")
            # --- CORREÇÃO CRÍTICA ---
            # Esta linha estava faltando. Ela efetivamente inicia o player.
            await self.play_next(ctx)

    @commands.command(name='skip', aliases=['pular'], help='Pula para a próxima música da fila.')
    async def skip(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            # Parar a música aciona o callback 'after' que chama play_next()
            voice_client.stop()
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
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música pausada."))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Não há música tocando para pausar.",
                                                                                   type="error"))

    @commands.command(name='resume', aliases=['continuar'], help='Retoma a música que estava pausada.')
    async def resume(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
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
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.move_to(voice_channel)
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                f"Movi para o canal: **{voice_channel.name}**"))
        else:
            await voice_channel.connect()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                f"Entrei no canal: **{voice_channel.name}**"))

    @commands.command(name='stop', aliases=['parar'], help='Para a música completamente e limpa a fila de reprodução.')
    async def stop(self, ctx):
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            if guild_id in self.music_queues: self.music_queues[guild_id] = []
            voice_client.stop()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música parada e fila limpa!",
                                                                                   type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Não há nenhuma música tocando no momento.", type="error"))

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

    @commands.command(name='ds', help='Toca a playlist temática de Dark Souls (definida no .env).')
    async def ds(self, ctx):
        playlist_url = os.getenv('DS_PLAYLIST')
        if not playlist_url:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "A URL da playlist 'DS_PLAYLIST' não foi encontrada no arquivo .env.", type="error"))
            return
        await self.play(ctx, search=playlist_url)

    @commands.command(name='wicked', help='Toca a playlist temática de Wicked (definida no .env).')
    async def wicked(self, ctx):
        playlist_url = os.getenv('WICKED_PLAYLIST')
        if not playlist_url:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "A URL da playlist 'WICKED_PLAYLIST' não foi encontrada no arquivo .env.", type="error"))
            return
        await self.play(ctx, search=playlist_url)

    @commands.command(name='xama', help='Toca a playlist temática de Xamã (definida no .env).')
    async def xama(self, ctx):
        playlist_url = os.getenv('XAMA_PLAYLIST')
        if not playlist_url:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "A URL da playlist 'XAMA_PLAYLIST' não foi encontrada no arquivo .env.", type="error"))
            return
        await self.play(ctx, search=playlist_url)

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
        if member.id == self.bot.user.id: return
        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.is_connected(): return

        if len(voice_client.channel.members) == 1:
            guild_id = member.guild.id
            if guild_id in self.music_queues: self.music_queues[guild_id] = []
            if voice_client.is_playing() or voice_client.is_paused(): voice_client.stop()
            if guild_id in self.last_ctx:
                ctx = self.last_ctx[guild_id]
                embed = self.message_cog.create_embed("Fui deixado sozinho, então estou saindo. A fila foi limpa!")
                await self.message_cog.send_message(ctx, embed)
            await asyncio.sleep(5)
            if voice_client.is_connected():
                await voice_client.disconnect()
                log.info(f"Bot disconnected from {member.guild.name} due to being alone.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))