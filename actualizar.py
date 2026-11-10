import os
import re
import json
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests

# ==========================================================
# CONFIGURACION ACE-AUTO
# ==========================================================

FUENTE_ELCANO = (
    "https://tokyo2.elcano-ipfs.workers.dev/"
    "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs/"
    "hashes_acestream.m3u"
)

API_GIT_GAY = "https://git.gay/api/v1"
REPO_GIT_GAY = "iptvpro2026/lista"
RAMA_GIT_GAY = "main"
ARCHIVO_DESTINO = "hashes.m3u"

ARCHIVO_AUTO = Path("canales.m3u")
ARCHIVO_MANUAL = Path("canales_manuales.m3u")
ARCHIVO_HISTORIAL = Path("historial.json")
ARCHIVO_CAMBIOS = Path("cambios.md")

GRUPO_AUTO = "⭐ ELCANO [MÁXIMA CALIDAD]"
URL_ACE_LOCAL = "http://127.0.0.1:6878/ace/getstream?id="

# EPG tomada de la configuración de la lista que compartiste.
EPG_URLS = [
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml",
]

CABECERA = (
    '#EXTM3U url-tvg="' + ",".join(EPG_URLS) + '" refresh="3600"'
)

CABECERA_FINAL = [
    CABECERA,
    "#EXTVLCOPT:network-caching=1000",
    (
        '#EXTGRP: group-title="' + GRUPO_AUTO +
        '" group-logo="https://raw.githubusercontent.com/'
        'davidmuma/picons_dobleM/master/icon/M%2B%20LaLiga.png"'
    ),
]

SESION = requests.Session()
SESION.headers.update({"User-Agent": "ACE-AUTO/1.0"})


# ==========================================================
# DESCARGA Y VALIDACION
# ==========================================================

def descargar_fuente():
    print("Descargando lista automatica de Elcano...")
    r = SESION.get(FUENTE_ELCANO, timeout=120)
    r.raise_for_status()
    texto = r.content.decode("utf-8-sig", errors="replace").strip()

    if not texto.startswith("#EXTM3U"):
        raise RuntimeError("La fuente descargada no parece una lista M3U.")

    if "#EXTINF" not in texto:
        raise RuntimeError("La lista de Elcano no contiene canales. No se publicara una lista vacia.")

    return texto


# ==========================================================
# PROCESAMIENTO M3U
# ==========================================================

def extraer_id_acestream(url):
    url = url.strip()

    if url.lower().startswith("acestream://"):
        return url.split("://", 1)[1].strip()

    if "/ace/getstream?id=" in url:
        return url.split("/ace/getstream?id=", 1)[1].split("&", 1)[0].strip()

    # Algunos M3U pueden traer el identificador como URL de acestream
    m = re.search(r"(?:infohash=|id=)([A-Fa-f0-9]{20,})", url)
    return m.group(1) if m else ""


def convertir_url(url):
    url = url.strip()
    identificador = extraer_id_acestream(url)

    if identificador:
        return URL_ACE_LOCAL + identificador

    return url


def separar_registros(texto):
    """Devuelve cabecera/globales y registros #EXTINF completos."""
    lineas = [x.rstrip("\r") for x in texto.replace("\ufeff", "").splitlines()]
    registros = []
    actual = None

    for linea in lineas:
        if linea.startswith("#EXTINF:"):
            if actual:
                registros.append(actual)
            actual = [linea]
        elif actual is not None:
            if linea.strip():
                actual.append(linea.strip())

    if actual:
        registros.append(actual)

    return registros


def nombre_canal(registro):
    extinf = registro[0]
    if "," in extinf:
        return extinf.split(",", 1)[1].strip()
    return "Canal sin nombre"


def atributo(extinf, nombre):
    m = re.search(r'\b' + re.escape(nombre) + r'="([^"]*)"', extinf, re.I)
    return m.group(1).strip() if m else ""


def clave_canal(registro):
    extinf = registro[0]
    tvg = atributo(extinf, "tvg-id")
    if tvg:
        return tvg.casefold()

    nombre = nombre_canal(registro)
    nombre = re.sub(r"\b(2160p|1080p|720p|4k|uhd|fhd|hd)\b", "", nombre, flags=re.I)
    nombre = re.sub(r"[\*\s\-_]+$", "", nombre).strip()
    return nombre.casefold()


