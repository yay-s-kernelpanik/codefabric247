# Releases y paquetes

Los paquetes oficiales se publican en la sección Releases del repositorio:
https://github.com/yay-s-kernelpanik/codefabric247/releases

Cada versión ofrece cuatro ZIP independientes:

| Archivo | Sistema | Perfil |
|---|---|---|
| Fabrica247-vX.Y.Z-Windows-Lite.zip | Windows | windows-lite |
| Fabrica247-vX.Y.Z-Windows-Heavy.zip | Windows | windows-heavy |
| Fabrica247-vX.Y.Z-Linux-Lite.zip | Linux | linux-lite |
| Fabrica247-vX.Y.Z-Linux-Heavy.zip | Linux | linux-heavy |

Cada ZIP contiene el núcleo común, sus documentos, el instalador de esa edición y solamente su perfil. No contiene perfiles de otras ediciones, cachés de Python, secretos, bases de datos ni carpetas de desarrollo.

## Construcción local

Desde la carpeta Fabrica247:

    python build_release.py --edition linux-lite --version 3.0.1

Ediciones válidas: windows-lite, windows-heavy, linux-lite, linux-heavy.

## Publicación

- .github/workflows/ci.yml ejecuta tests y compilación en Windows y Linux.
- .github/workflows/release.yml se activa al publicar un tag vX.Y.Z.
- La publicación espera a que los tests de Windows y Linux pasen.
- El workflow crea los cuatro ZIP, genera SHA256SUMS.txt y publica los archivos en GitHub Releases.

No se debe crear un release estable manualmente si el workflow no terminó correctamente.
