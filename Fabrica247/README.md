# Fabrica247 v3.0

## Empezá por la guía correcta

- **No sabés programar ni instalar Git en Windows:** [Guía para principiantes sin administrador](docs/NOOBS_WINDOWS_SIN_ADMIN.md).
- **Querés instalar, administrar y operar todo el sistema:** [Guía completa](docs/GUIA_COMPLETA.md).
- **Querés conectar el repositorio donde trabajarán las PCs y configurar contexto:** [Repositorio objetivo y AGENTS.md](docs/CONFIGURAR_REPO_Y_CONTEXTO.md).
- **Querés entender el ciclo diario de tareas y patches:** [Flujo de trabajo](docs/FLUJO_DE_TRABAJO.md).
- **Querés contribuir al propio Fabrica247:** [CONTRIBUTING.md](CONTRIBUTING.md).
- **Querés que una IA con acceso a GitHub prepare el repositorio:** [Prompt para IA de GitHub](docs/PROMPT_PARA_IA_GITHUB.md).
- **Plantilla de contexto para copiar al repo objetivo:** [AGENTS.md.example](AGENTS.md.example).

> Integración automática opcional: con `TARGET_REPO` y `HUB_AUTO_PUSH=true` en el Hub, cada patch validado se convierte en un commit y se sube a una rama exclusiva `fabrica/task-ID`. Nunca se hace push automático a `main` ni se fuerzan ramas.

**Fabrica247 es una plataforma distribuida para coordinar agentes de programación en varias computadoras.** Un Hub central administra proyectos, prioridades, cola de tareas e instrucciones. Cada computadora participante ejecuta su propio Worker, con sus propias APIs y/o IA local.

El Hub no necesita instalar OpenCode ni un modelo. Los Workers se conectan al Hub mediante conexiones salientes; no necesitan abrir puertos ni compartir una base SQLite.

## Ediciones

| Edición | Función |
|---|---|
| **Windows** | Asistente para elegir Worker liviano o pesado en Windows. |
| **Linux** | Asistente para elegir Worker liviano o pesado en Linux. |
| **Windows Lite** | Worker online: OpenCode + APIs/router; no instala IA local. |
| **Windows Heavy** | Worker con proveedor Ollama local; el propietario instala y elige el modelo. |
| **Linux Lite** | Worker online: OpenCode + APIs/router; no instala IA local. |
| **Linux Heavy** | Worker con proveedor Ollama local; el propietario instala y elige el modelo. |
| **Linux Mother** | Hub administrador y Worker local opcional para tu PC principal. Incluye panel, prioridades, prompts y gestión de Workers. |
| **Hub** | Solo servidor central y dashboard; no instala ni ejecuta agente local (Linux o Windows). |

Los perfiles están en `profiles/`. Las ediciones Lite y Heavy comparten el mismo núcleo; cambian el proveedor sugerido y los requisitos de cada PC.

## Instaladores simples

No hay que ejecutar como administrador. Abrí el instalador correspondiente:

| Sistema / edición | Instalador |
|---|---|
| Windows, asistente | `install.bat` o `install-windows.bat` |
| Windows Lite | `install-windows-lite.bat` |
| Windows Heavy | `install-windows-heavy.bat` |
| Windows Worker alias | `install-windows-worker.bat` |
| Hub en Windows | `install-hub.bat` |
| Linux, asistente | `install.sh` o `install-linux.sh` |
| Linux Lite | `install-linux-lite.sh` |
| Linux Heavy | `install-linux-heavy.sh` |
| PC principal Linux Mother | `install-linux-mother.sh` |
| Hub en Linux | `install-hub.sh` |

En Linux también podés ejecutar `bash install.sh` sin depender del bit ejecutable del archivo. Los lanzadores `.bat` y `.sh` abren un asistente de texto; no instalan software ocultamente ni piden elevación de privilegios.

### Requisitos

- Python 3.9 o superior.
- Git instalado para los Workers que procesen repositorios.
- OpenCode CLI instalado en cada Worker que vaya a ejecutar agentes.
- Para Heavy, Ollama instalado y el modelo descargado localmente.

