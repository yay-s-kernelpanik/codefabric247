# Prompt para que una IA prepare Fabrica247 en GitHub

Usá este prompt en un agente de programación que tenga acceso autorizado de escritura al repositorio GitHub. Antes, creá un repositorio separado llamado `Fabrica247` (preferentemente privado al principio) o seleccioná el repositorio Fabrica247 ya existente. **No uses el repositorio del producto que los Workers van a desarrollar como repositorio del coordinador.**

Adjuntá el ZIP de Fabrica247 que te entregaron o asegurate de que el código v3.0 esté ya en el repositorio. Después pegá:

---

Actuá como ingeniero de software responsable de integrar y mantener este repositorio **Fabrica247**, una plataforma distribuida Hub + Workers para coordinar agentes de programación en varias computadoras.

## Objetivo

Dejá este repositorio listo para que el dueño y colaboradores puedan instalar, entender, probar y mantener Fabrica247. Conservá el núcleo funcional existente y trabajá en una rama nueva; no hagas push directo a `main` ni publiques una versión automáticamente.

## Arquitectura que debés respetar

- Hub: servidor central, dashboard, cola de tareas, prioridades, prompts, invitaciones, autenticación y almacenamiento de patches.
- Worker: cliente instalado en cada PC; se conecta hacia el Hub y ejecuta tareas en un clon local del repositorio objetivo.
- OpenCode: agente de programación ejecutado localmente en el Worker.
- Lite: proveedor online configurado localmente por el propietario.
- Heavy: Ollama local configurado por el propietario.
- GitHub: repositorio oficial del código objetivo. El Worker entrega patches al Hub; la integración/commit/push final requiere revisión humana.

## Restricciones obligatorias

1. Primero auditá los archivos reales, la estructura, el historial y las pruebas. No inventes funciones basándote solo en README.
2. No reemplaces un archivo entero sin comparar su versión actual.
3. No borres código funcional ni cambies el protocolo de Hub/Worker sin tests de compatibilidad.
4. No agregues acceso remoto al escritorio, consola remota arbitraria, lectura de archivos personales ni comandos ocultos.
5. El shell del agente debe seguir desactivado por defecto. No cambies permisos seguros para conseguir que un test pase.
6. Las claves API, tokens, contraseñas y archivos privados deben quedarse en la PC correspondiente. Nunca los escribas en logs, Git o el Hub.
7. Los Workers requieren consentimiento explícito del dueño para implementación y control administrativo remoto.
8. No hagas push ni merge directo a la rama principal. Prepará un Pull Request con resumen y pruebas.
9. No afirmes que Windows o macOS está probado si no corriste sus pruebas en ese sistema.
10. No instales software de terceros ni descargues modelos de forma silenciosa.

## Tareas

1. Inspeccioná `README.md`, `fabrica/`, `tests/`, instaladores y perfiles.
2. Verificá que las instrucciones de instalación coincidan exactamente con los comandos y archivos disponibles.
3. Mantené/actualizá los documentos siguientes si faltan: `docs/GUIA_COMPLETA.md`, `docs/NOOBS_WINDOWS_SIN_ADMIN.md`, `docs/CONFIGURAR_REPO_Y_CONTEXTO.md`, `CONTRIBUTING.md`, `AGENTS.md.example`.
4. Añadí links de navegación a esos documentos desde `README.md`.
5. Documentá claramente que cada Worker mantiene un clon separado y que el flujo actual entrega patches al Hub; no describas sincronización o push automático si no existe.
6. Documentá `AGENTS.md` como archivo de contexto persistente de OpenCode en el repositorio objetivo. Incluí cómo crearlo, completarlo, revisarlo y versionarlo, sin añadir secretos.
7. Revisá el flujo no-admin de Windows: Git Portable, Python por usuario, OpenCode CLI standalone y Ollama per-user para Heavy. No uses rutas que requieran `C:\Program Files` ni permisos de administrador.
8. Revisá `.gitignore` para asegurarte de excluir `.env`, `.worker.env`, `worker.json`, `worker.token`, bases de datos, logs, worktrees y secretos.
9. Ejecutá todas las pruebas automatizadas disponibles. En Linux: `python -m unittest discover -s tests -v`. Reportá exactamente el resultado.
10. Validá sintaxis de scripts Linux y al menos inspeccioná los scripts Windows. Si no hay Windows disponible, declaralo como no probado.
11. Añadí o mejorá pruebas para cada defecto real que encuentres.
12. No cambies funcionalidades por estética ni reescribas el frontend sin necesidad.

## Entregable

- Una rama con cambios completos.
- Un Pull Request listo para revisar.
- Resumen de archivos cambiados.
- Lista de pruebas ejecutadas, pruebas fallidas y plataformas no probadas.
- Pasos exactos para instalar el Hub y registrar un primer Worker Windows Lite/Heavy.
- Lista explícita de limitaciones que siguen pendientes.

Si necesitás una decisión que afecte seguridad, privacidad, compatibilidad o datos existentes, no la inventes: dejá la alternativa más segura y documentá la decisión pendiente.

---

## Si la IA tiene que crear el repositorio desde cero

Primero pedile que cree un repositorio nuevo `Fabrica247` con rama principal `main` y visibilidad privada. Luego adjuntale el ZIP y el prompt anterior. Si la herramienta no puede crear repositorios nuevos, crealo manualmente desde GitHub con **New repository** y volvé a ejecutar el prompt dentro del repositorio vacío.