def rango_calidad(registro):
    texto = " ".join(registro).lower()

    if re.search(r"\b(4k|2160p|uhd)\b", texto):
        return 4
    if re.search(r"\b(1080p|fhd|full hd)\b", texto):
        return 3
    if re.search(r"\b(720p|hd)\b", texto):
        return 2
    if re.search(r"\b(576p|sd)\b", texto):
        return 1
    return 0


def preparar_registro(registro, automatico=False):
    salida = list(registro)
    extinf = salida[0]

    if automatico:
        # Todos los canales automáticos quedan en la carpeta/grupo Elcano.
        if "group-title=" in extinf:
            extinf = re.sub(
                r'group-title="[^"]*"',
                'group-title="' + GRUPO_AUTO + '"',
                extinf,
                count=1,
                flags=re.I
            )
        else:
            extinf = extinf.replace(",", ' group-title="' + GRUPO_AUTO + '",', 1)
        salida[0] = extinf

    for i in range(1, len(salida)):
        if not salida[i].startswith("#"):
            salida[i] = convertir_url(salida[i])

    return salida


def seleccionar_maxima_calidad(registros):
    """
    Por cada canal conserva solo la calidad más alta encontrada.
    Si hay varias fuentes con esa misma calidad, conserva todas como alternativas.
    """
    grupos = {}

    for registro in registros:
        preparado = preparar_registro(registro, automatico=True)
        key = clave_canal(preparado)
        rank = rango_calidad(preparado)

        if key not in grupos or rank > grupos[key]["rank"]:
            grupos[key] = {"rank": rank, "registros": [preparado]}
        elif rank == grupos[key]["rank"]:
            grupos[key]["registros"].append(preparado)

    resultado = []
    for item in grupos.values():
        resultado.extend(item["registros"])

    # Ordena por nombre para que la carpeta sea estable entre actualizaciones.
    resultado.sort(key=lambda r: nombre_canal(r).casefold())
    return resultado


def leer_manual():
    if not ARCHIVO_MANUAL.exists():
        ARCHIVO_MANUAL.write_text("#EXTM3U\n", encoding="utf-8")
        print("Creado canales_manuales.m3u. Puedes añadir ahi tus canales propios.")

    texto = ARCHIVO_MANUAL.read_text(encoding="utf-8-sig", errors="replace")
    if not texto.strip():
        return []

    return [
        preparar_registro(r, automatico=False)
        for r in separar_registros(texto)
    ]


def serializar_registros(registros):
    lineas = []
    for registro in registros:
        lineas.extend(registro)
    return "\n".join(lineas)


# ==========================================================
# HISTORIAL DE CAMBIOS
# ==========================================================

def firma(registro):
    contenido = "\n".join(registro).strip()
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def mapa_registros(registros):
    resultado = {}
    repetidos = {}

    for registro in registros:
        base = clave_canal(registro)
        repetidos[base] = repetidos.get(base, 0) + 1
        key = f"{base}##{repetidos[base]}"
        resultado[key] = {
            "nombre": nombre_canal(registro),
            "hash": firma(registro)
        }

    return resultado


def cargar_historial():
    if not ARCHIVO_HISTORIAL.exists():
        return None
    try:
        return json.loads(ARCHIVO_HISTORIAL.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"historial.json no se puede leer; se detiene para no perder el historial: {e}")