Los instaladores de Fabrica247 configuran el proyecto y abren un asistente; no descargan ni ejecutan instaladores de terceros a escondidas. En equipos sin Python, Git, OpenCode u Ollama, el asistente indica qué falta. La instalación de esos requisitos puede necesitar una acción del propietario del equipo y depende de su sistema.
Para un amigo que aporta una PC, el flujo es: extraer el ZIP, abrir `install.bat` en Windows o ejecutar `bash install.sh` en Linux, ingresar la URL privada del Hub y su invitación individual, elegir el repositorio y confirmar explícitamente los permisos. El asistente pide la API key sin mostrarla y la guarda localmente. No compartas contraseñas del Hub, archivos `worker.token` ni `.worker.env` por WhatsApp.

Los instaladores de Fabrica247 **no instalan software de terceros, no descargan modelos y no piden permisos de administrador**. Esto evita instalar cosas sin que el propietario lo sepa. Si una PC no tiene Python o Git, el asistente indica qué falta; OpenCode y Ollama también se instalan por separado. Por eso no sería honesto prometer que el ZIP funciona en cualquier PC sin ningún requisito previo.

## Asistente de instalación

En Windows hacé doble clic en `install.bat`. En Linux ejecutá `bash install.sh`.

El asistente pregunta la URL del Hub, código de invitación, nombre de la PC, proyecto y ruta local del repositorio. También pregunta dos permisos independientes:

1. **Permitir implementación:** habilita que el agente proponga y genere cambios de código en el repositorio configurado. Por defecto está desactivado.
2. **Permitir control administrativo remoto:** habilita que el Hub pause/reanude ese Worker y edite sus instrucciones. Por defecto está desactivado.

La ejecución de shell del agente permanece desactivada. La opción de shell no es necesaria para conectar ni para las tareas de análisis.

Para registrar una PC por comandos, también están disponibles:

```bash
python -m fabrica worker join --hub https://TU-HUB --invite CODIGO --name PC \\
  --project slug-del-proyecto --repo /ruta/al/repo \\
  --allow-remote-code --accept-remote-control
```

En Windows podés usar `py -3 -m fabrica ...`.

## Mother: la PC administradora

En Linux, ejecutá `bash install-linux-mother.sh`. El asistente:

- Inicializa el Hub y la base central.
- Crea el proyecto principal.
- Guarda la contraseña del administrador en `hub/admin_password.txt`.
- Puede crear un Worker local vinculado al proyecto para que tu PC también aporte capacidad.
- Te deja elegir si el Worker local usa un endpoint online o un modelo Ollama que ya tengas instalado.

Después iniciá el servidor:

```bash
python -m fabrica hub serve --host 127.0.0.1 --port 8765
```

Abrí `http://127.0.0.1:8765/`. Para iniciar el Worker local, abrí otra terminal y ejecutá:

```bash
python -m fabrica worker doctor
python -m fabrica worker run
```

Los accesos directos `start-hub.bat` / `start-hub.sh` y `start-worker.bat` / `start-worker.sh` hacen estos pasos más cómodos. La configuración de prompts del dashboard permite ajustar instrucciones del proyecto, de cada Worker y de cada tarea sin editar archivos en las PCs remotas.

La PC Mother tiene el panel de administración: crear proyectos y tareas, editar prompts, cambiar prioridades, pausar/reanudar Workers que hayan aceptado el control, revocar equipos, descargar patches y consultar el estado de integración Git. No obtiene acceso secreto al escritorio ni a los archivos completos de las otras computadoras.

## Conectar amigos por WhatsApp

Podés mandar por WhatsApp **la URL privada del Hub y el código de invitación individual**. WhatsApp solo transporta el mensaje: no crea el túnel ni protege el puerto.

