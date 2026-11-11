import os
import re
import json
import base64
import hashlib
import unicodedata
from collections import Counter
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

EPG_URLS = [
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml",
]

CABECERA = (
    '#EXTM3U url-tvg="' + ",".join(EPG_URLS) +
    '" refresh="3600"'
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
SESION.headers.update({
    "User-Agent": "ACE-AUTO/2.0"
})


# ==========================================================
# DESCARGAR FUENTE
# ==========================================================

def descargar_fuente():

    print("Descargando lista original de Elcano...")

    respuesta = SESION.get(
        FUENTE_ELCANO,
        timeout=120
    )

    respuesta.raise_for_status()

    texto = respuesta.content.decode(
        "utf-8-sig",
        errors="replace"
    ).strip()

    if not texto.startswith("#EXTM3U"):
        raise RuntimeError(
            "La fuente descargada no parece una lista M3U."
        )

    if "#EXTINF" not in texto:
        raise RuntimeError(
            "Elcano no ha devuelto canales. "
            "Se conserva la lista anterior."
        )

    return texto


# ==========================================================
# EXTRAER IDS ACESTREAM
# ==========================================================

def extraer_id_acestream(url):

    url = url.strip()

    if not url:
        return ""

    # Formato acestream://HASH
    if url.lower().startswith("acestream://"):

        identificador = url.split(
            "://", 1
        )[1].strip()

        identificador = identificador.split(
            "?", 1
        )[0].split("&", 1)[0]

        if re.fullmatch(
            r"[a-fA-F0-9]{20,64}",
            identificador
        ):
            return identificador

    # Formato /ace/getstream?id=HASH
    if "/ace/getstream?id=" in url:

        identificador = url.split(
            "/ace/getstream?id=", 1
        )[1].split("&", 1)[0].strip()

        if re.fullmatch(
            r"[a-fA-F0-9]{20,64}",
            identificador
        ):
            return identificador

    # Otros formatos con id o infohash
    coincidencia = re.search(
        r"(?:infohash=|id=)([a-fA-F0-9]{20,64})",
        url,
        re.I
    )

    if coincidencia:
        return coincidencia.group(1)

    # Si la línea contiene directamente una ID
    if re.fullmatch(
        r"[a-fA-F0-9]{20,64}",
        url
    ):
        return url

    return ""


def convertir_url(url):

    identificador = extraer_id_acestream(url)

    if identificador:
        return URL_ACE_LOCAL + identificador

    return url.strip()


# ==========================================================
# SEPARAR REGISTROS M3U
# ==========================================================

def separar_registros(texto):

    lineas = texto.replace(
        "\ufeff", ""
    ).splitlines()

    registros = []
    actual = None

    for linea in lineas:

        linea = linea.strip()

        if not linea:
            continue

        if linea.startswith("#EXTM3U"):
            continue

        if linea.startswith("#EXTINF:"):

            if actual:
                registros.append(actual)

            actual = [linea]

        elif actual is not None:

            actual.append(linea)

    if actual:
        registros.append(actual)

    return registros


# ==========================================================
# DATOS DEL CANAL
# ==========================================================

def nombre_canal(registro):

    extinf = registro[0]

    if "," in extinf:
        return extinf.split(",", 1)[1].strip()

    return "Canal sin nombre"


def atributo(extinf, nombre):

    coincidencia = re.search(
        r'\b' + re.escape(nombre) + r'="([^"]*)"',
        extinf,
        re.I
    )

    return coincidencia.group(1).strip() if coincidencia else ""


def url_registro(registro):

    for linea in registro[1:]:

        if not linea.startswith("#"):
            return linea.strip()

    return ""


def normalizar_nombre(nombre):

    nombre = nombre.casefold()

    nombre = unicodedata.normalize(
        "NFKD",
        nombre
    )

    nombre = "".join(
        c for c in nombre
        if not unicodedata.combining(c)
    )

    nombre = re.sub(
        r"\b(4k|8k|2160p|1440p|1080p|720p|576p|540p|480p|uhd|fhd|full[ .-]?hd|hd|sd)\b",
        " ",
        nombre
    )

    nombre = re.sub(
        r"\b(hevc|h265|h264|x265|x264|hdr10?\+?|dolby[ .-]?vision)\b",
        " ",
        nombre
    )

    nombre = re.sub(
        r"\([^)]*\)|\[[^]]*\]",
        " ",
        nombre
    )

    nombre = re.sub(
        r"[^a-z0-9]+",
        " ",
        nombre
    )

    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    ).strip()

    return nombre


