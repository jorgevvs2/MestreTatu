# -*- coding: utf-8 -*-
import os
import random
import re
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy # Importa a biblioteca do Spotify
from spotipy.oauth2 import SpotifyClientCredentials # Para autenticação


from dotenv import load_dotenv

load_dotenv()

# --- Configuração Inicial ---

# Pega o token do arquivo .env
TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Configura o cliente do Spotify
try:
    spotify_client = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET)
    )
except Exception as e:
    spotify_client = None
    print(f"Erro ao inicializar o cliente Spotify: {e}. Verifique as credenciais.")



# 2. DEFINIÇÃO DAS INTENÇÕES (INTENTS)
# As intenções permitem que o bot receba certos tipos de eventos do Discord.
# message_content é necessária para ler o conteúdo das mensagens (comandos).
# guilds e voice_states são necessárias para gerenciar canais de voz.
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

# 3. CRIAÇÃO DA INSTÂNCIA DO BOT
# Usamos '!' como prefixo para os comandos. Você pode mudar para o que preferir.
bot = commands.Bot(command_prefix='.', intents=intents,
                   help_command=None)  # Desativamos o comando de ajuda padrão para criar um personalizado se quisermos

music_queues = {}

# --- Configuration for yt-dlp and FFmpeg ---
COOKIE_FILE_PATH = 'cookies.txt'
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extractor_args': {
        'youtube': {
            'formats': 'missing_pot'
        }
    },
}

# Check for cookies.txt and ensure it is a FILE, not a directory
if os.path.exists(COOKIE_FILE_PATH):
    if os.path.isfile(COOKIE_FILE_PATH):
        print("INFO: Arquivo de cookies encontrado. Usando para autenticação.")
        YDL_OPTIONS['cookiefile'] = COOKIE_FILE_PATH
    else:
        print(f"AVISO: O caminho '{COOKIE_FILE_PATH}' existe, mas é um diretório, não um arquivo. Ignorando.")
else:
    print(f"AVISO: O arquivo de cookies '{COOKIE_FILE_PATH}' não foi encontrado.")
    print("O bot funcionará, mas não poderá acessar conteúdo exclusivo do YouTube Premium.")


# Opções para o FFmpeg: são passadas antes do input para garantir reconexão em caso de falha.
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',  # '-vn' significa que não queremos o vídeo, apenas o áudio.
}


# --- FUNÇÃO AUXILIAR PARA TOCAR A PRÓXIMA MÚSICA ---

