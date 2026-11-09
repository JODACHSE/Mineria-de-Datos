"""R6 · Extrae comentarios de YouTube con la API YouTube Data v3.

Uso (desde la raíz del repo):  python scripts/R6/extraer_comentarios_youtube.py
Requiere: requests, python-dotenv y la clave en .env  ->  YOUTUBE_API_KEY=...

Criterios de búsqueda y límites: scripts/R6/youtube_config.json
Salida en orange/data/youtube/:
  videos.csv              video, enlace, canal, fecha de publicación, vistas, comentarios, consulta de origen
  comentarios_crudos.csv  texto, me gusta, respuestas y fecha (SIN autor ni identificadores de la persona)
  log_extraccion.json     fecha, parámetros, cuota estimada, restricciones encontradas

Privacidad: no se guarda nombre, canal, foto ni id del autor. La clave nunca se imprime ni se escribe:
los mensajes de error se limpian antes de mostrarse.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("youtube_config.json")
OUT = ROOT / "orange" / "data" / "youtube"
API = "https://www.googleapis.com/youtube/v3"
COSTO = {"search": 100, "videos": 1, "commentThreads": 1}   # unidades de cuota por llamada
CUOTA_DIARIA = 10_000
MOTIVOS_CUOTA = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}


class ErrorAPI(Exception):
    def __init__(self, status: int, motivo: str, mensaje: str):
        super().__init__(f"HTTP {status} · {motivo} · {mensaje}")
        self.status, self.motivo = status, motivo


class CuotaAgotada(Exception):
    pass


class Cliente:
    def __init__(self, clave: str, sesion: requests.Session | None = None, pausa: float = 0.2):
        self._clave = clave
        self._s = sesion or requests.Session()
        self._pausa = pausa
        self.cuota = 0

    def _limpio(self, texto: str) -> str:
        return texto.replace(self._clave, "***")

    def get(self, recurso: str, **params) -> dict:
        params["key"] = self._clave
        for intento in range(4):
            try:
                r = self._s.get(f"{API}/{recurso}", params=params, timeout=30)
            except requests.RequestException as e:
                if intento == 3:
                    raise RuntimeError(f"Sin conexión con la API: {self._limpio(str(e))}") from None
                time.sleep(2 ** intento)
                continue
            if r.status_code >= 500:
                if intento == 3:
                    raise ErrorAPI(r.status_code, "serverError", "El servicio no respondió")
                time.sleep(2 ** intento)
                continue
            self.cuota += COSTO[recurso]
            time.sleep(self._pausa)
            if r.status_code == 200:
                return r.json()
            try:
                err = r.json()["error"]
                motivo = (err.get("errors") or [{}])[0].get("reason", "desconocido")
                mensaje = self._limpio(err.get("message", ""))
            except Exception:
                motivo, mensaje = "desconocido", self._limpio(r.text[:200])
            if motivo in MOTIVOS_CUOTA:
                raise CuotaAgotada(mensaje)
            raise ErrorAPI(r.status_code, motivo, mensaje)
        raise RuntimeError("inalcanzable")


def extraer_id(valor: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", valor)
    if m:
        return m.group(1)
    return valor if re.fullmatch(r"[\w-]{11}", valor) else None


def buscar_videos(cli: Cliente, cfg: dict, log: dict) -> dict[str, str]:
    """video_id -> consulta de origen ('manual' para los dados a mano)."""
    candidatos: dict[str, str] = {}
    for v in cfg.get("videos_manuales", []):
        vid = extraer_id(v)
        if vid:
            candidatos[vid] = "manual"
        else:
            log["restricciones"].append(f"Enlace manual no reconocido: {v}")
    desde = cfg.get("publicados_desde")
    for q in cfg.get("consultas", []):
        params = dict(part="snippet", type="video", q=q, maxResults=cfg.get("max_videos_por_consulta", 5),
                      regionCode=cfg.get("region", "CO"), relevanceLanguage=cfg.get("idioma", "es"),
                      order="relevance", safeSearch="moderate")
        if desde:
            params["publishedAfter"] = f"{desde}T00:00:00Z"
        try:
            items = cli.get("search", **params).get("items", [])
        except ErrorAPI as e:
            log["restricciones"].append(f"Búsqueda '{q}' falló: {e}")
            continue
        except CuotaAgotada as e:
            log["restricciones"].append(f"Cuota agotada en la búsqueda '{q}' ({e}); se siguen con los videos ya encontrados")
            break
        nuevos = 0
        for it in items:
            vid = it["id"]["videoId"]
            if vid not in candidatos:
                candidatos[vid] = q
                nuevos += 1
        log["consultas"].append({"consulta": q, "resultados": len(items), "videos_nuevos": nuevos})
    return candidatos


def metadatos(cli: Cliente, ids: list[str], log: dict) -> dict[str, dict]:
    datos: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        lote = ids[i:i + 50]
        for it in cli.get("videos", part="snippet,statistics", id=",".join(lote)).get("items", []):
            st, sn = it.get("statistics", {}), it["snippet"]
            datos[it["id"]] = {
                "titulo": sn.get("title", ""), "canal": sn.get("channelTitle", ""),
                "fecha_publicacion": sn.get("publishedAt", "")[:10],
                "vistas": int(st.get("viewCount", 0)),
                # sin 'commentCount' = comentarios desactivados
                "comentarios_api": int(st["commentCount"]) if "commentCount" in st else None,
            }
        for vid in set(lote) - set(datos):
            log["restricciones"].append(f"Video {vid}: no disponible (privado, eliminado o restringido)")
    return datos


def comentarios_de(cli: Cliente, vid: str, maximo: int, orden: str) -> list[dict]:
    filas, token = [], None
    while len(filas) < maximo:
        params = dict(part="snippet", videoId=vid, maxResults=min(100, maximo - len(filas)),
                      order=orden, textFormat="plainText")
        if token:
            params["pageToken"] = token
        data = cli.get("commentThreads", **params)
        for it in data.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            filas.append({"texto": sn.get("textDisplay", ""), "me_gusta": sn.get("likeCount", 0),
                          "respuestas": it["snippet"].get("totalReplyCount", 0),
                          "fecha": sn.get("publishedAt", "")[:10]})
        token = data.get("nextPageToken")
        if not token:
            break
    return filas


def main() -> None:
    load_dotenv(ROOT / ".env")
    clave = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not clave:
        sys.exit("Falta YOUTUBE_API_KEY en el archivo .env (ver .env.example).")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cli = Cliente(clave)
    ahora = datetime.now(timezone.utc)
    log: dict = {"fecha_extraccion_utc": ahora.isoformat(timespec="seconds"), "proposito": cfg.get("proposito"),
                 "parametros": {k: v for k, v in cfg.items() if k != "proposito"},
                 "consultas": [], "restricciones": []}
    videos: list[dict] = []
    filas: list[dict] = []
    try:
        candidatos = buscar_videos(cli, cfg, log)
        meta = metadatos(cli, list(candidatos), log)
        minimo = cfg.get("min_comentarios_video", 0)
        for vid, info in meta.items():
            if info["comentarios_api"] is None:
                log["restricciones"].append(f"Video {vid}: comentarios desactivados")
                continue
            if info["comentarios_api"] < minimo:
                log["restricciones"].append(f"Video {vid}: {info['comentarios_api']} comentarios (< {minimo}), descartado")
                continue
            try:
                cs = comentarios_de(cli, vid, cfg.get("max_comentarios_por_video", 500),
                                    cfg.get("orden_comentarios", "relevance"))
            except ErrorAPI as e:
                log["restricciones"].append(f"Video {vid}: {e}")
                continue
            videos.append({"video_id": vid, "enlace": f"https://www.youtube.com/watch?v={vid}", **info,
                           "comentarios_extraidos": len(cs), "consulta_origen": candidatos[vid],
                           "fecha_extraccion": ahora.date().isoformat()})
            filas += [{"video_id": vid, **c} for c in cs]
            print(f"  {vid}: {len(cs):4d} comentarios | {info['titulo'][:60]}")
    except CuotaAgotada as e:
        log["restricciones"].append(f"Cuota diaria agotada; la extracción quedó incompleta ({e})")
        print("Cuota agotada: se guardará lo obtenido hasta aquí.")

    OUT.mkdir(parents=True, exist_ok=True)
    campos_v = ["video_id", "enlace", "titulo", "canal", "fecha_publicacion", "vistas", "comentarios_api",
                "comentarios_extraidos", "consulta_origen", "fecha_extraccion"]
    with (OUT / "videos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos_v)
        w.writeheader()
        w.writerows(videos)
    with (OUT / "comentarios_crudos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "video_id", "texto", "me_gusta", "respuestas", "fecha"])
        w.writeheader()
        for n, fila in enumerate(filas, 1):
            w.writerow({"id": f"c{n:05d}", **fila})
    log.update(videos_consultados=len(videos), comentarios_obtenidos=len(filas),
               cuota_estimada_unidades=cli.cuota, cuota_diaria=CUOTA_DIARIA)
    (OUT / "log_extraccion.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(videos)} videos, {len(filas)} comentarios, ~{cli.cuota} unidades de cuota. "
          f"Restricciones registradas: {len(log['restricciones'])}. Salida: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
