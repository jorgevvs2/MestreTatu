PinoBeats 🎶

Um bot de música para Discord robusto e fácil de usar, construído com `discord.py` e containerizado com Docker. PinoBeats pode tocar suas músicas e playlists favoritas do YouTube e Spotify diretamente no seu canal de voz.

-   **Suporte a Múltiplas Fontes**: Toca músicas e playlists do YouTube, YouTube Music e Spotify.
-   **Controles Completos**: Comandos para tocar, pausar, pular, parar, gerenciar a fila e muito mais.
-   **Qualidade de Áudio**: Utiliza `yt-dlp` e `FFmpeg` para streaming de áudio de alta qualidade.
-   **Fácil de Hospedar**: Totalmente containerizado com Docker para uma configuração e implantação simples e consistente.
-   **Seguro**: Gerenciamento de segredos através de um arquivo `.env` para manter suas chaves de API seguras.
-   **Suporte a YouTube Premium**: Pode utilizar um arquivo de cookies para tocar conteúdo exclusivo do YouTube Premium.

Para executar o PinoBeats, você precisará ter o Git e o Docker instalados na sua máquina.

1.  Clone o Repositório
    Substitua `seu-usuario` pelo seu nome de usuário no GitHub.

    ```bash
    git clone [https://github.com/seu-usuario/PinoBeats.git](https://github.com/seu-usuario/PinoBeats.git)
    cd PinoBeats
    ```

2.  Configure o Ambiente
    Crie um arquivo chamado `.env` na raiz do projeto. Este arquivo guardará todas as suas chaves de API e segredos.

    Copie o conteúdo abaixo para o seu `.env` e preencha com suas credenciais:

    ```env
    # Token do seu bot Discord
    DISCORD_TOKEN=SEU_TOKEN_DO_DISCORD

    # ID do cliente e segredo do Spotify (opcional, se quiser suporte ao Spotify)
    SPOTIPY_CLIENT_ID=SEU_ID_DO_CLIENTE_SPOTIFY
    SPOTIPY_CLIENT_SECRET=SEU_SEGREDO_DO_CLIENTE_SPOTIFY

    # ID da playlist do YouTube para o comando .ds (opcional)
    DARK_SOULS_PLAYLIST_ID=ID_DA_PLAYLIST_DARK_SOULS_YOUTUBE
    ```

3.  (Opcional) Configurar YouTube Premium
    Para permitir que o bot toque conteúdo exclusivo do YouTube Premium, você pode exportar seus cookies do navegador.

    Use uma extensão como `Get cookies.txt LOCALLY` (Chrome) ou `cookies.txt` (Firefox).

    Navegue até `youtube.com` e exporte os cookies.

    Salve o arquivo baixado como `cookies.txt` na raiz do projeto.

4.  Construa e Execute o Container Docker
    Com o Docker em execução, use os seguintes comandos no seu terminal:

    ```bash
    docker build -t pinobeats .
    docker run -d --name pinobeats -v "$(pwd)/.env:/app/.env:ro" -v "$(pwd)/cookies.txt:/app/cookies.txt:ro" pinobeats
    ```

    Nota: Se você não estiver usando o `cookies.txt`, pode omitir a parte `-v "$(pwd)/cookies.txt:/app/cookies.txt:ro"` do comando run.

    Seu bot agora deve estar online e pronto para receber comandos!

    Para ver os logs do bot:

    ```bash
    docker logs -f pinobeats
    ```

O prefixo padrão do bot é `.`

| Comando e Aliases                | Descrição                                                    | Exemplo de Uso                  |
| -------------------------------- | -------------------------------------------------------------- | ------------------------------- |
| `.play`, `.p`, `.tocar`          | Toca uma música ou playlist do YouTube/Spotify.                | `.p Never Gonna Give You Up`    |
| `.join`, `.entrar`               | Faz o bot entrar no seu canal de voz.                          | `.join`                         |
| `.leave`, `.sair`, `.disconnect` | Faz o bot sair do canal de voz e limpa a fila.                 | `.leave`                        |
| `.pause`, `.pausar`              | Pausa a música que está tocando.                               | `.pause`                        |
| `.resume`, `.continuar`          | Retoma a música que estava pausada.                            | `.resume`                       |
| `.skip`, `.pular`                | Pula para a próxima música da fila.                            | `.skip`                         |
| `.stop`, `.parar`                | Para a música completamente e limpa a fila.                    | `.stop`                         |
| `.queue`, `.q`, `.fila`          | Mostra as próximas 10 músicas na fila.                         | `.queue`                        |
| `.clear`, `.limpar`              | Limpa todas as músicas da fila.                                | `.clear`                        |
| `.shuffle`, `.misturar`          | Embaralha a ordem das músicas na fila.                         | `.shuffle`                      |
| `.ds`                            | Toca a playlist temática de Dark Souls (definida no `.env`).   | `.ds`                           |