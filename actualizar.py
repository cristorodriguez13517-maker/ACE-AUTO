import os
import base64
import requests
from pathlib import Path

# =====================================
# CONFIGURACIÓN
# =====================================

TOKEN = os.environ["GIT_GAY_TOKEN"]

API = "https://git.gay/api/v1"

PROPIETARIO = "iptvpro2026"
REPOSITORIO = "lista"
RAMA = "main"
ARCHIVO = "hashes.m3u"

ARCHIVO_LOCAL = Path("canales.m3u")

# =====================================
# CABECERAS
# =====================================

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# =====================================
# LEER LISTA LOCAL
# =====================================

def leer_lista():

    if not ARCHIVO_LOCAL.exists():
        raise Exception("No existe canales.m3u")

    contenido = ARCHIVO_LOCAL.read_text(
        encoding="utf-8"
    ).strip()

    if not contenido:
        raise Exception("La lista está vacía")

    if not contenido.startswith("#EXTM3U"):
        raise Exception("Formato M3U incorrecto")

    lineas = [
        linea.strip()
        for linea in contenido.splitlines()
        if linea.strip()
    ]

    entradas = [
        linea for linea in lineas
        if not linea.startswith("#")
    ]

    if not entradas:
        raise Exception("No hay entradas en la lista")

    return contenido + "\n"


# =====================================
# ACTUALIZAR REPOSITORIO GIT.GAY
# =====================================

def publicar(contenido):

    url = (
        f"{API}/repos/"
        f"{PROPIETARIO}/{REPOSITORIO}/contents/{ARCHIVO}"
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
        datos = respuesta.json()
        sha = datos.get("sha")
        print("Archivo existente encontrado")

    elif respuesta.status_code == 404:
        print("El archivo todavía no existe")

    else:
        raise Exception(
            f"Error consultando archivo: "
            f"{respuesta.status_code} {respuesta.text}"
        )

    contenido_base64 = base64.b64encode(
        contenido.encode("utf-8")
    ).decode("utf-8")

    datos = {
        "message": "Actualizar lista ACESTREAM desde ACE-AUTO",
        "content": contenido_base64,
        "branch": RAMA
    }

    if sha:
        datos["sha"] = sha

    print("Publicando lista...")

    respuesta = requests.put(
        url,
        headers=HEADERS,
        json=datos,
        timeout=60
    )

    if respuesta.status_code not in (200, 201):
        raise Exception(
            f"Error publicando: "
            f"{respuesta.status_code} {respuesta.text}"
        )

    print("--------------------------------")
    print("LISTA ACTUALIZADA CORRECTAMENTE")
    print("--------------------------------")

    print(
        "Archivo publicado:",
        f"https://git.gay/{PROPIETARIO}/{REPOSITORIO}/src/branch/{RAMA}/{ARCHIVO}"
    )


# =====================================
# PROGRAMA PRINCIPAL
# =====================================

def main():

    print("--------------------------------")
    print("ACTUALIZADOR ACESTREAM")
    print("--------------------------------")

    contenido = leer_lista()

    print("Lista local comprobada")

    publicar(contenido)


if __name__ == "__main__":
    main()
