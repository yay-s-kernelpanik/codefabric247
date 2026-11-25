# Fabrica247: guía completa de uso y administración

Esta guía explica el sistema desde cero: qué es cada componente, cómo preparar el Hub, cómo conectar el repositorio que se va a desarrollar, cómo sumar computadoras, cómo escribir el contexto del proyecto, cómo crear tareas y cómo integrar los resultados sin pisar trabajo ajeno.

## 1. La idea en una frase

**El Hub organiza. Los Workers ejecutan. GitHub conserva el repositorio oficial.**

- **Hub:** servidor y panel web central. Guarda proyectos, tareas, prioridades, invitaciones, estado de Workers, instrucciones y patches.
- **Worker:** programa pequeño que corre en cada computadora colaboradora. Se conecta hacia el Hub, reclama tareas compatibles y ejecuta OpenCode en un repositorio local.
- **OpenCode:** agente de programación que interpreta la tarea y trabaja dentro de un worktree Git.
- **Proveedor de IA:** API online (Lite) u Ollama local (Heavy).
- **GitHub:** repositorio remoto oficial del proyecto. No es reemplazado por el Hub.

```text
                         PANEL DEL HUB
                  proyectos · tareas · prompts
                                |
                                v
                     HUB CENTRAL (Mother)
                     hub.sqlite3 + patches
                       ^       ^       ^
                       |       |       |
                  Worker A  Worker B  Worker C
                  Win Lite  Win Heavy  Linux Lite
                       |       |       |
                    OpenCode + repositorios locales
                       |       |       |
                       +-------+-------+
                               |
                               v
                      GitHub: repo oficial
                (el administrador revisa e integra)
```

Cada Worker usa su propio clon del proyecto. **Nunca configures dos computadoras para escribir a la misma carpeta de red.**

## 2. Repositorios: separar el coordinador del código objetivo

Mantené dos repositorios distintos:

1. `Fabrica247`: contiene el Hub, los Workers, instaladores, documentación y pruebas del coordinador.
2. `PROYECTO_OBJETIVO`: es el repositorio de software donde las computadoras van a trabajar.

En las conversaciones anteriores venías trabajando con `VIctory-CachyOS`. Si sigue siendo el proyecto objetivo, usá esta URL como ejemplo:

```text
https://github.com/yay-s-kernelpanik/VIctory-CachyOS.git
```

Verificá que el nombre y el acceso sean correctos antes de clonarlo. Si ahora querés desarrollar otro repositorio, reemplazá esa URL.

El Hub no necesita clonar el repositorio objetivo. Cada Worker sí necesita una copia local accesible por Git. El slug del proyecto en el Hub es una etiqueta corta, por ejemplo `victory-cachyos`; debe escribirse exactamente igual en cada Worker, pero no tiene por qué coincidir con el nombre del repositorio GitHub.

## 3. Preparación del Hub

Podés ejecutar el Hub en Linux Mother (recomendado si esa es tu PC principal) o en Windows. El Hub no necesita instalar OpenCode ni Ollama.

### Linux

1. Instalá Python 3.9+.
2. Extraé el repositorio Fabrica247.
3. Abrí una terminal dentro de la carpeta `Fabrica247`.
4. Ejecutá:

   ```bash
   bash install-hub.sh
   ```

   Esto inicializa la base de datos y la contraseña inicial. El script no inicia el servidor todavía.

5. Iniciá el Hub:

   ```bash
   python3 -m fabrica hub serve --host 127.0.0.1 --port 8765
   ```

6. Abrí `http://127.0.0.1:8765/` en el navegador de esa misma PC.
7. Consultá la ruta de la contraseña que mostró el instalador. En una instalación estándar suele ser `hub/admin_password.txt` dentro del directorio de datos de Fabrica247. No la compartas.

### Windows

1. Instalá Python 3.9+ para tu usuario.
2. Extraé Fabrica247.
3. Hacé doble clic en `install-hub.bat`.
4. Abrí PowerShell dentro de esa carpeta y ejecutá:

   ```powershell
   py -3 -m fabrica hub serve --host 127.0.0.1 --port 8765
   ```

5. Abrí `http://127.0.0.1:8765/`.

