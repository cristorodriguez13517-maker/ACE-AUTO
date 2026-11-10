import os
import re
import json
import base64
import hashlib
import requests
from pathlib import Path
from datetime import datetime

# ==========================================
# CONFIGURACION
# ==========================================

TOKEN = os.environ["GIT_GAY_TOKEN"]

FUENTE_ELCANO = (
    "https://tokyo2.elcano-ipfs.workers.dev/"
    "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs/"
    "hashes_acestream.m3u"
)

API = "https://git.gay/api/v1"

PROPIETARIO = "iptvpro2026"
REPOSITORIO = "lista"
RAMA = "main"
ARCHIVO_DESTINO = "hashes.m3u"

ARCHIVO_AUTO = Path("canales.m3u")
ARCHIVO_MANUAL = Path("canales_manuales.m3u")
ARCHIVO_HISTORIAL = Path("historial.json")
ARCHIVO_CAMBIOS = Path("cambios.md")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# ==========================================
# DESCARGAR LISTA AUTOMATICA
# ==========================================

def descargar_elcano():

    print("Descargando lista de Elcano...")

    respuesta = requests.get(
        FUENTE_ELCANO,
        timeout=90,
        headers={
            "User-Agent": "ACE-AUTO/1.0"
        }
    )

    respuesta.raise_for_status()

    contenido = respuesta.content.decode(
        "utf-8-sig"
    ).strip()

    if not contenido.startswith("#EXTM3U"):
        raise Exception("La fuente de Elcano no contiene una M3U valida")

    registros = analizar_lista(contenido)

    if not registros:
        raise Exception("Elcano no ha devuelto canales validos")

    ARCHIVO_AUTO.write_text(
        contenido + "\n",
        encoding="utf-8"
    )

    print("Canales automaticos:", len(registros))

    return registros


# ==========================================
# ANALIZAR LISTA M3U
# ==========================================

def analizar_lista(contenido):

    lineas = contenido.splitlines()

    registros = []
    actual = []

    for linea in lineas:

        linea = linea.strip()

        if not linea:
            continue

        if linea.startswith("#EXTINF:"):

            if actual:
                registros.append(actual)

            actual = [linea]

        elif actual:

            actual.append(linea)

    if actual:
        registros.append(actual)

    resultado = {}

    for registro in registros:

        info = registro[0]

        urls = [
            linea for linea in registro[1:]
            if linea and not linea.startswith("#")
        ]

        if not urls:
            continue

        nombre_match = re.search(r",\s*(.*)$", info)

        nombre = (
            nombre_match.group(1).strip()
            if nombre_match
            else "Canal sin nombre"
        )

        grupo_match = re.search(
            r'group-title="([^"]*)"',
            info
        )

        grupo = (
            grupo_match.group(1)
            if grupo_match
            else "Sin categoria"
        )

        id_match = re.search(
            r'tvg-id="([^"]*)"',
            info
        )

        tvg_id = (
            id_match.group(1)
            if id_match
            else ""
        )

        # Identificador estable para comparar canales.
        if tvg_id:
            clave = "ID:" + tvg_id
        else:
            clave = "NOMBRE:" + grupo + "|" + nombre

        base = clave
        numero = 2

        while clave in resultado:
            clave = f"{base}#{numero}"
            numero += 1

        huella = hashlib.sha256(
            "\n".join(registro).encode("utf-8")
        ).hexdigest()

        resultado[clave] = {
            "nombre": nombre,
            "grupo": grupo,
            "huella": huella,
            "registro": registro
        }

    return resultado


# ==========================================
# LEER LISTA MANUAL
# ==========================================

def leer_manuales():

    if not ARCHIVO_MANUAL.exists():
        ARCHIVO_MANUAL.write_text(
            "#EXTM3U\n",
            encoding="utf-8"
        )

    contenido = ARCHIVO_MANUAL.read_text(
        encoding="utf-8-sig"
    ).strip()

    if not contenido:
        raise Exception("El archivo manual esta vacio o incorrecto")

    if not contenido.startswith("#EXTM3U"):
        raise Exception("La lista manual no tiene cabecera M3U")

    registros = analizar_lista(contenido)

    if len(registros) == 0:
        print("No hay canales manuales todavia")

    return contenido


# ==========================================
# LEER HISTORIAL
# ==========================================

