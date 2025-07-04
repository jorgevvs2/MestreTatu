# Mestre Tatu 🎲

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/discord.py-2.3.2-blue?style=for-the-badge&logo=discord&logoColor=white" alt="discord.py Version">
  <img src="https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker" alt="Docker Ready">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

**Mestre Tatu** é um assistente completo de RPG para Discord, projetado para enriquecer e agilizar suas campanhas. O que começou como um simples bot de música evoluiu para uma ferramenta poderosa para Mestres e jogadores, combinando utilidades de jogo, um sistema de estatísticas robusto e um gerador de conteúdo com IA.

Construído com `discord.py` e `google-generativeai`, e totalmente containerizado com Docker para uma implantação simples e consistente.

## ✨ Funcionalidades Principais

### 🎲 Ferramentas de RPG e Mestre (IA)
-   **Mestre de Regras**: Tire dúvidas sobre regras de D&D 5e a qualquer momento com o comando `.rpg`. O bot busca em PDFs locais e usa IA para dar respostas precisas.
-   **Gerador de NPCs**: Crie NPCs complexos e memoráveis instantaneamente com o comando `.npc`. A IA gera nome, aparência, personalidade e um gancho de aventura.
-   **Rolador de Dados**: Um sistema completo de rolagem de dados (`.d20`, `.3d6+5`, etc.) com suporte a expressões matemáticas complexas.
-   **Controle de Iniciativa**: Gerencie a ordem de combate de forma fácil e visual com um painel interativo usando `.init`.

### 📊 Gerenciamento de Campanha
-   **Registro de Estatísticas**: Grave todos os eventos importantes da sessão — dano, cura, abates, quedas e rolagens críticas — com o comando `.log`.
-   **Visualização de Dados**: Consulte as estatísticas de um jogador (`.stats`), de uma sessão específica (`.sessionstats`) ou veja o "Hall da Fama" da campanha com os recordistas de cada categoria (`.mvp`).

### 🎶 Música e Ambiência
-   **Suporte a Múltiplas Fontes**: Toca músicas e playlists do YouTube, YouTube Music e Spotify.
-   **Controles Completos**: Comandos para tocar, pausar, pular, parar, gerenciar a fila e muito mais.
-   **Qualidade de Áudio**: Utiliza `yt-dlp` e `FFmpeg` para streaming de áudio de alta qualidade.

## 🛠️ Tecnologias Utilizadas

-   **Backend:** Python
-   **API Discord:** `discord.py`
-   **IA Generativa:** `google-generativeai`
-   **Streaming de Áudio:** `yt-dlp`, `FFmpeg`
-   **Containerização:** `Docker`
-   **Gerenciamento de Dependências:** `pip`

## 📜 Comandos

O prefixo padrão do bot é `.`

### Comandos de RPG

| Comando e Aliases       | Descrição                                                          | Exemplo de Uso                          |
| ----------------------- | -------------------------------------------------------------------- | --------------------------------------- |
| `.rpg`                  | Tira uma dúvida de D&D, consultando a IA e os livros locais.         | `.rpg como funciona a ação agarrar`     |
| `.npc`                  | Gera um NPC completo com base em uma descrição.                      | `.npc um taverneiro anão rabugento`     |
| `.d`, `.roll`           | Rola dados. Suporta expressões complexas.                          | `.d20+5` ou `.3d8 - 2`                  |
| `.init`                 | Abre o painel interativo para gerenciar a iniciativa do combate.     | `.init`                                 |

### Comandos de Estatísticas

| Comando e Aliases         | Descrição                                                            | Exemplo de Uso     |
| ------------------------- | -------------------------------------------------------------------- | ------------------ |
| `.log`                    | Abre um menu para registrar eventos da sessão (dano, cura, etc.).    | `.log`             |
| `.stats`, `.estatisticas` | Mostra as estatísticas totais de um jogador específico.              | `.stats @Jogador`  |
| `.sessionstats`, `.sessao`| Mostra um resumo das estatísticas de uma sessão específica.          | `.sessionstats 5`  |
| `.mvp`, `.destaques`      | Mostra o "Hall da Fama" com os recordistas de cada categoria.        | `.mvp`             |
| `.setsession`             | (Mestre) Define o número da sessão atual para o registro de logs.    | `.setsession 7`    |

## 🤝 Contribuições

Contribuições são sempre bem-vindas! Se você tem ideias para novas funcionalidades, melhorias ou encontrou algum bug, sinta-se à vontade para abrir uma *Issue* ou enviar um *Pull Request*.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.