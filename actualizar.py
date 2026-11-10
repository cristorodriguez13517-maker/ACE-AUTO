import os
import re
import json
import base64
import requests
from pathlib import Path
from datetime import datetime, timezone

# =====================================
# CONFIGURACIÓN
# =====================================

TOKEN = os.environ["GIT_GAY_TOKEN"]

API = "https://git.gay/api/v1"

PROPIETARIO = "iptvpro2026"
REPOSITORIO = "lista"
RAMA = "main"
ARCHIVO = "hashes.m3u"

LISTA_LOCAL = Path("canales.m3u")
HISTORIAL = Path("historial.json")
INFORME = Path("cambios.md")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}


# =====================================
# LEER LISTA M3U
# =====================================

def leer_canales():

    if not LISTA_LOCAL.exists():
        raise Exception("No existe canales.m3u")

    contenido = LISTA_LOCAL.read_text(
        encoding="utf-8-sig"
    ).strip()

    if not contenido.startswith("#EXTM3U"):
        raise Exception("Formato M3U incorrecto")

    lineas = contenido.splitlines()

    canales = {}
    info = None
    numero = 0

    for linea in lineas:

        linea = linea.strip()

        if linea.startswith("#EXTINF:"):
            info = linea

        elif linea and not linea.startswith("#") and info:

            numero += 1

            partes = info.split(",", 1)

            nombre = (
                partes[1].strip()
                if len(partes) > 1
                else f"Canal {numero}"
            )

            grupo = re.search(
                r'group-title="([^"]*)"',
                info
            )

            categoria = (
                grupo.group(1)
                if grupo
                else "Sin categoría"
            )

            clave = f"{categoria} | {nombre}"

            # Evitar colisiones cuando hay nombres repetidos.
            base = clave
            repetido = 2

            while clave in canales:
                clave = f"{base} [{repetido}]"
                repetido += 1

            canales[clave] = {
                "nombre": nombre,
                "categoria": categoria,
                "url": linea
            }

            info = None

    if not canales:
        raise Exception("No se encontraron canales en la lista")

    return contenido + "\n", canales


# =====================================
# LEER HISTORIAL ANTERIOR
# =====================================

def leer_historial():

    if not HISTORIAL.exists():
        return {}

    try:
        return json.loads(
            HISTORIAL.read_text(encoding="utf-8")
        )
    except Exception:
        raise Exception(
            "historial.json está dañado. "
            "No se sobrescribirá."
        )


# =====================================
# COMPARAR LISTAS
# =====================================

def comparar(anterior, actual):

    nuevos = []
    eliminados = []
    modificados = []

    for clave, canal in actual.items():

        if clave not in anterior:
            nuevos.append(canal)

        elif anterior[clave]["url"] != canal["url"]:

            modificados.append({
                "anterior": anterior[clave],
                "actual": canal
            })

    for clave, canal in anterior.items():

        if clave not in actual:
            eliminados.append(canal)

    return nuevos, eliminados, modificados


# =====================================
# GUARDAR HISTORIAL
# =====================================

def guardar_historial(canales):

    HISTORIAL.write_text(
        json.dumps(
            canales,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# =====================================
# GENERAR INFORME
# =====================================

def generar_informe(nuevos, eliminados, modificados):

    fecha = datetime.now().astimezone().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    lineas = [
        f"\n## Actualización: {fecha}\n",
        f"- Canales nuevos: {len(nuevos)}",
        f"- Canales eliminados: {len(eliminados)}",
        f"- Canales modificados: {len(modificados)}",
        ""
    ]

    lineas.append("### 🟢 Canales nuevos")

    if nuevos:
        for canal in nuevos:
            lineas.append(
                f"- {canal['nombre']} ({canal['categoria']})"
            )
    else:
        lineas.append("- Ninguno")

    lineas.append("")
    lineas.append("### 🔴 Canales eliminados")

    if eliminados:
        for canal in eliminados:
            lineas.append(
                f"- {canal['nombre']} ({canal['categoria']})"
            )
    else:
        lineas.append("- Ninguno")

    lineas.append("")
    lineas.append("### 🟡 Canales modificados")

    if modificados:
        for cambio in modificados:
            lineas.append(
                f"- {cambio['actual']['nombre']}"
            )
    else:
        lineas.append("- Ninguno")

    lineas.append("\n---\n")

    anterior = ""

    if INFORME.exists():
        anterior = INFORME.read_text(encoding="utf-8")

    if not anterior.strip():
        anterior = "# HISTORIAL DE CAMBIOS ACESTREAM\n"

    INFORME.write_text(
        anterior + "\n".join(lineas),
        encoding="utf-8"
    )


# =====================================
# PUBLICAR EN GIT.GAY
# =====================================

def publicar(contenido):

    url = (
        f"{API}/repos/{PROPIETARIO}/"
        f"{REPOSITORIO}/contents/{ARCHIVO}"
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
            f"Error consultando git.gay: {respuesta.text}"
        )

    datos = {
        "message": "Actualizar lista ACESTREAM",
        "content": base64.b64encode(
            contenido.encode("utf-8")
        ).decode("utf-8"),
        "branch": RAMA
    }

    if sha:
        datos["sha"] = sha

    respuesta = requests.put(
        url,
        headers=HEADERS,
        json=datos,
        timeout=60
    )

    if respuesta.status_code not in (200, 201):
        raise Exception(
            f"Error publicando lista: {respuesta.text}"
        )

    print("Lista publicada correctamente")


# =====================================
# PROGRAMA PRINCIPAL
# =====================================

def main():

    print("--------------------------------")
    print("ACTUALIZADOR ACESTREAM")
    print("--------------------------------")

    contenido, canales_actuales = leer_canales()

    canales_anteriores = leer_historial()

    if not canales_anteriores:

        print("Primera ejecución: creando referencia inicial")

        nuevos = []
        eliminados = []
        modificados = []

    else:

        nuevos, eliminados, modificados = comparar(
            canales_anteriores,
            canales_actuales
        )

    print("Canales actuales:", len(canales_actuales))
    print("Canales nuevos:", len(nuevos))
    print("Canales eliminados:", len(eliminados))
    print("Canales modificados:", len(modificados))

    generar_informe(
        nuevos,
        eliminados,
        modificados
    )

    guardar_historial(canales_actuales)

    publicar(contenido)

    print("--------------------------------")
    print("ACTUALIZACIÓN COMPLETADA")
    print("--------------------------------")


if __name__ == "__main__":
    main()
