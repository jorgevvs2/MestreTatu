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

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            song_request = self.music_queues[guild_id].pop(0)

            with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                try:
                    info = ydl.extract_info(song_request['query'], download=False)['entries'][0]
                except Exception as e:
                    await ctx.send(f"❌ Não consegui encontrar: `{song_request['title']}`. Pulando.")
                    print(f"Erro ao buscar com yt-dlp: {e}")
                    await self.play_next(ctx)
                    return

            url = info['url']
            title = info['title']

            source = discord.FFmpegPCMAudio(url, **self.ffmpeg_options)
            ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))

            await ctx.send(f'🎶 Tocando agora: **{title}** (Pedido por: {song_request["requester"]})')
        else:
            await ctx.send("Fila de músicas terminada.")

    @commands.command(name='play', aliases=['p', 'tocar'], help='Toca uma música ou playlist do Spotify/YouTube.')
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice:
            await ctx.send("Você precisa estar em um canal de voz para usar este comando!")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if not voice_client:
            voice_client = await voice_channel.connect()

        spotify_playlist_pattern = r"open\.spotify\.com/playlist/"
        youtube_playlist_pattern = r"(youtube\.com/playlist\?list=|music\.youtube\.com/playlist\?list=)"

        if re.search(spotify_playlist_pattern, search):
            if not self.spotify_client:
                await ctx.send("❌ Desculpe, a integração com o Spotify não está configurada corretamente.")
                return

            await ctx.send("🔎 Analisando playlist do Spotify... Isso pode levar um momento para playlists grandes.")
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
                    await ctx.send("Essa playlist parece estar vazia ou é privada.")
                    return

                await ctx.send(f"✅ Playlist do Spotify encontrada! Adicionando **{len(tracks_to_add)}** músicas à fila...")
                guild_id = ctx.guild.id
                if guild_id not in self.music_queues:
                    self.music_queues[guild_id] = []

                for item in tracks_to_add:
                    track = item.get('track')
                    if track:
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        song_info = {
                            'type': 'search', 'query': query,
                            'title': f"{track['name']} - {track['artists'][0]['name']}",
                            'requester': ctx.author.mention
                        }
                        self.music_queues[guild_id].append(song_info)

            except Exception as e:
                await ctx.send("❌ Ocorreu um erro ao buscar a playlist do Spotify. Verifique o link.")
                print(f"Erro no Spotify: {e}")
                return

        elif re.search(youtube_playlist_pattern, search):
            await ctx.send("🔎 Analisando playlist do YouTube... Isso pode levar um momento.")
            try:
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    info = ydl.extract_info(search, download=False)

                if 'entries' not in info or not info['entries']:
                    await ctx.send("❌ Não encontrei vídeos nesta playlist ou o link é inválido.")
                    return

                tracks_to_add = info['entries']
                await ctx.send(f"✅ Playlist do YouTube encontrada! Adicionando **{len(tracks_to_add)}** músicas à fila...")
                guild_id = ctx.guild.id
                if guild_id not in self.music_queues:
                    self.music_queues[guild_id] = []

                for entry in tracks_to_add:
                    song_info = {
                        'type': 'search', 'query': entry['webpage_url'],
                        'title': entry.get('title', 'Título desconhecido'),
                        'requester': ctx.author.mention
                    }
                    self.music_queues[guild_id].append(song_info)

            except Exception as e:
                await ctx.send("❌ Ocorreu um erro ao buscar a playlist do YouTube. Verifique o link.")
                print(f"Erro no YouTube Playlist: {e}")
                return
        else:
            await ctx.send(f'🔎 Buscando por: `{search}`...')
            song_info = {
                'type': 'search', 'query': f"ytsearch:{search}",
                'title': search, 'requester': ctx.author.mention
            }
            guild_id = ctx.guild.id
            if guild_id not in self.music_queues:
                self.music_queues[guild_id] = []
            self.music_queues[guild_id].append(song_info)
            await ctx.send(f"✅ Adicionado à fila: **{search}**")

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self.play_next(ctx)

    @commands.command(name='leave', aliases=['sair', 'disconnect'], help='Faz o bot sair do canal de voz.')
    async def leave(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_connected():
            guild_id = ctx.guild.id
            if guild_id in self.music_queues:
                self.music_queues[guild_id] = []
            await voice_client.disconnect()
            await ctx.send("👋 Saí do canal de voz e limpei a fila!")
        else:
            await ctx.send("Eu não estou em um canal de voz no momento.")

    @commands.command(name='skip', aliases=['pular'], help='Pula a música que está tocando.')
    async def skip(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await ctx.send("⏭️ Música pulada!")
        else:
            await ctx.send("Não há nenhuma música tocando para pular.")

    @commands.command(name='queue', aliases=['q', 'fila'], help='Mostra a fila de músicas.')
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.music_queues or not self.music_queues[guild_id]:
            await ctx.send("A fila de músicas está vazia!")
            return

        queue_list = ""
        for i, song in enumerate(self.music_queues[guild_id][:10]):
            queue_list += f"`{i + 1}.` {song['title']}\n"

        embed = discord.Embed(title="🎵 Fila de Músicas", description=queue_list, color=discord.Color.blue())
        embed.set_footer(text=f"Total de {len(self.music_queues[guild_id])} músicas na fila.")
        await ctx.send(embed=embed)

    @commands.command(name='pause', aliases=['pausar'], help='Pausa a música atual.')
    async def pause(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("⏸️ Música pausada.")
        else:
            await ctx.send("Não há música tocando para pausar.")

    @commands.command(name='resume', aliases=['continuar'], help='Continua a música pausada.')
    async def resume(self, ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await ctx.send("▶️ Música retomada.")
        else:
            await ctx.send("A música não está pausada.")

    @commands.command(name='join', aliases=['entrar'], help='Faz o bot entrar no seu canal de voz.')
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("Você precisa estar em um canal de voz para eu poder entrar!")
            return
        voice_channel = ctx.author.voice.channel
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.move_to(voice_channel)
            await ctx.send(f"Movi para o canal: **{voice_channel.name}**")
        else:
            await voice_channel.connect()
            await ctx.send(f"Entrei no canal: **{voice_channel.name}**")

    @commands.command(name='stop', aliases=['parar'], help='Para a música e limpa a fila.')
    async def stop(self, ctx):
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            if guild_id in self.music_queues:
                self.music_queues[guild_id] = []
            voice_client.stop()
            await ctx.send("⏹️ Música parada e fila limpa!")
        else:
            await ctx.send("Não há nenhuma música tocando no momento.")

    @commands.command(name='clear', aliases=['limpar'], help='Limpa todas as músicas da fila.')
    async def clear(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            self.music_queues[guild_id] = []
            await ctx.send("🧹 Fila de músicas limpa!")
        else:
            await ctx.send("A fila já está vazia.")

    @commands.command(name='ds', help='Toca a playlist temática de Dark Souls.')
    async def ds(self, ctx):
        playlist_url = os.getenv('DS_PLAYLIST')
        if not playlist_url:
            await ctx.send("❌ A URL da playlist 'DS_PLAYLIST' não foi encontrada no arquivo .env.")
            return
        # Re-use the play command's logic to avoid code duplication
        await self.play(ctx, search=playlist_url)

    @commands.command(name='shuffle', aliases=['misturar', 'embaralhar'], help='Embaralha a ordem das músicas na fila.')
    async def shuffle(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and len(self.music_queues[guild_id]) > 1:
            random.shuffle(self.music_queues[guild_id])
            await ctx.send("🔀 A fila de músicas foi embaralhada com sucesso!")
        elif guild_id in self.music_queues and len(self.music_queues[guild_id]) <= 1:
            await ctx.send("Não há músicas suficientes na fila para embaralhar.")
        else:
            await ctx.send("A fila está vazia, não há o que misturar.")

async def setup(bot):
    # This function is called by discord.py when the extension is loaded.
    # We pass the bot instance and any other dependencies the cog needs.
    spotify_client = bot.spotify_client
    ydl_options = bot.ydl_options
    ffmpeg_options = bot.ffmpeg_options
    await bot.add_cog(MusicCog(bot, spotify_client, ydl_options, ffmpeg_options))