def clave_canal(registro):

    nombre = normalizar_nombre(
        nombre_canal(registro)
    )

    if nombre:
        return nombre

    tvg = atributo(
        registro[0],
        "tvg-id"
    )

    return tvg.casefold() if tvg else "canal sin nombre"


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


# ==========================================================
# PREPARAR REGISTROS
# ==========================================================

def preparar_registro(registro, automatico=False):

    salida = list(registro)

    extinf = salida[0]

    if automatico:

        if re.search(
            r'group-title="[^"]*"',
            extinf,
            re.I
        ):

            extinf = re.sub(
                r'group-title="[^"]*"',
                'group-title="' + GRUPO_AUTO + '"',
                extinf,
                count=1,
                flags=re.I
            )

        else:

            extinf = extinf.replace(
                ",",
                ' group-title="' + GRUPO_AUTO + '",',
                1
            )

        salida[0] = extinf

    for i in range(1, len(salida)):

        if not salida[i].startswith("#"):

            salida[i] = convertir_url(
                salida[i]
            )

    return salida


# ==========================================================
# SELECCIONAR CANALES DE ELCANO
# ==========================================================

def seleccionar_opciones(registros):

    resultado = []

    ids_encontradas = set()

    descartados = 0

    for registro in registros:

        url = url_registro(registro)

        identificador = extraer_id_acestream(url)

        # No aceptar registros sin ID AceStream válida.
        if not identificador:

            descartados += 1

            print(
                "Descartado por no tener ID válida:",
                nombre_canal(registro)
            )

            continue

        preparado = preparar_registro(
            registro,
            automatico=True
        )

        # IMPORTANTE:
        # No agrupamos por nombre ni por calidad.
        # Cada entrada original de Elcano se conserva.
        resultado.append(preparado)

        ids_encontradas.add(
            identificador.lower()
        )

    print("---------------------------------------")
    print("RESULTADO DE LA LECTURA DE ELCANO")
    print("---------------------------------------")

    print(
        "Entradas recibidas:",
        len(registros)
    )

    print(
        "Entradas con ID válida:",
        len(resultado)
    )

    print(
        "IDs diferentes:",
        len(ids_encontradas)
    )

    print(
        "Entradas descartadas:",
        descartados
    )

    nombres = set(
        clave_canal(r)
        for r in resultado
    )

    print(
        "Canales diferentes:",
        len(nombres)
    )

    print("---------------------------------------")

    return resultado


# ==========================================================
# LEER CANALES MANUALES
# ==========================================================

def leer_manual():

    if not ARCHIVO_MANUAL.exists():

        ARCHIVO_MANUAL.write_text(
            "#EXTM3U\n",
            encoding="utf-8"
        )

        print(
            "Creado canales_manuales.m3u"
        )

    texto = ARCHIVO_MANUAL.read_text(
        encoding="utf-8-sig",
        errors="replace"
    )

    if not texto.strip():
        return []

    registros = separar_registros(texto)

    resultado = []

    for registro in registros:

        resultado.append(
            preparar_registro(
                registro,
                automatico=False
            )
        )

    return resultado


# ==========================================================
# SERIALIZAR REGISTROS
# ==========================================================

def serializar_registros(registros):

    lineas = []

    for registro in registros:

        lineas.extend(registro)

    return "\n".join(lineas)


# ==========================================================
# HISTORIAL DE CAMBIOS
# ==========================================================

def firma(registro):

    contenido = "\n".join(
        registro
    ).strip()

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def mapa_registros(registros):

    resultado = {}

    contadores = Counter()

    for registro in registros:

        canal = clave_canal(registro)

        calidad = rango_calidad(registro)

        base = f"{canal}|calidad-{calidad}"

        # Permite conservar varias entradas del mismo canal
        # y de la misma calidad en el historial.
        contadores[base] += 1

        clave = (
            f"{base}|opcion-{contadores[base]}"
        )

        resultado[clave] = {
            "nombre": nombre_canal(registro),
            "calidad": calidad,
            "hash": firma(registro)
        }

    return resultado