def leer_historial():

    if not ARCHIVO_HISTORIAL.exists():
        return {}

    try:

        return json.loads(
            ARCHIVO_HISTORIAL.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        raise Exception(
            "historial.json esta dañado. "
            "No se sobrescribira."
        )


# ==========================================
# COMPARAR CAMBIOS
# ==========================================

def comparar(anterior, actual):

    nuevos = []
    eliminados = []
    modificados = []

    for clave, canal in actual.items():

        if clave not in anterior:

            nuevos.append(canal)

        elif canal["huella"] != anterior[clave]["huella"]:

            modificados.append({
                "anterior": anterior[clave],
                "actual": canal
            })

    for clave, canal in anterior.items():

        if clave not in actual:
            eliminados.append(canal)

    return nuevos, eliminados, modificados


# ==========================================
# GUARDAR HISTORIAL
# ==========================================

def guardar_historial(canales):

    datos = {}

    for clave, canal in canales.items():

        datos[clave] = {
            "nombre": canal["nombre"],
            "grupo": canal["grupo"],
            "huella": canal["huella"]
        }

    ARCHIVO_HISTORIAL.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ==========================================
# GENERAR INFORME
# ==========================================

def generar_informe(nuevos, eliminados, modificados):

    fecha = datetime.now().astimezone().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    lineas = [
        f"\n## Actualizacion: {fecha}\n",
        f"- Canales nuevos: {len(nuevos)}",
        f"- Canales eliminados: {len(eliminados)}",
        f"- Canales modificados: {len(modificados)}",
        "",
        "### Canales nuevos"
    ]

    for canal in nuevos:
        lineas.append(
            f"- {canal['nombre']} ({canal['grupo']})"
        )

    if not nuevos:
        lineas.append("- Ninguno")

    lineas.extend([
        "",
        "### Canales eliminados"
    ])

    for canal in eliminados:
        lineas.append(
            f"- {canal['nombre']} ({canal['grupo']})"
        )

    if not eliminados:
        lineas.append("- Ninguno")

    lineas.extend([
        "",
        "### Canales modificados"
    ])

    for cambio in modificados:

        lineas.append(
            f"- {cambio['actual']['nombre']}"
        )

    if not modificados:
        lineas.append("- Ninguno")

    lineas.append("\n---\n")

    anterior = ""

    if ARCHIVO_CAMBIOS.exists():
        anterior = ARCHIVO_CAMBIOS.read_text(
            encoding="utf-8"
        )

    if not anterior.strip():
        anterior = "# HISTORIAL DE CAMBIOS ACESTREAM\n"

    ARCHIVO_CAMBIOS.write_text(
        anterior + "\n".join(lineas),
        encoding="utf-8"
    )


# ==========================================
# CREAR LISTA COMBINADA
# ==========================================

def crear_lista_final():

    automaticos = ARCHIVO_AUTO.read_text(
        encoding="utf-8-sig"
    ).strip()

    manuales = ARCHIVO_MANUAL.read_text(
        encoding="utf-8-sig"
    ).strip()

    lineas = ["#EXTM3U"]

    # Primero los canales automaticos.
    for contenido in (automaticos, manuales):

        registros = analizar_lista(contenido)

        for canal in registros.values():

            lineas.extend(canal["registro"])

    return "\n".join(lineas) + "\n"


# ==========================================
# PUBLICAR EN GIT.GAY
# ==========================================

def publicar(contenido):

    url = (
        f"{API}/repos/{PROPIETARIO}/"
        f"{REPOSITORIO}/contents/{ARCHIVO_DESTINO}"
    )

    print("Consultando archivo remoto...")

    respuesta = requests.get(
        url,
        headers=HEADERS,
        params={"ref": RAMA},
        timeout=30
    )

    sha = None

    if respuesta.status_code == 200:

        sha = respuesta.json().get("sha")

    elif respuesta.status_code != 404:

        raise Exception(
            f"Error consultando git.gay: {respuesta.status_code} "
            f"{respuesta.text}"
        )

    datos = {
        "message": "Actualizar lista ACESTREAM desde ACE-AUTO",
        "content": base64.b64encode(
            contenido.encode("utf-8")
        ).decode("utf-8"),
        "branch": RAMA
    }

    if sha:
        datos["sha"] = sha

    print("Publicando lista combinada...")

    respuesta = requests.put(
        url,
        headers=HEADERS,
        json=datos,
        timeout=60
    )

    if respuesta.status_code not in (200, 201):

        raise Exception(
            f"Error publicando lista: {respuesta.status_code} "
            f"{respuesta.text}"
        )

    print("Lista publicada correctamente")


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():

    print("================================")
    print("ACTUALIZADOR ACE-AUTO")
    print("================================")

    automaticos = descargar_elcano()

    manuales = leer_manuales()

    anterior = leer_historial()

    # La primera ejecucion establece la referencia.
    if not anterior:

        print("Primera ejecucion: creando referencia inicial")

        nuevos = []
        eliminados = []
        modificados = []

    else:

        nuevos, eliminados, modificados = comparar(
            anterior,
            automaticos
        )

    print("Canales automaticos:", len(automaticos))
    print("Canales nuevos:", len(nuevos))
    print("Canales eliminados:", len(eliminados))
    print("Canales modificados:", len(modificados))

    generar_informe(
        nuevos,
        eliminados,
        modificados
    )

    lista_final = crear_lista_final()

    if not lista_final.startswith("#EXTM3U"):
        raise Exception("Lista final incorrecta")

    publicar(lista_final)

    guardar_historial(automaticos)

    print("================================")
    print("ACTUALIZACION COMPLETADA")
    print("Canales manuales conservados")
    print("================================")


if __name__ == "__main__":
    main()