`127.0.0.1` sirve para probar el Hub desde la misma computadora. Para recibir conexiones de otras PCs por una VPN privada o LAN confiable, el Hub puede escuchar en `0.0.0.0`:

```bash
python3 -m fabrica hub serve --host 0.0.0.0 --port 8765
```

Eso no configura seguridad de red por sí solo. El puerto debe quedar accesible únicamente por una VPN privada o red confiable. El servidor integrado no termina TLS: **no publiques HTTP directamente en Internet**.

## 4. Crear el proyecto en el Hub

1. Iniciá sesión con la contraseña de administrador.
2. Abrí la sección de proyectos del dashboard.
3. Creá un proyecto nuevo.
4. Elegí un nombre comprensible, por ejemplo `Victory CachyOS`.
5. Elegí un slug estable y sin espacios, por ejemplo `victory-cachyos`.
6. Agregá una breve descripción y las instrucciones permanentes del proyecto.
7. Guardá.

El slug que elegiste es el identificador que se configura en todos los Workers.

## 5. Preparar el repositorio objetivo en GitHub

Antes de sumar Workers:

1. Revisá que el repositorio exista y que puedas acceder.
2. Elegí la rama base estable, normalmente `main`.
3. Asegurate de que el repositorio tenga un `README.md` que explique qué hace el proyecto.
4. Agregá y completá `AGENTS.md` en la raíz. La plantilla está en `AGENTS.md.example` dentro de este ZIP y también se explica en `CONFIGURAR_REPO_Y_CONTEXTO.md`.
5. Hacé commit y push del archivo de contexto.
6. Si el repo es privado, concedé a cada Worker solo el acceso que haga falta para clonar/actualizar. Fabrica247 no necesita ni debe recibir tu contraseña de GitHub.

## 6. Invitar a un Worker

Desde el dashboard del Hub:

1. Abrí la sección Workers/invitaciones.
2. Creá una invitación nueva.
3. Poné una etiqueta que identifique la computadora o persona.
4. Limitá la invitación a un uso y definí un vencimiento corto.
5. Copiá el código y enviáselo al dueño de esa PC por un canal privado.

Cada invitación es de un solo uso. Generá una diferente para cada PC. No compartas la contraseña de administrador ni el token de un Worker.

## 7. Registrar cada computadora

En cada PC:

1. Descargá y extraé el ZIP de Fabrica247.
2. Instalá Python, Git y OpenCode según el sistema.
3. Para Heavy, instalá Ollama y descargá el modelo aprobado.
4. Ejecutá el instalador de la edición adecuada.
5. Completá la dirección del Hub, la invitación, el nombre de la PC, el slug del proyecto y la ruta local del repo (o la URL Git para clonarlo).
6. Decidí conscientemente si aceptás cambios de código y control administrativo del Worker.
7. Ejecutá `worker doctor` y luego `worker run`.

La guía sin conocimientos previos para Windows está en `NOOBS_WINDOWS_SIN_ADMIN.md`.

### Ediciones

| Edición | Componentes | Caso de uso |
|---|---|---|
| Windows Lite | Worker + OpenCode + APIs online | PC sin GPU o sin espacio para modelo local |
| Windows Heavy | Worker + OpenCode + Ollama | PC con recursos para IA local |
| Linux Lite | Worker + OpenCode + APIs online | PC Linux con conexión a proveedor remoto |
| Linux Heavy | Worker + OpenCode + Ollama | PC Linux con modelo local |
| Linux Mother | Hub + dashboard + Worker opcional | PC principal que administra el proyecto |
| Hub | Solo Hub y dashboard | Servidor central sin agente local |

## 8. Conectar el repositorio objetivo a los Workers

Al registrar el Worker hay dos opciones:

- Si el repositorio ya está clonado, indicá la ruta de la carpeta raíz donde está `.git`.
- Si no está clonado, dejá vacía la ruta y luego indicá la URL Git. El asistente intentará clonarlo en el directorio de datos del Worker.

Cada Worker guarda su ruta local en `worker.json`, dentro de su carpeta de configuración. Por ejemplo en Windows:

```text
%APPDATA%\Fabrica247\worker.json
```

La sección `projects` se parece a esto:

