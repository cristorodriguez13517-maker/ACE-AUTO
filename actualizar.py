import os
import re
import json
import base64
import hashlib
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests


# ==========================================================
# CONFIGURACION ACE-AUTO
# ==========================================================

FUENTES_ELCANO = [
    (
        "Elcano original",
        "https://tokyo2.elcano-ipfs.workers.dev/"
        "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs/"
        "hashes_acestream.m3u"
    ),
    (
        "IPFS.io",
        "https://ipfs.io/ipns/"
        "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs/"
        "hashes_acestream.m3u"
    ),
    (
        "DWeb.link",
        "https://k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs."
        "ipns.dweb.link/hashes_acestream.m3u"
    ),
]

API_GIT_GAY = "https://git.gay/api/v1"
REPO_GIT_GAY = "iptvpro2026/lista"
RAMA_GIT_GAY = "main"
ARCHIVO_DESTINO = "hashes.m3u"

ARCHIVO_AUTO = Path("canales.m3u")
ARCHIVO_TDT = Path("canales_tdt.m3u")
ARCHIVO_RADIO = Path("canales_radio.m3u")
ARCHIVO_MANUAL = Path("canales_manuales.m3u")
ARCHIVO_HISTORIAL = Path("historial.json")
ARCHIVO_CAMBIOS = Path("cambios.md")

# Archivo que utilizará la página de GitHub Pages.
ARCHIVO_WEB = Path("datos/canales.m3u")

GRUPO_AUTO = "CANO AUTO"
GRUPO_TDT = "TDT AUTO"
GRUPO_RADIO = "RADIOS AUTO"

FUENTE_TDT = "https://www.tdtchannels.com/lists/tv.m3u"
FUENTE_RADIO = "https://www.tdtchannels.com/lists/radio.m3u"

URL_ACE_LOCAL = "http://127.0.0.1:6878/ace/getstream?id="

