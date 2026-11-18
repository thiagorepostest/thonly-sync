import json
import os
import re
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".")

HEADERS = {
    "User-Agent": "ThonlySyncStudio/10.0 (https://github.com/thonly-studio)"
}


def http_get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def lrc_to_srt(lrc_text: str, duration_sec: float = 0.0) -> list[dict]:
    """Converte formato LRC oficial ([mm:ss.xx] verso) em lista de cues SRT."""
    pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
    raw_items = []
    for line in lrc_text.splitlines():
        matches = list(pattern.finditer(line))
        if not matches:
            continue
        text = pattern.sub("", line).strip()
        if not text:
            continue
        for m in matches:
            mins = int(m.group(1))
            secs = int(m.group(2))
            frac = m.group(3) or "0"
            ms = int(frac.ljust(3, "0")[:3])
            t = mins * 60 + secs + ms / 1000.0
            raw_items.append((t, text))

    raw_items.sort(key=lambda x: x[0])
    cues = []
    for i, (start_t, text) in enumerate(raw_items):
        if i + 1 < len(raw_items):
            end_t = max(start_t + 0.4, raw_items[i + 1][0] - 0.05)
        else:
            end_t = max(start_t + 3.0, duration_sec if duration_sec > start_t else start_t + 3.5)
        cues.append({
            "start": round(start_t, 3),
            "end": round(end_t, 3),
            "text": text,
        })
    return cues


def clean_song_title(raw_title: str) -> str:
    """Remove sufixos comuns de YouTube/Spotify como (Official Video), [Clipe Oficial], etc."""
    cleaned = re.sub(
        r"[\(\[\{].*?(official|clipe|video|audio|lyric|visualizer|hd|4k|prod\.|ao vivo).*?[\)\]\}]",
        "",
        raw_title,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*\|\s*.*$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def resolve_link_metadata(query_or_url: str) -> dict:
    """Extrai artista e música a partir de links do Spotify, YouTube, Musixmatch ou texto livre."""
    q = query_or_url.strip()
    meta = {"source": "busca", "query": q, "track": q, "artist": ""}

    if "open.spotify.com" in q:
        meta["source"] = "Spotify"
        try:
            oembed = http_get_json(f"https://open.spotify.com/oembed?url={urllib.parse.quote(q, safe='')}")
            title = oembed.get("title", "")
            # Spotify oEmbed costuma retornar "Nome da Música" ou "Música - song and lyrics by Artista"
            if " - " in title:
                parts = title.split(" - ", 1)
                meta["track"] = parts[0].strip()
                meta["artist"] = re.sub(r"song and lyrics by\s*", "", parts[1], flags=re.IGNORECASE).strip()
            else:
                meta["track"] = title.strip()
            meta["query"] = f"{meta['track']} {meta['artist']}".strip()
        except Exception:
            pass
        return meta

    if "youtube.com" in q or "youtu.be" in q:
        meta["source"] = "YouTube"
        try:
            oembed = http_get_json(f"https://www.youtube.com/oembed?url={urllib.parse.quote(q, safe='')}&format=json")
            raw_title = oembed.get("title", "")
            author = oembed.get("author_name", "")
            cleaned = clean_song_title(raw_title)
            if " - " in cleaned:
                left, right = cleaned.split(" - ", 1)
                meta["artist"] = left.strip()
                meta["track"] = right.strip()
            else:
                meta["track"] = cleaned
                meta["artist"] = re.sub(r"\s*-\s*Topic$", "", author, flags=re.IGNORECASE).strip()
            meta["query"] = f"{meta['artist']} {meta['track']}".strip()
        except Exception:
            pass
        return meta

    if "musixmatch.com" in q:
        meta["source"] = "Musixmatch"
        try:
            parsed = urllib.parse.urlparse(q)
            parts = [p for p in parsed.path.split("/") if p]
            # Ex: /lyrics/Artist-Name/Track-Name
            if "lyrics" in parts:
                idx = parts.index("lyrics")
                if idx + 2 < len(parts):
                    meta["artist"] = urllib.parse.unquote(parts[idx + 1]).replace("-", " ")
                    meta["track"] = urllib.parse.unquote(parts[idx + 2]).replace("-", " ")
                    meta["query"] = f"{meta['artist']} {meta['track']}".strip()
        except Exception:
            pass
        return meta

    # Texto livre ("Artista - Música" ou "Música Artista")
    if " - " in q:
        left, right = q.split(" - ", 1)
        meta["artist"] = left.strip()
        meta["track"] = right.strip()
    return meta


def search_lrclib(query: str, track: str = "", artist: str = "") -> list[dict]:
    results = []
    seen_ids = set()

    urls = [f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"]
    if track and artist:
        urls.insert(0, f"https://lrclib.net/api/search?track_name={urllib.parse.quote(track)}&artist_name={urllib.parse.quote(artist)}")

    for u in urls:
        try:
            data = http_get_json(u)
            if isinstance(data, list):
                for item in data:
                    item_id = item.get("id")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    synced = item.get("syncedLyrics") or ""
                    plain = item.get("plainLyrics") or ""
                    if not synced and not plain:
                        continue
                    duration = float(item.get("duration") or 0)
                    cues = lrc_to_srt(synced, duration) if synced else []
                    results.append({
                        "id": item_id,
                        "trackName": item.get("trackName", ""),
                        "artistName": item.get("artistName", ""),
                        "albumName": item.get("albumName", ""),
                        "duration": duration,
                        "hasSynced": bool(cues),
                        "cues": cues,
                        "plainLyrics": plain,
                    })
        except Exception:
            continue

    # Prioriza resultados com legenda sincronizada oficial
    results.sort(key=lambda r: (0 if r["hasSynced"] else 1))
    return results[:12]


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "v11"})


@app.route("/api/resolve-lyrics", methods=["POST"])
def resolve_lyrics():
    try:
        body = request.get_json(silent=True) or {}
        raw_input = (body.get("input") or "").strip()
        if not raw_input:
            return jsonify({"error": "Cole um link do Spotify, YouTube, Musixmatch ou digite o nome da música."}), 400

        meta = resolve_link_metadata(raw_input)
        results = search_lrclib(meta["query"], meta.get("track", ""), meta.get("artist", ""))
        return jsonify({"meta": meta, "results": results})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"Thonly Sync Studio v11 rodando em http://localhost:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