async def play_next(ctx):
    """
    Função auxiliar que busca a URL real da música (se necessário) e a toca.
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        # Pega a próxima música da fila
        song_request = music_queues[guild_id].pop(0)

        # Busca o vídeo no YouTube usando yt-dlp
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                # Usa a query guardada para buscar a música
                info = ydl.extract_info(song_request['query'], download=False)['entries'][0]
            except Exception as e:
                await ctx.send(f"❌ Não consegui encontrar: `{song_request['title']}`. Pulando.")
                print(f"Erro ao buscar com yt-dlp: {e}")
                # Tenta tocar a próxima da fila
                await play_next(ctx)
                return

        url = info['url']
        title = info['title']

        # Cria a fonte de áudio e a toca
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

        await ctx.send(f'🎶 Tocando agora: **{title}** (Pedido por: {song_request["requester"]})')
    else:
        await ctx.send("Fila de músicas terminada.")


# --- EVENTOS DO BOT ---

@bot.event
async def on_ready():
    """
    Evento que é acionado quando o bot está online e pronto para uso.
    """
    print(f'Bot {bot.user.name} está online e pronto!')
    print(f'ID do Bot: {bot.user.id}')
    print('-----------------------------------------')
    # Muda o status do bot para "Ouvindo !play"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play"))


@bot.command(name='play', aliases=['p', 'tocar'], help='Toca uma música ou playlist do Spotify/YouTube.')
async def play(ctx, *, search: str):
    """
    Comando principal para tocar música.
    - Detecta se é um link de playlist do Spotify ou YouTube.
    - Busca a música/playlist.
    - Adiciona à fila e começa a tocar se a fila estiver vazia.
    """
    if not ctx.author.voice:
        await ctx.send("Você precisa estar em um canal de voz para usar este comando!")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    if not voice_client:
        voice_client = await voice_channel.connect()

    # Padrões de URL para playlists
    spotify_playlist_pattern = r"open\.spotify\.com/playlist/"
    youtube_playlist_pattern = r"(youtube\.com/playlist\?list=|music\.youtube\.com/playlist\?list=)"

    # --- LÓGICA DE DETECÇÃO APRIMORADA ---

    # 1. Verifica se é uma playlist do Spotify
    if re.search(spotify_playlist_pattern, search):
        if not spotify_client:
            await ctx.send("❌ Desculpe, a integração com o Spotify não está configurada corretamente.")
            return

        await ctx.send("🔎 Analisando playlist do Spotify... Isso pode levar um momento para playlists grandes.")
        try:
            playlist_id = search.split("/")[-1].split("?")[0]

            # --- LÓGICA DE PAGINAÇÃO ADICIONADA AQUI ---
            all_tracks = []
            results = spotify_client.playlist_tracks(playlist_id)
            all_tracks.extend(results['items'])

            # Continua buscando a próxima página de resultados enquanto houver uma
            while results['next']:
                results = spotify_client.next(results)
                all_tracks.extend(results['items'])

            tracks_to_add = all_tracks
            # --- FIM DA CORREÇÃO ---

            if not tracks_to_add:
                await ctx.send("Essa playlist parece estar vazia ou é privada.")
                return

            await ctx.send(f"✅ Playlist do Spotify encontrada! Adicionando **{len(tracks_to_add)}** músicas à fila...")

            guild_id = ctx.guild.id
            if guild_id not in music_queues:
                music_queues[guild_id] = []

            for item in tracks_to_add:
                track = item.get('track')
                if track:
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    song_info = {
                        'type': 'search',
                        'query': query,
                        'title': f"{track['name']} - {track['artists'][0]['name']}",
                        'requester': ctx.author.mention
                    }
                    music_queues[guild_id].append(song_info)

        except Exception as e:
            await ctx.send("❌ Ocorreu um erro ao buscar a playlist do Spotify. Verifique o link.")
            print(f"Erro no Spotify: {e}")
            return

    # 2. Verifica se é uma playlist do YouTube/YouTube Music
    elif re.search(youtube_playlist_pattern, search):
        await ctx.send("🔎 Analisando playlist do YouTube... Isso pode levar um momento.")
        try:
            # Usamos o yt-dlp para extrair informações da playlist, mas sem baixar
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(search, download=False)

            if 'entries' not in info or not info['entries']:
                await ctx.send("❌ Não encontrei vídeos nesta playlist ou o link é inválido.")
                return

            tracks_to_add = info['entries']
            await ctx.send(f"✅ Playlist do YouTube encontrada! Adicionando **{len(tracks_to_add)}** músicas à fila...")

            guild_id = ctx.guild.id
            if guild_id not in music_queues:
                music_queues[guild_id] = []

            for entry in tracks_to_add:
                # Para playlists do YouTube, já temos a informação, então a busca será direta pelo ID
                song_info = {
                    'type': 'search',
                    'query': entry['webpage_url'],  # Usar a URL direta é mais confiável
                    'title': entry.get('title', 'Título desconhecido'),
                    'requester': ctx.author.mention
                }
                music_queues[guild_id].append(song_info)

        except Exception as e:
            await ctx.send("❌ Ocorreu um erro ao buscar a playlist do YouTube. Verifique o link.")
            print(f"Erro no YouTube Playlist: {e}")
            return

    # 3. Se não for nenhuma playlist, trata como uma busca normal
    else:
        await ctx.send(f'🔎 Buscando por: `{search}`...')
        song_info = {
            'type': 'search',
            'query': f"ytsearch:{search}",
            'title': search,
            'requester': ctx.author.mention
        }
        guild_id = ctx.guild.id
        if guild_id not in music_queues:
            music_queues[guild_id] = []
        music_queues[guild_id].append(song_info)
        await ctx.send(f"✅ Adicionado à fila: **{search}**")

    # Inicia a reprodução se nada estiver tocando
    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_next(ctx)


@bot.command(name='leave', aliases=['sair', 'disconnect'], help='Faz o bot sair do canal de voz.')
async def leave(ctx):
    """Comando para o bot sair do canal de voz e limpar a fila."""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_connected():
        guild_id = ctx.guild.id
        if guild_id in music_queues:
            music_queues[guild_id] = []  # Limpa a fila
        await voice_client.disconnect()
        await ctx.send("👋 Saí do canal de voz e limpei a fila!")
    else:
        await ctx.send("Eu não estou em um canal de voz no momento.")


@bot.command(name='skip', aliases=['pular'], help='Pula a música que está tocando.')
async def skip(ctx):
    """Pula a música atual e toca a próxima da fila."""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()  # O 'stop' aciona a função 'after' no play, que chama play_next
        await ctx.send("⏭️ Música pulada!")
    else:
        await ctx.send("Não há nenhuma música tocando para pular.")


@bot.command(name='queue', aliases=['q', 'fila'], help='Mostra a fila de músicas.')
async def queue(ctx):
    """Exibe as próximas músicas na fila."""
    guild_id = ctx.guild.id
    if guild_id not in music_queues or not music_queues[guild_id]:
        await ctx.send("A fila de músicas está vazia!")
        return

    # Cria uma mensagem formatada com a lista de músicas
    queue_list = ""
    for i, song in enumerate(music_queues[guild_id][:10]):  # Mostra até 10 músicas
        queue_list += f"`{i + 1}.` {song['title']}\n"

    embed = discord.Embed(
        title="🎵 Fila de Músicas",
        description=queue_list,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Total de {len(music_queues[guild_id])} músicas na fila.")
    await ctx.send(embed=embed)


@bot.command(name='pause', aliases=['pausar'], help='Pausa a música atual.')
async def pause(ctx):
    """Pausa a reprodução da música."""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Música pausada.")
    else:
        await ctx.send("Não há música tocando para pausar.")


@bot.command(name='resume', aliases=['continuar'], help='Continua a música pausada.')
async def resume(ctx):
    """Continua a reprodução da música."""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Música retomada.")
    else:
        await ctx.send("A música não está pausada.")


@bot.command(name='join', aliases=['entrar'], help='Faz o bot entrar no seu canal de voz.')
async def join(ctx):
    """Faz o bot entrar no canal de voz do autor do comando."""
    # Verifica se o autor do comando está em um canal de voz
    if not ctx.author.voice:
        await ctx.send("Você precisa estar em um canal de voz para eu poder entrar!")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    # Se o bot já estiver em um canal, ele se move para o canal do autor.
    # Se não, ele se conecta.
    if voice_client and voice_client.is_connected():
        await voice_client.move_to(voice_channel)
        await ctx.send(f"Movi para o canal: **{voice_channel.name}**")
    else:
        await voice_channel.connect()
        await ctx.send(f"Entrei no canal: **{voice_channel.name}**")


@bot.command(name='stop', aliases=['parar'], help='Para a música e limpa a fila.')
async def stop(ctx):
    """Para a reprodução, limpa a fila, mas não sai do canal de voz."""
    voice_client = ctx.voice_client
    guild_id = ctx.guild.id

    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        # Limpa a fila de músicas do servidor
        if guild_id in music_queues:
            music_queues[guild_id] = []

        # Para a música atual (isso também impede que a próxima música comece)
        voice_client.stop()
        await ctx.send("⏹️ Música parada e fila limpa!")
    else:
        await ctx.send("Não há nenhuma música tocando no momento.")


@bot.command(name='clear', aliases=['limpar'], help='Limpa todas as músicas da fila.')
async def clear(ctx):
    """Limpa a fila de músicas sem parar a música que está tocando."""
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        music_queues[guild_id] = []
        await ctx.send("🧹 Fila de músicas limpa!")
    else:
        await ctx.send("A fila já está vazia.")


@bot.command(name='ds', help='Toca a playlist temática de Dark Souls.')
async def ds(ctx):
    """
    Carrega uma playlist específica do Spotify (definida no .env),
    embaralha as músicas e as adiciona à fila.
    """
    playlist_url = os.getenv('DS_PLAYLIST')
    if not playlist_url:
        await ctx.send("❌ A URL da playlist 'DS_PLAYLIST' não foi encontrada no arquivo .env.")
        print("ERRO: A variável de ambiente DS_PLAYLIST não está definida.")
        return

    if not ctx.author.voice:
        await ctx.send("Você precisa estar em um canal de voz para usar este comando!")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    if not voice_client:
        voice_client = await voice_channel.connect()

    if not spotify_client:
        await ctx.send("❌ Desculpe, a integração com o Spotify não está configurada corretamente.")
        return

    await ctx.send(f"🔥 Carregando a playlist Chama do Dark Souls... Isso pode levar um momento para playlists grandes.")

    try:
        playlist_id = playlist_url.split("/")[-1].split("?")[0]

        # --- LÓGICA DE PAGINAÇÃO CORRIGIDA ---
        all_tracks = []
        results = spotify_client.playlist_tracks(playlist_id)
        all_tracks.extend(results['items'])

        # Continua buscando a próxima página de resultados enquanto houver uma
        while results['next']:
            results = spotify_client.next(results)
            all_tracks.extend(results['items'])

        tracks_to_add = all_tracks
        # --- FIM DA CORREÇÃO ---

        if not tracks_to_add:
            await ctx.send("A playlist parece estar vazia ou é privada.")
            return

        random.shuffle(tracks_to_add)

        guild_id = ctx.guild.id
        if guild_id not in music_queues:
            music_queues[guild_id] = []

        for item in tracks_to_add:
            track = item.get('track')
            if track:
                query = f"{track['name']} {track['artists'][0]['name']}"
                song_info = {
                    'type': 'search',
                    'query': query,
                    'title': f"{track['name']} - {track['artists'][0]['name']}",
                    'requester': ctx.author.mention
                }
                music_queues[guild_id].append(song_info)

        await ctx.send(f"✅ Playlist Chama do Dark Souls com **{len(tracks_to_add)}** músicas adicionada e embaralhada!")

    except Exception as e:
        await ctx.send("❌ Ocorreu um erro ao buscar a playlist. Verifique se o link em DS_PLAYLIST é válido.")
        print(f"Erro no comando .ds: {e}")
        return

    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_next(ctx)

@bot.command(name='shuffle', aliases=['misturar', 'embaralhar'], help='Embaralha a ordem das músicas na fila.')
async def shuffle(ctx):
    """Embaralha a fila de músicas atual."""
    guild_id = ctx.guild.id

    # Verifica se existe uma fila para o servidor e se ela tem mais de uma música
    if guild_id in music_queues and len(music_queues[guild_id]) > 1:
        # A função random.shuffle modifica a lista diretamente (in-place)
        random.shuffle(music_queues[guild_id])
        await ctx.send("🔀 A fila de músicas foi embaralhada com sucesso!")
    elif guild_id in music_queues and len(music_queues[guild_id]) <= 1:
        await ctx.send("Não há músicas suficientes na fila para embaralhar.")
    else:
        await ctx.send("A fila está vazia, não há o que misturar.")

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("ERRO: Token inválido. Verifique o token no seu arquivo.")
    except Exception as e:
        print(f"Ocorreu um erro ao iniciar o bot: {e}")