EPG_URLS = [
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml",
    "https://www.tdtchannels.com/epg/TV.xml.gz",
    "https://www.ondachannels.com/epg/RADIO.xml.gz",
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
# DESCARGAR FUENTES DE ELCANO CON RESPALDO AUTOMATICO
# ==========================================================

def descargar_fuente():

    print("=" * 55)
    print("BUSCANDO UNA FUENTE DISPONIBLE DE ELCANO")
    print("=" * 55)

    errores = []

    for nombre, url in FUENTES_ELCANO:

        print()
        print("Probando fuente:", nombre)
        print("URL:", url)

        try:

            respuesta = SESION.get(
                url,
                timeout=90
            )

            respuesta.raise_for_status()

            texto = respuesta.content.decode(
                "utf-8-sig",
                errors="replace"
            ).strip()

            if not texto.startswith("#EXTM3U"):
                raise RuntimeError(
                    "La respuesta no es una lista M3U válida."
                )

            if "#EXTINF" not in texto:
                raise RuntimeError(
                    "La lista no contiene canales."
                )

            registros = separar_registros(texto)

            validos = [
                registro
                for registro in registros
                if extraer_id_acestream(
                    url_registro(registro)
                )
            ]

            if not validos:
                raise RuntimeError(
                    "La lista no contiene hashes AceStream válidos."
                )

            print("---------------------------------------")
            print("FUENTE ELCANO SELECCIONADA:", nombre)
            print("Entradas recibidas:", len(registros))
            print("Canales con ID válida:", len(validos))
            print("---------------------------------------")

            return texto

        except Exception as error:

            mensaje = f"{nombre}: {error}"

            errores.append(mensaje)

            print("ERROR:", mensaje)
            print("Probando la siguiente fuente...")

    raise RuntimeError(
        "NINGUNA FUENTE DE ELCANO ESTÁ DISPONIBLE.\n"
        "Se detiene la actualización para proteger "
        "el catálogo anterior.\n\n"
        + "\n".join(errores)
    )


# ==========================================================
# DESCARGAR TDT
# ==========================================================

def descargar_fuente_tdt():

    print("Descargando lista oficial de TDTChannels...")

    respuesta = SESION.get(
        FUENTE_TDT,
        timeout=120
    )

    respuesta.raise_for_status()

    texto = respuesta.content.decode(
        "utf-8-sig",
        errors="replace"
    ).strip()

    if not texto.startswith("#EXTM3U"):
        raise RuntimeError(
            "TDTChannels no ha devuelto una lista M3U válida."
        )

    if "#EXTINF" not in texto:
        raise RuntimeError(
            "La lista de TDTChannels no contiene canales. "
            "Se detiene la actualización para no publicar una lista incompleta."
        )

    return texto


# ==========================================================
# DESCARGAR RADIO
# ==========================================================

def descargar_fuente_radio():

    print("Descargando lista oficial de radios de TDTChannels...")

    respuesta = SESION.get(
        FUENTE_RADIO,
        timeout=120
    )

    respuesta.raise_for_status()

    texto = respuesta.content.decode(
        "utf-8-sig",
        errors="replace"
    ).strip()

    if not texto.startswith("#EXTM3U"):
        raise RuntimeError(
            "TDTChannels no ha devuelto una lista M3U de radio válida."
        )

    if "#EXTINF" not in texto:
        raise RuntimeError(
            "La lista de radios de TDTChannels está vacía. "
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


def asignar_grupo(extinf, grupo):

    if re.search(r'group-title="[^"]*"', extinf, re.I):
        return re.sub(
            r'group-title="[^"]*"',
            'group-title="' + grupo + '"',
            extinf,
            count=1,
            flags=re.I
        )

    return extinf.replace(",", ' group-title="' + grupo + '",', 1)


def preparar_registro_tdt(registro):

    salida = list(registro)
    salida[0] = asignar_grupo(salida[0], GRUPO_TDT)

    return salida


def es_formato_radio_permitido(url):

    ruta = urlsplit(url.strip()).path.lower()

    return ruta.endswith(
        (".aac", ".mp3", ".m3u8")
    )


def preparar_registro_radio(registro):

    salida = list(registro)
    salida[0] = asignar_grupo(salida[0], GRUPO_RADIO)

    return salida


# ==========================================================
# PREPARAR REGISTROS
# ==========================================================

def preparar_registro(registro, automatico=False):

    salida = list(registro)

    extinf = salida[0]

    if automatico:

        extinf = asignar_grupo(extinf, GRUPO_AUTO)
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

    nuevos = [
        k for k in actual
        if k not in anterior
    ]

    eliminados = [
        k for k in anterior
        if k not in actual
    ]

    modificados = [
        k for k in actual
        if (
            k in anterior
            and actual[k]["hash"] != anterior[k].get("hash")
        )
    ]

    ARCHIVO_HISTORIAL.write_text(
        json.dumps(actual, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    if not nuevos and not eliminados and not modificados:

        print("Sin cambios. Se conserva la última actualización.")
        return

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

            informe.extend([
                "",
                f"### {titulo}"
            ])

            for clave in claves:

                if clave in actual:
                    nombre = actual[clave]["nombre"]
                else:
                    nombre = anterior[clave]["nombre"]

                informe.append(
                    f"- {nombre}"
                )

    ARCHIVO_CAMBIOS.write_text(
        "\n".join(informe) + "\n",
        encoding="utf-8"
    )

    print("Última actualización guardada correctamente.")


# ==========================================================
# PUBLICAR LISTA EN GIT.GAY
# ==========================================================

def publicar_git_gay(contenido):

    token = os.environ.get(
        "GIT_GAY_TOKEN",
        ""
    ).strip()

    if not token:

        raise RuntimeError(
            "Falta el secreto GIT_GAY_TOKEN en GitHub Actions."
        )

    url = (
        f"{API_GIT_GAY}/repos/"
        f"{REPO_GIT_GAY}/contents/{ARCHIVO_DESTINO}"
    )

    cabeceras = {
        "Authorization": f"token {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ACE-AUTO/2.0",
    }

    respuesta = SESION.get(
        url,
        headers=cabeceras,
        params={"ref": RAMA_GIT_GAY},
        timeout=60,
    )

    sha = None

    if respuesta.status_code == 200:

        try:
            datos = respuesta.json()

        except ValueError as error:

            raise RuntimeError(
                "git.gay devolvió una respuesta no válida al consultar "
                f"{ARCHIVO_DESTINO}: {respuesta.text[:500]}"
            ) from error

        sha = datos.get("sha")

        if not sha:

            raise RuntimeError(
                "git.gay encontró el archivo, pero no devolvió su SHA."
            )

    elif respuesta.status_code != 404:

        raise RuntimeError(
            "No se pudo consultar el archivo en git.gay. "
            f"HTTP {respuesta.status_code}: {respuesta.text[:1000]}"
        )

    contenido_codificado = base64.b64encode(
        contenido.encode("utf-8")
    ).decode("utf-8")

    datos_put = {
        "message": "Actualizar lista ACE-AUTO",
        "content": contenido_codificado,
        "branch": RAMA_GIT_GAY,
    }

    if sha:
        datos_put["sha"] = sha

    publicacion = SESION.put(
        url,
        headers=cabeceras,
        json=datos_put,
        timeout=120,
    )

    if publicacion.status_code not in (200, 201):

        raise RuntimeError(
            "No se pudo publicar hashes.m3u en git.gay. "
            f"HTTP {publicacion.status_code}: "
            f"{publicacion.text[:1500]}"
        )

    print("Lista publicada correctamente en git.gay.")

    return True


# ==========================================================
# GUARDAR LISTA PARA GITHUB PAGES
# ==========================================================

def guardar_lista_web(contenido):

    # Crear la carpeta datos si todavía no existe.
    ARCHIVO_WEB.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Guardar la lista unificada.
    ARCHIVO_WEB.write_text(
        contenido,
        encoding="utf-8"
    )

    print("---------------------------------------")
    print("LISTA WEB GUARDADA CORRECTAMENTE")
    print("---------------------------------------")
    print("Archivo:", ARCHIVO_WEB)
    print("Tamaño:", ARCHIVO_WEB.stat().st_size, "bytes")
    print("---------------------------------------")


# ==========================================================
# PROCESO PRINCIPAL
# ==========================================================

def main():

    print("=" * 55)
    print("ACTUALIZANDO ACE-AUTO")
    print("=" * 55)

    # 1. Descargar Elcano utilizando las tres fuentes de respaldo.
    fuente = descargar_fuente()

    # 2. Separar las entradas originales.
    registros_fuente = separar_registros(
        fuente
    )

    if not registros_fuente:

        raise RuntimeError(
            "Elcano no devolvió registros válidos."
        )

    # 3. Procesar exclusivamente las entradas de Elcano.
    automaticos = seleccionar_opciones(
        registros_fuente
    )

    if not automaticos:

        raise RuntimeError(
            "No se encontraron IDs AceStream válidas. "
            "Se conserva la lista anterior."
        )

    # 4. Generar canales.m3u SOLO con Elcano.
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

    # 5. Descargar y procesar TDTChannels.
    fuente_tdt = descargar_fuente_tdt()

    registros_tdt_fuente = separar_registros(
        fuente_tdt
    )

    if not registros_tdt_fuente:

        raise RuntimeError(
            "TDTChannels no devolvió registros válidos. "
            "Se conserva la lista anterior."
        )

    canales_tdt = [
        preparar_registro_tdt(registro)
        for registro in registros_tdt_fuente
        if url_registro(registro)
    ]

    if not canales_tdt:

        raise RuntimeError(
            "No se encontraron canales TDT con URL. "
            "Se conserva la lista anterior."
        )

    texto_tdt = (
        CABECERA
        + "\n# Fuente: TDTChannels - https://github.com/LaQuay/TDTChannels"
        + "\n"
        + serializar_registros(canales_tdt)
        + "\n"
    )

    ARCHIVO_TDT.write_text(
        texto_tdt,
        encoding="utf-8"
    )

    print(
        "canales_tdt.m3u actualizado exclusivamente con TDT AUTO."
    )

    # 6. Descargar y procesar RADIOS AUTO.
    fuente_radio = descargar_fuente_radio()

    registros_radio_fuente = separar_registros(
        fuente_radio
    )

    if not registros_radio_fuente:

        raise RuntimeError(
            "TDTChannels no devolvió registros de radio válidos. "
            "Se conserva la lista anterior."
        )

    canales_radio = []

    descartadas_radio = 0

    for registro in registros_radio_fuente:

        url = url_registro(registro)

        if not url or not es_formato_radio_permitido(url):

            descartadas_radio += 1
            continue

        canales_radio.append(
            preparar_registro_radio(registro)
        )

    if not canales_radio:

        raise RuntimeError(
            "No se encontraron radios AAC, MP3 o M3U8. "
            "Se conserva la lista anterior."
        )

    texto_radio = (
        CABECERA
        + "\n# Fuente: TDTChannels RADIO.md - "
        "https://github.com/LaQuay/TDTChannels/blob/master/RADIO.md"
        + "\n"
        + serializar_registros(canales_radio)
        + "\n"
    )

    ARCHIVO_RADIO.write_text(
        texto_radio,
        encoding="utf-8"
    )

    print(
        "canales_radio.m3u actualizado exclusivamente con RADIOS AUTO."
    )

    print(
        "Radios incluidas (AAC/MP3/M3U8):",
        len(canales_radio)
    )

    print(
        "Streams descartados por otro formato:",
        descartadas_radio
    )

    # 7. Leer canales manuales.
    manuales = leer_manual()

    # 8. Crear una única lista con los cuatro grupos.
    todos = (
        automaticos
        + canales_tdt
        + canales_radio
        + manuales
    )

    final = (
        "\n".join(CABECERA_FINAL)
        + "\n# Fuente TDT AUTO: https://github.com/LaQuay/TDTChannels"
        + "\n# Fuente RADIOS AUTO: https://github.com/LaQuay/TDTChannels/blob/master/RADIO.md"
        + "\n"
        + serializar_registros(todos)
        + "\n"
    )

    # 9. Guardar la lista unificada para GitHub Pages.
    guardar_lista_web(
        final
    )

    # 10. Registrar cambios solo de Elcano.
    registrar_cambios(
        automaticos
    )

    # 11. Publicar la lista final en git.gay.
    publicar_git_gay(
        final
    )

    # 12. Resumen final.
    print("---------------------------------------")
    print("RESUMEN FINAL ACE-AUTO")
    print("---------------------------------------")

    print(
        "Entradas automáticas CANO AUTO:",
        len(automaticos)
    )

    print(
        "Entradas TDT AUTO:",
        len(canales_tdt)
    )

    print(
        "Entradas RADIOS AUTO:",
        len(canales_radio)
    )

    print(
        "Entradas manuales:",
        len(manuales)
    )

    print(
        "Total publicado:",
        len(todos)
    )

    print(
        "Lista web:",
        ARCHIVO_WEB
    )

    print("---------------------------------------")
    print("ACTUALIZACIÓN TERMINADA")
    print("=" * 55)


if __name__ == "__main__":

    main()
