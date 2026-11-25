# Flujo de trabajo continuo con Fabrica247

## Integración automática por tarea

Cada Worker ejecuta su IA en un worktree aislado y envía un patch al Hub. El Worker no necesita credenciales Git remotas. El Hub ejecuta una única cola de integración serializada: aplica el patch sobre la última versión de `origin/HUB_BASE_BRANCH`, crea un commit y publica una rama `fabrica/task-ID`.

Activación en el equipo Hub (archivo `.env`):

```dotenv
TARGET_REPO=/ruta/al/clon-del-repositorio
HUB_AUTO_PUSH=true
HUB_BASE_BRANCH=main
```

El usuario local del Hub necesita acceso Git de lectura y escritura a `origin`. Configurá el gestor de credenciales Git local en esa PC. No copies tokens ni claves SSH a los Workers, ni los guardes en el proyecto.

Reiniciá el Hub tras modificar `.env`. El panel muestra los estados `QUEUED`, `INTEGRATING`, `PUSHED`, `CONFLICT` y `FAILED`. Si una integración falla, el patch queda guardado y se puede reintentar desde el dashboard.

## Aislamiento y conflictos

- Cada Worker tiene su propio worktree y no modifica directamente la copia central del Hub.
- El integrador único serializa los cambios y obtiene el último commit de la rama base antes de aplicar cada patch.
- Las tareas pueden avanzar en paralelo; los push se ejecutan de a uno.
- Si el patch no aplica, se sale de `allowed_files` o intenta incluir archivos de entorno privados, se rechaza y se conserva para revisión.
- Las ramas de tareas aún no incorporadas reservan sus rutas modificadas; otra tarea que intente tocar esos mismos archivos o rutas padre/hijo queda bloqueada como conflicto.
- Los fallos transitorios de Git y red se reintentan con espera incremental hasta 8 veces; luego quedan como `FAILED` para intervención.
- No se modifica la rama base, no se usa force-push y no se descartan cambios locales.
- Una rama por tarea sirve para abrir Pull Requests separados. El Hub no fusiona automáticamente a `main`.

## Operación 24/7

1. Mantener el Hub activo en una PC con conexión estable y el repositorio central clonado.
2. Mantener los Workers conectados por VPN privada.
3. Definir tareas pequeñas con rutas permitidas, entregables y criterios de aceptación.
4. Comprobar el estado del agente y la integración en el dashboard.
5. Revisar los resultados del CI y agrupar cambios compatibles mediante Pull Requests.
6. Mantener copias de seguridad del directorio `hub/` y del repositorio central.

## Recuperación

Si el Hub reinicia mientras una tarea está en integración, recupera su estado y vuelve a procesar el patch. Si el commit ya existe localmente pero el push falló, intenta publicar ese mismo commit; si la rama ya se publicó, detecta el marcador de tarea y evita crear un segundo commit. Si surge un conflicto, el patch original sigue disponible.

## Dueños de Workers

Cada amigo mantiene su propia configuración, API key y token de Worker. Debe autorizar localmente la edición del repositorio y puede detener el Worker en cualquier momento. Un worktree no es un sandbox: el agente trabaja con los permisos del usuario local. La integración remota administra cambios Git del proyecto, no el sistema operativo de las otras PCs.