```json
{
  "projects": {
    "victory-cachyos": {
      "path": "C:\\Users\\NOMBRE\\Fabrica247\\projects\\victory-cachyos",
      "enabled": true
    }
  }
}
```

En Linux la ruta será distinta, por ejemplo `/home/usuario/proyectos/VIctory-CachyOS`. No copies el `worker.json` de una PC a otra: cada Worker tiene su propia ruta, ID y token.

## 9. El archivo de contexto: AGENTS.md

`AGENTS.md` contiene las instrucciones persistentes para OpenCode: propósito del repo, arquitectura, comandos, límites, convención de nombres y cómo verificar cambios. Debe estar versionado en el **repositorio objetivo**, no solo en la carpeta de Fabrica247.

1. Copiá `AGENTS.md.example` a `AGENTS.md` en la raíz del repositorio objetivo.
2. Reemplazá todos los marcadores `[COMPLETAR]`.
3. Agregá comandos reales de test/build del proyecto.
4. Quitá reglas que no correspondan.
5. Hacé commit y push.

OpenCode descubre `AGENTS.md` del proyecto y lo usa como contexto persistente. También podés abrir OpenCode en la raíz del repo y ejecutar `/init` para que genere un primer borrador; revisalo antes de guardar. No pongas contraseñas, claves API, tokens, archivos personales ni datos privados en ese documento.

Además de `AGENTS.md`, Fabrica247 puede añadir prompts desde el dashboard:

1. Prompt local del Worker (solo en esa PC).
2. Prompt permanente del proyecto (Hub).
3. Prompt adicional por Worker (si ese dueño aceptó control remoto).
4. Prompt específico de la tarea.
5. Objetivo y límites de la tarea.

Estas instrucciones se complementan; no son una forma de saltarse los permisos locales del dueño.

## 10. Configurar el proveedor de IA

### Lite: proveedor online

Cada dueño configura su endpoint/modelo y guarda su API key en `.worker.env` en esa PC. Nunca mandes la API key al Hub ni la pongas en `worker.json`, `AGENTS.md` o GitHub.

`worker.json` define proveedor, modelo, endpoint y nombre de variable de entorno. `.worker.env` contiene el secreto. El perfil base de ejemplo es `worker.example.json`; `PROVIDERS.md` explica el formato OpenAI-compatible.

### Heavy: Ollama local

El propietario instala Ollama, descarga un modelo y deja el servicio local activo. El perfil Heavy usa inicialmente `http://127.0.0.1:11434/v1`. Confirmá que el nombre del modelo en `worker.json` coincide exactamente con el devuelto por `ollama list`.

Si Ollama no está levantado, el Worker Heavy no podrá ejecutar tareas aunque el Hub funcione.

## 11. Crear una tarea en el dashboard

1. Elegí el proyecto.
2. Escribí un objetivo específico y verificable.
3. Indicá el tipo de tarea (análisis/solo lectura o implementación).
4. Limitá archivos o directorios cuando corresponda.
5. Escribí el criterio de aceptación y comandos de prueba.
6. Asigná prioridad.
7. Guardá la tarea.

Ejemplo de objetivo claro:

```text
Revisá el manejo de configuración en src/config/.
Identificá errores de validación y agrega tests para los casos faltantes.
No cambies APIs públicas. Ejecutá los tests de esa carpeta y resumí los archivos modificados.
```

Ejemplo pobre:

```text
Arreglá todo el proyecto.
```

Separá tareas grandes en unidades pequeñas. Así es más fácil revisar resultados y evitar conflictos.

## 12. Cómo se devuelven e integran los cambios

Este punto es especialmente importante: **el Worker no hace push automático a la rama principal de GitHub**. Al terminar, devuelve un patch al Hub. El administrador lo descarga y decide si lo aplica.

Flujo recomendado:

1. Descargá el patch desde el dashboard.
2. En la PC de integración, entrá a un clon limpio y actualizado del repositorio objetivo.
3. Revisá primero el patch:

   ```powershell
   git status
   git apply --check .\Downloads\fabrica-task-123.patch
   ```

   En Linux/macOS:

   ```bash
   git status
   git apply --check ~/Downloads/fabrica-task-123.patch
   ```

4. Si el chequeo funciona, aplicalo:

   ```bash
   git apply .\Downloads\fabrica-task-123.patch
   ```

