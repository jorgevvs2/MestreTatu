import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import re


class MusicCog(commands.Cog):
    def __init__(self, bot, spotify_client, ydl_options, ffmpeg_options):
        self.bot = bot
        self.spotify_client = spotify_client
        self.ydl_options = ydl_options
        self.ffmpeg_options = ffmpeg_options
        self.music_queues = {}
        self.last_ctx = {}
        self.message_cog = self.bot.get_cog('MessageCog')

    async def cog_before_invoke(self, ctx: commands.Context):
        self.last_ctx[ctx.guild.id] = ctx
        if not self.message_cog:
            self.message_cog = self.bot.get_cog('MessageCog')

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            song_request = self.music_queues[guild_id].pop(0)

            with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                try:
                    info = ydl.extract_info(song_request['query'], download=False)['entries'][0]
                except Exception as e:
                    embed = self.message_cog.create_embed(
                        f"Não consegui encontrar: `{song_request['title']}`. Pulando.", type="error")
                    await self.message_cog.send_message(ctx, embed)
                    print(f"Erro ao buscar com yt-dlp: {e}")
                    await self.play_next(ctx)
                    return

            url = info['url']
            title = info['title']
            source = discord.FFmpegPCMAudio(url, **self.ffmpeg_options)
            ctx.voice_client.play(source,
                                  after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))

            embed = self.message_cog.create_embed(
                f"Tocando agora: **{title}**\n(Pedido por: {song_request['requester']})")
            await self.message_cog.send_message(ctx, embed)
        else:
            embed = self.message_cog.create_embed("Fila de músicas terminada.")
            await self.message_cog.send_message(ctx, embed)

    @commands.command(name='play', aliases=['p', 'tocar'])
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice:
            embed = self.message_cog.create_embed("Você precisa estar em um canal de voz para usar este comando!",
                                                  type="error")
            await self.message_cog.send_message(ctx, embed)
            return

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.voice_client
        if not voice_client:
            voice_client = await voice_channel.connect()

        spotify_playlist_pattern = r"open\.spotify\.com/playlist/"
        youtube_playlist_pattern = r"(youtube\.com/playlist\?list=|music\.youtube\.com/playlist\?list=)"

        if re.search(spotify_playlist_pattern, search):
            if not self.spotify_client:
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
                tracks_to_add = all_tracks

                if not tracks_to_add:
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Essa playlist parece estar vazia ou é privada.", type="error"))
                    return

                # Embaralha a playlist antes de adicionar
                random.shuffle(tracks_to_add)

                await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                    f"Playlist do Spotify encontrada! Adicionando e embaralhando **{len(tracks_to_add)}** músicas à fila...",
                    type="success"))
                guild_id = ctx.guild.id
                if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                for item in tracks_to_add:
                    track = item.get('track')
                    if track:
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        song_info = {'type': 'search', 'query': query,
                                     'title': f"{track['name']} - {track['artists'][0]['name']}",
                                     'requester': ctx.author.mention}
                        self.music_queues[guild_id].append(song_info)
            except Exception as e:
                await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                    "Ocorreu um erro ao buscar a playlist do Spotify. Verifique o link.", type="error"))
                print(f"Erro no Spotify: {e}")
                return

        elif re.search(youtube_playlist_pattern, search):
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Analisando playlist do YouTube... Isso pode levar um momento."), transient=True)
            try:
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    info = ydl.extract_info(search, download=False)
                if 'entries' not in info or not info['entries']:
                    await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                        "Não encontrei vídeos nesta playlist ou o link é inválido.", type="error"))
                    return
                tracks_to_add = info['entries']

                # Embaralha a playlist antes de adicionar
                random.shuffle(tracks_to_add)

                await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                    f"Playlist do YouTube encontrada! Adicionando e embaralhando **{len(tracks_to_add)}** músicas à fila...",
                    type="success"))
                guild_id = ctx.guild.id
                if guild_id not in self.music_queues: self.music_queues[guild_id] = []
                for entry in tracks_to_add:
                    song_info = {'type': 'search', 'query': entry['webpage_url'],
                                 'title': entry.get('title', 'Título desconhecido'), 'requester': ctx.author.mention}
                    self.music_queues[guild_id].append(song_info)
            except Exception as e:
                await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                    "Ocorreu um erro ao buscar a playlist do YouTube. Verifique o link.", type="error"))
                print(f"Erro no YouTube Playlist: {e}")
                return
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(f'Buscando por: `{search}`...'),
                                                transient=True)
            song_info = {'type': 'search', 'query': f"ytsearch:{search}", 'title': search,
                         'requester': ctx.author.mention}
            guild_id = ctx.guild.id
            if guild_id not in self.music_queues: self.music_queues[guild_id] = []
            self.music_queues[guild_id].append(song_info)
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(f"Adicionado à fila: **{search}**",
                                                                                   type="success"))

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self.play_next(ctx)

    @commands.command(name='leave', aliases=['sair', 'disconnect'])
    async def leave(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_connected():
            guild_id = ctx.guild.id
            if guild_id in self.music_queues: self.music_queues[guild_id] = []
            await voice_client.disconnect()
            await self.message_cog.send_message(ctx,
                                                self.message_cog.create_embed("Saí do canal de voz e limpei a fila!",
                                                                              type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Eu não estou em um canal de voz no momento.", type="error"))

    @commands.command(name='skip', aliases=['pular'])
    async def skip(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música pulada!", type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "Não há nenhuma música tocando para pular.", type="error"))

    @commands.command(name='queue', aliases=['q', 'fila'])
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

    @commands.command(name='pause', aliases=['pausar'])
    async def pause(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música pausada."))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Não há música tocando para pausar.",
                                                                                   type="error"))

    @commands.command(name='resume', aliases=['continuar'])
    async def resume(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("Música retomada."))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("A música não está pausada.",
                                                                                   type="error"))

    @commands.command(name='join', aliases=['entrar'])
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

    @commands.command(name='stop', aliases=['parar'])
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

    @commands.command(name='clear', aliases=['limpar'])
    async def clear(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            self.music_queues[guild_id] = []
            await self.message_cog.send_message(ctx,
                                                self.message_cog.create_embed("Fila de músicas limpa!", type="success"))
        else:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed("A fila já está vazia."))

    @commands.command(name='ds')
    async def ds(self, ctx):
        playlist_url = os.getenv('DS_PLAYLIST')
        if not playlist_url:
            await self.message_cog.send_message(ctx, self.message_cog.create_embed(
                "A URL da playlist 'DS_PLAYLIST' não foi encontrada no arquivo .env.", type="error"))
            return
        await self.play(ctx, search=playlist_url)

    @commands.command(name='shuffle', aliases=['misturar', 'embaralhar'])
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
                print(f"Bot disconnected from {member.guild.name} due to being alone.")


async def setup(bot):
    spotify_client = bot.spotify_client
    ydl_options = bot.ydl_options
    ffmpeg_options = bot.ffmpeg_options
    await bot.add_cog(MusicCog(bot, spotify_client, ydl_options, ffmpeg_options))