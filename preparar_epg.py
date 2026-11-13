#!/usr/bin/env python3
import gzip
from pathlib import Path
import requests

URLS = [
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml",
    "https://www.tdtchannels.com/epg/TV.xml.gz",
    "https://www.ondachannels.com/epg/RADIO.xml.gz",
]
DESTINO = Path("datos/epg")
DESTINO.mkdir(parents=True, exist_ok=True)
s = requests.Session()
s.headers.update({"User-Agent": "ACE-AUTO/2.0"})

for i, url in enumerate(URLS, 1):
    destino = DESTINO / f"epg-{i}.xml"
    try:
        print(f"Descargando EPG {i}: {url}")
        r = s.get(url, timeout=180)
        r.raise_for_status()
        contenido = r.content
        if contenido[:2] == b"\x1f\x8b":
            contenido = gzip.decompress(contenido)
        # Validación mínima para no sustituir una guía válida por HTML/error.
        inicio = contenido.lstrip()[:300].lower()
        if b"<tv" not in inicio and b"<?xml" not in inicio:
            raise ValueError("La respuesta no parece XMLTV válido.")
        destino.write_bytes(contenido)
        print(f"Guardada {destino} ({len(contenido)} bytes)")
    except Exception as e:
        # No borrar una copia anterior si la fuente falla.
        print(f"AVISO: no se pudo actualizar EPG {i}: {e}")
        if not destino.exists():
            destino.write_text("", encoding="utf-8")
