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

    # 9. Registrar cambios solo de Elcano.
    registrar_cambios(
        automaticos
    )

    # 10. Publicar la lista final en git.gay.
    publicar_git_gay(
        final
    )

    # 11. Resumen final.
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

    print("---------------------------------------")
    print("ACTUALIZACIÓN TERMINADA")
    print("=" * 55)


if __name__ == "__main__":

    main()
