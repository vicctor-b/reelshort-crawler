"""Baixa todos os episodios de uma serie do ReelShort e monta o video final com ffmpeg.

Fluxo:
 1. Busca a pagina da serie e extrai os links /pt/episodes/episode-N-... do HTML
    (nao precisa mais de Selenium: os links vem no HTML renderizado no servidor).
 2. Para cada episodio, busca a pagina e extrai o link .m3u8 do JSON-LD
    (<script type="application/ld+json">, campo @graph[0].contentUrl).
 3. Baixa cada .m3u8 para .mp4 com ffmpeg (-c copy), em paralelo.
 4. Concatena tudo em um unico .mp4 com o demuxer concat do ffmpeg.

Uso:
    python reelshort_downloader.py [url_da_serie]
"""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

SERIES_URL = "https://www.reelshort.com/pt/movie/como-chutar-um-craque-da-bola-69d86163964a80d1480645cf"
BASE_URL = "https://www.reelshort.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TEMP_DIR = "temp_videos"
MAX_WORKERS = 6


def get_episode_urls(series_url):
    resp = requests.get(series_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    links = re.findall(r'/pt/episodes/episode-\d+[^"\'\s>]*', resp.text)
    uniq = sorted(set(links), key=lambda x: int(re.search(r"episode-(\d+)", x).group(1)))
    return [BASE_URL + link for link in uniq]


def get_m3u8_url(episode_url):
    resp = requests.get(episode_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.S)
    if not match:
        raise ValueError(f"JSON-LD nao encontrado em {episode_url}")
    data = json.loads(match.group(1))
    content_url = data["@graph"][0].get("contentUrl")
    if not content_url:
        raise ValueError(f"contentUrl ausente em {episode_url}")
    return content_url


def download_episode(m3u8_url, index):
    output_file = os.path.join(TEMP_DIR, f"ep_{index:03d}.mp4")
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        print(f"[ep {index}] ja baixado, pulando")
        return output_file
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", m3u8_url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        output_file,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou no ep {index}: {result.stderr.strip()}")
    print(f"[ep {index}] baixado -> {output_file}")
    return output_file


def concat_episodes(files, output_final):
    concat_list = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in files:
            f.write(f"file '{os.path.basename(path)}'\n")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        output_final,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou na concatenacao: {result.stderr.strip()}")
    print(f"Video final criado: {output_final}")


def main():
    series_url = sys.argv[1] if len(sys.argv) > 1 else SERIES_URL
    os.makedirs(TEMP_DIR, exist_ok=True)

    print(f"Buscando episodios de {series_url}")
    episode_urls = get_episode_urls(series_url)
    print(f"{len(episode_urls)} episodios encontrados")

    print("Extraindo links .m3u8...")
    m3u8_urls = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        m3u8_urls = list(executor.map(get_m3u8_url, episode_urls))
    print(f"{len(m3u8_urls)} links .m3u8 extraidos")

    print("Baixando episodios com ffmpeg...")
    files = {}
    errors = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_episode, url, i): i
            for i, url in enumerate(m3u8_urls, start=1)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                files[index] = future.result()
            except Exception as exc:
                errors.append((index, exc))
                print(f"[ep {index}] ERRO: {exc}")

    if errors:
        print(f"{len(errors)} episodios falharam; corrija e rode de novo (os ja baixados sao reaproveitados).")
        sys.exit(1)

    ordered_files = [files[i] for i in sorted(files)]
    slug = re.search(r"/movie/([a-z0-9-]+?)-[0-9a-f]{24}", series_url)
    output_final = (slug.group(1) if slug else "serie") + ".mp4"
    concat_episodes(ordered_files, output_final)

    for path in ordered_files:
        os.remove(path)
    os.remove(os.path.join(TEMP_DIR, "concat_list.txt"))
    os.rmdir(TEMP_DIR)
    print("Arquivos temporarios removidos.")


if __name__ == "__main__":
    main()
