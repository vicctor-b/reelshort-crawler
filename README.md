# reelshort-crawler

Script de estudo que baixa todos os episódios de uma série do ReelShort e monta um único vídeo final com ffmpeg.

## Como funciona

1. Busca a página da série e extrai os links dos episódios (`/pt/episodes/episode-N-...`) direto do HTML renderizado no servidor — não precisa de Selenium.
2. Para cada episódio, busca a página e extrai o link `.m3u8` do JSON-LD (`<script type="application/ld+json">`, campo `@graph[0].contentUrl`).
3. Baixa cada `.m3u8` para `.mp4` com ffmpeg (`-c copy`), em paralelo (6 downloads simultâneos).
4. Concatena tudo em um único `.mp4` com o demuxer concat do ffmpeg, nomeado a partir do slug da série.

O trailer não aparece na lista de episódios (só na página da série), então todos os itens da lista são baixados.

## Requisitos

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) no PATH
- `pip install requests`

## Uso

```bash
python reelshort_downloader.py <url_da_serie>
```

Exemplo:

```bash
python reelshort_downloader.py https://www.reelshort.com/pt/movie/como-chutar-um-craque-da-bola-69d86163964a80d1480645cf
```

Sem argumento, usa a URL definida em `SERIES_URL` no script.

Os episódios baixam para `temp_videos/` e, ao final, são concatenados e os temporários removidos. Se algum download falhar, basta rodar de novo: os episódios já baixados são reaproveitados.
