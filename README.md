# ACE-AUTO

Automatización de la parte Elcano de una lista M3U.

## Archivos
- `actualizar.py`: descarga Elcano, filtra la mejor calidad disponible por canal y publica la lista final.
- `canales.m3u`: salida automática de Elcano. Se regenera en cada ejecución.
- `canales_manuales.m3u`: canales añadidos manualmente. No se sobrescribe.
- `historial.json`: referencia de la parte automática.
- `cambios.md`: registro de canales añadidos, eliminados y modificados.
- `.github/workflows/actualizar.yml`: ejecución manual, al cambiar canales manuales y cada 3 horas.

## Configuración
En GitHub > Settings > Secrets and variables > Actions, debe existir:
- `GIT_GAY_TOKEN`

El token no debe escribirse en archivos ni compartirse.

## Importante antes de la primera ejecución
Si ya tienes canales manuales dentro del `hashes.m3u` antiguo, cópialos a `canales_manuales.m3u` antes de ejecutar por primera vez. La publicación final se compone de la zona automática de Elcano y de ese archivo manual.

## EPG y reproducción
La cabecera M3U conserva las tres fuentes EPG de la lista que compartiste y `refresh=3600`.
Los enlaces AceStream se convierten a `http://127.0.0.1:6878/ace/getstream?id=...`.
`127.0.0.1` apunta al propio dispositivo: cada equipo que reproduzca debe tener AceStream Engine ejecutándose localmente en el puerto 6878.

La selección de calidad se basa en las etiquetas presentes en la fuente: 4K/2160p, 1080p/FHD, 720p/HD y SD. Para cada canal se conservan las fuentes que empatan en la mejor calidad detectada.