5. Revisá el diff:

   ```bash
   git diff --stat
   git diff
   ```

6. Ejecutá los tests y comprobaciones del proyecto.
7. Si está todo bien, creá una rama de integración, commit y push:

   ```bash
   git switch -c integrar/fabrica-task-123
   git add -A
   git commit -m "Integra tarea 123 de Fabrica247"
   git push -u origin integrar/fabrica-task-123
   ```

8. Abrí un Pull Request en GitHub hacia la rama principal. Revisá el cambio antes del merge.
9. Una vez integrada la tarea, actualizá los clones de los Workers antes de asignarles tareas nuevas:

   ```bash
   git pull --ff-only
   ```

Si el patch falla en `git apply --check`, no fuerces el cambio. Puede que la rama base haya avanzado o que otro patch haya cambiado las mismas líneas. Actualizá el clon, compará el diff y pedí regenerar o adaptar la tarea.

## 13. Trabajar con varias PCs sin pisarse

- Priorizá tareas independientes: documentación, tests diferentes, módulos distintos.
- Evitá que dos Workers editen simultáneamente las mismas funciones o archivos.
- Guardá en el dashboard qué tarea trabaja cada uno.
- Integrá y probá un patch antes de aplicar el siguiente cuando haya archivos compartidos.
- Después de aceptar cambios en GitHub, actualizá los clones locales con `git pull --ff-only`.
- No uses una carpeta sincronizada por OneDrive/Dropbox como repositorio de trabajo simultáneo.

La versión actual no realiza sincronización Git automática en todos los Workers después de cada merge. Esa actualización debe hacerse manualmente.

## 14. Control remoto y consentimiento

El administrador puede gestionar la cola, prompts, prioridades e invitaciones. En los Workers que aceptaron administración remota también puede:

- Pausar o reanudar la recepción de tareas.
- Añadir instrucciones adicionales al agente de esa PC.
- Solicitar cancelar la tarea activa.

La PC participante conserva un apagado local (`Ctrl+C`) y su configuración local. El dueño puede retirar el consentimiento desactivando `remote_control.enabled` en `worker.json`. La administración no equivale a escritorio remoto, acceso a documentos personales ni consola arbitraria del sistema.

## 15. Compartir el Hub fuera de casa

WhatsApp solo transporta la URL y la invitación: no crea una conexión de red segura. Para PCs fuera de tu casa usá una VPN privada o un proxy HTTPS bien configurado.

- No publiques el puerto HTTP 8765 directamente en Internet.
- No compartas la contraseña de administrador.
- Usá una invitación por computadora.
- Revocá un Worker que ya no participe.
- Conservá backups de la carpeta de datos del Hub.

## 16. Backups y mantenimiento

Antes de actualizar Fabrica247, guardá una copia de la carpeta de datos del Hub, especialmente su SQLite y secretos locales. No subas esa carpeta a GitHub.

En cada Worker protegé `worker.token`, `.worker.env` y `worker.json`. Si se sospecha que un token fue compartido, revocá el Worker desde el dashboard y registralo de nuevo con otra invitación.

## 17. Diagnóstico

En el Worker:

```powershell
py -3 -m fabrica worker doctor
```

En el Hub:

```powershell
py -3 -m fabrica hub serve --host 127.0.0.1 --port 8765
```

Si un agente no ejecuta:

- Comprobá que OpenCode responda a `opencode --version`.
- En Heavy, comprobá Ollama con `ollama list` y que el servicio esté activo.
- Comprobá conectividad a la URL del Hub.
- Revisá el slug configurado y que coincida con el proyecto.
- Comprobá que el Worker esté habilitado para ese proyecto.
- Comprobá que el propietario haya aceptado implementación si la tarea requiere editar.

## 18. Estado real y límites

La suite de tests automatizados incluida se ejecuta con:

```bash
python -m unittest discover -s tests -v
```

Los tests usan agentes simulados y un Hub local. No demuestran por sí solos compatibilidad con todas las APIs, todas las versiones de Windows, todas las GPUs ni una red de computadoras físicas. Antes de uso amplio, probá una PC Linux Mother y un Worker Windows Lite/Heavy, y validá el patch completo de principio a fin.