Recomendación: conecten el Hub y las PCs mediante una VPN privada, por ejemplo Tailscale. En Tailscale podés compartir únicamente la PC que aloja el Hub mediante un enlace de invitación; la otra persona tiene que aceptar el acceso. Luego mandale por WhatsApp la dirección privada del Hub (IP o nombre MagicDNS) y una invitación de Fabrica247 distinta para su Worker. El Worker se conecta hacia el Hub; la PC del amigo no necesita abrir un puerto entrante. Tratá los dos enlaces/códigos como secretos. Tailscale explica que compartir una máquina no expone toda la red y que las máquinas compartidas quedan en cuarentena por defecto; verificá también las reglas de acceso del puerto del Hub.

No publiques `http://tu-ip-publica:8765` directamente en Internet. El servidor integrado de Fabrica247 no incorpora TLS. Para conectarse desde fuera de la LAN, usá VPN privada o un proxy HTTPS bien configurado. Una invitación de Fabrica247 no reemplaza la seguridad de red.

## Dashboard y control de agentes

Desde el dashboard podés:

- Crear proyectos y ordenar la cola por prioridad.
- Ajustar la prioridad de cada Worker por proyecto.
- Invitar, revisar y revocar computadoras.
- Ver estado online/offline, sistema, CPU informada y modelo declarado.
- **Pausar/reanudar** un Worker que aceptó administración remota.
- **Solicitar detener una tarea en curso** y terminar el proceso del agente que la ejecuta; requiere consentimiento remoto del dueño de esa PC.
- Editar instrucciones permanentes de un proyecto.
- Editar instrucciones adicionales por Worker.
- Escribir instrucciones específicas para una tarea.
- Descargar el patch resultante para revisarlo antes de aplicarlo.

### Capas de instrucciones

El agente recibe estas capas, cuando están configuradas:

1. Prompt local del propietario (`agent.local_prompt` en `worker.json`).
2. Prompt permanente del proyecto (dashboard).
3. Prompt remoto por Worker (dashboard; requiere consentimiento remoto).
4. Prompt específico de la tarea (dashboard).
5. Objetivo y límites de la tarea.

El Hub no puede cambiar silenciosamente los permisos locales de código o shell. La PC participante conserva su configuración local. `remote_control.enabled` puede ponerse en `false` localmente para retirar el consentimiento de administración remota.

La pausa remota es cooperativa: evita que el Worker reclame nuevas tareas después de recibir la orden. Para detener una tarea en curso, el dashboard envía una solicitud y el Worker autorizado termina el árbol de procesos de ese agente y limpia su worktree. La solicitud tarda como máximo aproximadamente un intervalo de heartbeat en llegar. El dueño también puede detener todo el Worker localmente con Ctrl+C. Desactivar `remote_control.enabled` localmente retira el consentimiento y también descarta solicitudes de detención todavía no recibidas.

Esto es administración de agentes y tareas, no acceso remoto al escritorio ni una consola de comandos. El Hub no puede explorar archivos ajenos, abrir programas ni ejecutar comandos arbitrarios en la PC participante. El dueño conserva el control físico/local y decide por separado si autoriza cambios de código; shell permanece desactivado por defecto.

## Worker Lite: APIs online

Lite no requiere GPU ni descarga de un modelo. Utiliza OpenCode y un endpoint configurado por el propietario. La configuración se guarda en:

- `worker.json`: modelos, proveedores, rutas de repositorios y límites.
- `.worker.env`: claves API, solo en la PC del Worker.
- `worker.token`: token privado que autentica esa PC.

El asistente pregunta por el endpoint y el identificador real del modelo. Puede utilizarse un router OpenAI-compatible donde el propietario administre sus cuentas (por ejemplo, proxies o gateways configurados por él), pero Fabrica247 no afirma que un endpoint exista ni que tenga cuota gratuita. Los nombres de proveedor, rutas y modelos tienen que coincidir con la documentación del servicio.

**OpenCode:** Fabrica247 invoca el ejecutable `opencode` usando un archivo de configuración privado generado para cada tarea. El archivo usa el esquema V2 actual de OpenCode (`providers`, `package`, `settings.baseURL`, `permissions`). La autenticación nativa de una cuenta OpenCode no se convierte automáticamente en cualquier endpoint de proxy; para proveedores externos se debe configurar el adaptador y modelo que correspondan. No compartas archivos de autenticación personales.