def cargar_historial():

    if not ARCHIVO_HISTORIAL.exists():
        return None

    try:

        datos = json.loads(
            ARCHIVO_HISTORIAL.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(datos, dict):

            raise ValueError(
                "El historial no contiene un objeto JSON."
            )

        return datos

    except Exception as e:

        raise RuntimeError(
            "historial.json no se puede leer. "
            "Se detiene para proteger el historial: "
            + str(e)
        )


def registrar_cambios(registros):

    anterior = cargar_historial()
    actual = mapa_registros(registros)

    ahora = datetime.now(
        timezone.utc
    ).strftime("%d/%m/%Y %H:%M UTC")

    if anterior is None:
        ARCHIVO_HISTORIAL.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        ARCHIVO_CAMBIOS.write_text(
            "# Última actualización ACE-AUTO\n\n"
            "Primera sincronización completada.\n",
            encoding="utf-8"
        )

        print("Primera sincronización.")
        return

    nuevos = [k for k in actual if k not in anterior]

    eliminados = [k for k in anterior if k not in actual]

    modificados = [
        k for k in actual
        if (
            k in anterior
            and actual[k]["hash"] != anterior[k].get("hash")
        )
    ]

    # Actualizar el historial interno.
    ARCHIVO_HISTORIAL.write_text(
        json.dumps(actual, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Si no hay cambios, conservar la última actualización mostrada.
    if not nuevos and not eliminados and not modificados:
        print("Sin cambios. Se conserva la última actualización.")
        return

    # Crear exclusivamente el último resultado.
    informe = [
        "# Última actualización ACE-AUTO",
        "",
        f"Fecha: {ahora}",
        "",
        f"Canales añadidos: {len(nuevos)}",
        f"Canales eliminados: {len(eliminados)}",
        f"Canales modificados: {len(modificados)}"
    ]

    for titulo, claves in (
        ("Añadidos", nuevos),
        ("Eliminados", eliminados),
        ("Modificados", modificados)
    ):

        if claves:
            informe.extend(["", f"### {titulo}"])

            for clave in claves:
                if clave in actual:
                    nombre = actual[clave]["nombre"]
                else:
                    nombre = anterior[clave]["nombre"]

                informe.append(f"- {nombre}")

    # SOBRESCRIBIR: nunca acumular informes anteriores.
    ARCHIVO_CAMBIOS.write_text(
        "\n".join(informe) + "\n",
        encoding="utf-8"
    )

    print("Última actualización guardada correctamente.")


# ==========================================================
# PROCESO PRINCIPAL
# ==========================================================

def main():

    print("=" * 55)
    print("ACTUALIZANDO ACE-AUTO")
    print("=" * 55)

    # 1. Descargar fuente original
    fuente = descargar_fuente()

    # 2. Separar las entradas originales
    registros_fuente = separar_registros(
        fuente
    )

    if not registros_fuente:

        raise RuntimeError(
            "Elcano no devolvió registros válidos."
        )

    # 3. Procesar exclusivamente las entradas de Elcano
    automaticos = seleccionar_opciones(
        registros_fuente
    )

    if not automaticos:

        raise RuntimeError(
            "No se encontraron IDs AceStream válidas. "
            "Se conserva la lista anterior."
        )

    # 4. Generar canales.m3u SOLO con Elcano
    texto_auto = (
        CABECERA
        + "\n"
        + serializar_registros(automaticos)
        + "\n"
    )

    ARCHIVO_AUTO.write_text(
        texto_auto,
        encoding="utf-8"
    )

    print(
        "canales.m3u actualizado exclusivamente con Elcano."
    )

    # 5. Leer canales manuales por separado
    manuales = leer_manual()

    # 6. Combinar automáticos y manuales
    todos = automaticos + manuales

    final = (
        "\n".join(CABECERA_FINAL)
        + "\n"
        + serializar_registros(todos)
        + "\n"
    )

    # 7. Registrar cambios solo de Elcano
    registrar_cambios(
        automaticos
    )

    # 8. Publicar lista final
    publicar_git_gay(
        final
    )

    print("---------------------------------------")
    print("RESUMEN FINAL ACE-AUTO")
    print("---------------------------------------")

    print(
        "Entradas automáticas:",
        len(automaticos)
    )

    print(
        "Entradas manuales:",
        len(manuales)
    )

    print(
        "Total publicado:",
        len(todos)
    )

    print("---------------------------------------")
    print("ACTUALIZACIÓN TERMINADA")
    print("=" * 55)


if __name__ == "__main__":

    main()