def registrar_cambios(registros):
    anterior = cargar_historial()
    actual = mapa_registros(registros)
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if anterior is None:
        ARCHIVO_HISTORIAL.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        if not ARCHIVO_CAMBIOS.exists():
            ARCHIVO_CAMBIOS.write_text(
                "# Historial ACE-AUTO\n\n"
                f"## {ahora}\nPrimera sincronización: se guardó la lista de referencia "
                f"con {len(actual)} entradas. Los cambios se detallarán desde la próxima ejecución.\n\n",
                encoding="utf-8"
            )
        print("Primera sincronizacion: guardada como referencia.")
        return

    nuevos = [k for k in actual if k not in anterior]
    eliminados = [k for k in anterior if k not in actual]
    modificados = [
        k for k in actual
        if k in anterior and actual[k]["hash"] != anterior[k].get("hash")
    ]

    informe = [f"## {ahora}", ""]
    informe.append(f"- Canales añadidos: {len(nuevos)}")
    informe.append(f"- Canales eliminados: {len(eliminados)}")
    informe.append(f"- Canales modificados: {len(modificados)}")

    for titulo, claves in (
        ("Añadidos", nuevos),
        ("Eliminados", eliminados),
        ("Modificados", modificados),
    ):
        if claves:
            informe.extend(["", f"### {titulo}"])
            for k in claves:
                nombre = actual[k]["nombre"] if k in actual else anterior[k]["nombre"]
                informe.append(f"- {nombre}")

    informe.append("")
    previo = ARCHIVO_CAMBIOS.read_text(encoding="utf-8") if ARCHIVO_CAMBIOS.exists() else "# Historial ACE-AUTO\n\n"
    ARCHIVO_CAMBIOS.write_text(previo + "\n".join(informe) + "\n", encoding="utf-8")
    ARCHIVO_HISTORIAL.write_text(
        json.dumps(actual, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Cambios: +{len(nuevos)} / -{len(eliminados)} / modificados {len(modificados)}")


# ==========================================================
# PUBLICAR EN GIT.GAY (GITEA)
# ==========================================================

def publicar_git_gay(contenido):
    token = os.environ.get("GIT_GAY_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta el secreto GIT_GAY_TOKEN en GitHub Actions.")

    url = f"{API_GIT_GAY}/repos/{REPO_GIT_GAY}/contents/{ARCHIVO_DESTINO}"
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}

    existente = SESION.get(
        url,
        headers=headers,
        params={"ref": RAMA_GIT_GAY},
        timeout=40
    )

    payload = {
        "message": "Actualizar lista ACE-AUTO Elcano y canales manuales",
        "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
        "branch": RAMA_GIT_GAY,
    }

    if existente.status_code == 200:
        datos = existente.json()
        if datos.get("sha"):
            payload["sha"] = datos["sha"]
    elif existente.status_code != 404:
        raise RuntimeError(
            f"No se pudo consultar hashes.m3u en git.gay: "
            f"HTTP {existente.status_code} - {existente.text[:500]}"
        )

    respuesta = SESION.put(url, headers=headers, json=payload, timeout=90)

    if respuesta.status_code not in (200, 201):
        raise RuntimeError(
            f"Error publicando en git.gay: HTTP {respuesta.status_code} - "
            f"{respuesta.text[:1000]}"
        )

    print("Lista publicada correctamente en git.gay.")


# ==========================================================
# PROCESO PRINCIPAL
# ==========================================================

def main():
    print("=" * 55)
    print("ACTUALIZANDO ACE-AUTO")
    print("=" * 55)

    fuente = descargar_fuente()
    registros_fuente = separar_registros(fuente)

    if not registros_fuente:
        raise RuntimeError("Elcano no devolvió canales validos.")

    automaticos = seleccionar_maxima_calidad(registros_fuente)
    if not automaticos:
        raise RuntimeError("No quedaron canales automáticos tras el filtrado.")

    # canales.m3u es SOLO la parte automática y se regenera en cada ejecución.
    texto_auto = CABECERA + "\n" + serializar_registros(automaticos) + "\n"
    ARCHIVO_AUTO.write_text(texto_auto, encoding="utf-8")

    manuales = leer_manual()

    # El archivo final mezcla automáticos + manuales sin sobrescribir el archivo manual.
    todos = automaticos + manuales
    final = "\n".join(CABECERA_FINAL) + "\n" + serializar_registros(todos) + "\n"

    registrar_cambios(automaticos)
    publicar_git_gay(final)

    print(f"Canales automáticos (máxima calidad): {len(automaticos)}")
    print(f"Canales manuales conservados: {len(manuales)}")
    print(f"Total publicado: {len(todos)}")
    print("=" * 55)


if __name__ == "__main__":
    main()