## Worker Heavy: IA local

Heavy configura Ollama como proveedor OpenAI-compatible local, por defecto en `http://127.0.0.1:11434/v1`. El asistente pregunta qué modelo está instalado; `qwen2.5-coder:3b` aparece solo como ejemplo inicial.

El propietario instala Ollama, decide qué modelo descargar y ejecuta `ollama pull NOMBRE-DEL-MODELO`. La descarga puede ocupar varios GB y el rendimiento depende de CPU, RAM y GPU. Fabrica247 no descarga ni ejecuta modelos a escondidas.

También podés agregar un segundo proveedor online al arreglo `agent.providers` y cambiar `agent.model` localmente. Las claves permanecen en `.worker.env`.

## Proyectos, tareas y resultados

Cada PC debe tener un clon Git local del proyecto. El slug configurado en el Worker debe coincidir con el slug creado en el Hub, pero la ruta local puede ser diferente en cada computadora.

Un Worker crea un worktree Git separado, ejecuta su agente y devuelve un patch. Para activar commits y push automáticos, configurá en el Hub:

```dotenv
TARGET_REPO=/ruta/al/clon-del-repositorio
HUB_AUTO_PUSH=true
HUB_BASE_BRANCH=main
```

El Hub debe tener un clon Git con remoto `origin` autenticado para push. Cada tarea completada genera un commit y una rama `fabrica/task-ID`; la rama base nunca se modifica y no se usa force-push. Los cambios que chocan con otra rama de tarea pendiente quedan como `CONFLICT`; el integrador bloquea solapamientos de archivos hasta que la rama previa llegue a la base. Los errores temporales de Git/red se reintentan automáticamente con espera incremental (hasta 8 intentos); después quedan visibles para reintento manual. Cada push ejecuta los workflows CI del repositorio, pero no equivale a aprobar ni fusionar el cambio.

En modo manual, el administrador puede descargar el patch y aplicarlo así:

```bash
git apply fabrica-task-123.patch
```

No se hace merge automático a la rama principal ni se copia la carpeta entera del usuario al Hub.

## Seguridad y límites reales

- El Hub conserva una única cuenta administradora; todavía no hay cuentas individuales ni roles granulares por amigo.
- Los Workers usan tokens individuales revocables y conexiones salientes.
- Las claves API se guardan solo en la PC del Worker; no se envían al Hub.
- Un worktree Git **no es un sandbox**. El agente corre con los permisos del usuario local y puede acceder a archivos permitidos por el sistema operativo. Cada propietario debe entender qué repositorio comparte.
- Los prompts remotos solo llegan a Workers que aceptaron control remoto. El dueño puede desactivarlo localmente.
- El panel no ofrece escritorio remoto, transferencia arbitraria de archivos ni ejecución de comandos de administración en el sistema de los amigos. El control de Fabrica247 es control de la cola, prioridades, prompts, pausa cooperativa y revocación; no es acceso absoluto al sistema operativo.
- No uses cuentas o credenciales de terceros sin permiso. Revisá términos, cuotas y privacidad de cada proveedor/API.
- Los patches pueden contener código o información del proyecto. Protegé el Hub y sus backups.

## Supervisor local anterior

La modalidad de supervisor local de v1/v2 se mantiene:

```bash
./fabrica.sh init
./fabrica.sh doctor
./fabrica.sh add "Audita src/ y explica problemas" --type reasoning
./start.sh
```

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas usan un OpenCode simulado y un Hub local; no consumen APIs reales. La validación de los scripts `.bat`/PowerShell requiere ejecutarlos en Windows. Antes de producción hay que probar despliegue, reconexión y rendimiento en las PCs reales.


## Descargas oficiales

Los ZIP por edición y versión se publican en [GitHub Releases](https://github.com/yay-s-kernelpanik/codefabric247/releases). Elegí exactamente tu sistema y variante (Lite o Heavy). La guía de paquetes y publicación está en [docs/RELEASES.md](docs/RELEASES.md).
