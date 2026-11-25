# Fabrica247 para principiantes: Windows sin administrador

Esta guía está pensada para alguien que nunca usó Git, Python, una terminal ni agentes de programación. Leé los pasos en orden. **No ejecutes los instaladores como administrador**: Fabrica247 está diseñada para configurarse dentro de tu usuario.

## 0. Primero: ¿qué vas a hacer?

Hay dos maneras de participar:

- **Prestar capacidad de tu PC:** instalás un Worker y el administrador te asigna tareas del proyecto que aceptaste compartir. No necesitás convertirte en programador ni tocar GitHub a diario.
- **Contribuir al código de Fabrica247:** además de probarlo, modificás el repositorio de Fabrica247 y enviás tus cambios mediante un Pull Request.

Son dos repositorios distintos:

1. **Fabrica247:** el programa que organiza los agentes.
2. **Proyecto objetivo:** el código que los agentes van a trabajar. En el ejemplo de esta documentación, puede ser `https://github.com/yay-s-kernelpanik/VIctory-CachyOS.git`; verificá que sea el repositorio correcto antes de usarlo.

Cada computadora tiene su propia copia local del proyecto objetivo. No compartas una misma carpeta de Windows por red para que varias PCs trabajen sobre ella.

## 1. Preparar una carpeta de trabajo

1. Abrí el Explorador de archivos.
2. Entrá en `Documentos`.
3. Creá una carpeta llamada `Fabrica247`.
4. Descargá el ZIP de Fabrica247 desde el repositorio oficial o desde el archivo que te compartió el administrador.
5. Hacé clic derecho en el ZIP y elegí **Extraer todo**.
6. Guardá el contenido dentro de `Documentos\Fabrica247`.

No ejecutes ningún archivo todavía. Primero instalá las herramientas necesarias.

## 2. Descargar Git sin permisos de administrador

Git permite descargar una copia del proyecto, revisar cambios y crear ramas. En una PC sin permisos de administrador usá la versión **Portable** oficial.

1. Abrí <https://git-scm.com/install/win>.
2. Buscá la sección **Portable ("thumbdrive edition")**.
3. Descargá la versión que coincida con tu Windows (normalmente x64; ARM64 solo si tu equipo es ARM).
4. Ejecutá el archivo descargado. Cuando pregunte dónde extraerlo, elegí:

   `%LOCALAPPDATA%\Programs\PortableGit`

   No elijas `C:\Program Files`, porque esa carpeta puede requerir administrador.
5. Esperá a que termine la extracción.
6. Abrí **PowerShell**: pulsá Inicio, escribí `PowerShell` y abrilo normalmente.
7. Pegá este comando para que Git funcione en esta ventana:

   ```powershell
   $env:Path = "$env:LOCALAPPDATA\Programs\PortableGit\cmd;$env:Path"
   git --version
   ```

8. Si aparece `git version ...`, está listo.

### Hacer que Git quede disponible en futuras terminales

Este paso cambia el PATH de **tu usuario**, no el del equipo completo. No necesita administrador.

```powershell
$gitDir = Join-Path $env:LOCALAPPDATA 'Programs\PortableGit\cmd'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { $_ })
if ($parts -notcontains $gitDir) {
  $newPath = (@($parts + $gitDir) -join ';')
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
}
```

Cerrá PowerShell y abrilo de nuevo. Probá `git --version`. Si no aparece, repetí el comando temporal del paso anterior en esa ventana.

**Descargas oficiales:** <https://git-scm.com/install/win>. La edición Portable está diseñada para ejecutarse sin instalar Git para todos los usuarios ni escribir entradas permanentes en el registro. Si la PC de tu escuela/empresa bloquea incluso programas portables, no intentes saltarte esa política: pedí autorización al responsable del equipo.

## 3. Configurar el nombre de tus commits

Solo hace falta una vez por usuario. Usá tu nombre de colaborador y un correo asociado a GitHub. Si tenés activada la privacidad de correo en GitHub, podés usar la dirección `noreply` que GitHub muestra en tus ajustes.

```powershell
git config --global user.name "Tu nombre o alias"
git config --global user.email "tu-correo-de-github"
git config --global init.defaultBranch main
```

Comprobá:

```powershell
git config --global --list
```

No pegues contraseñas ni tokens en estos comandos.

## 4. Instalar Python para tu usuario

Fabrica247 necesita Python 3.9 o superior. No necesita instalar paquetes con `pip` porque el núcleo utiliza la biblioteca estándar de Python.

1. Abrí <https://www.python.org/downloads/windows/>.
2. Descargá el instalador de Windows que corresponda a tu equipo.
3. Ejecutalo normalmente.
4. Si aparece la opción, elegí instalar para **Just for me / Solo para mí**. No elijas instalar para todos los usuarios ni una carpeta del sistema.
5. Activá **Add Python to PATH** si el instalador ofrece esa opción.
6. Terminá la instalación.
7. Cerrá y volvé a abrir PowerShell.
8. Ejecutá:

   ```powershell
   py -3 --version
   python --version
   ```

Si `py -3 --version` muestra Python 3.9 o superior, sirve. Si Windows no permite instalar Python ni siquiera para tu usuario, necesitás que el administrador del equipo lo autorice.

## 5. Instalar OpenCode CLI para tu usuario

OpenCode es el agente que lee y modifica el código. Fabrica247 lo ejecuta en cada Worker.

1. Abrí la documentación oficial: <https://opencode.ai/docs/>.
2. Buscá la sección **Download a standalone CLI binary** y elegí **Windows x64** (o ARM64 si tu equipo usa ARM).
3. Descargá el binario oficial.
4. Creá esta carpeta si no existe:

   `%LOCALAPPDATA%\Programs\OpenCode`

5. Extraé o copiá el ejecutable allí y asegurate de que se llame `opencode.exe`.
6. Añadí esa carpeta al PATH de tu usuario desde **Configuración de Windows → Sistema → Información → Configuración avanzada del sistema → Variables de entorno**. Editá únicamente la variable `Path` de la parte superior (**Variables de usuario**), no la sección de variables del sistema. Si esa pantalla está bloqueada, pedí ayuda al responsable del equipo.
7. Cerrá y volvé a abrir PowerShell.
8. Probá:

   ```powershell
   opencode --version
   ```

Si no reconoce el comando, ejecutalo mediante la ruta completa para comprobar que el binario se descargó correctamente.

## 6. Solo para Windows Heavy: instalar Ollama y un modelo

Ollama ejecuta un modelo local. Esta parte puede ocupar varios GB y consumir bastante RAM/CPU/GPU. Si la PC es modesta o no tiene espacio libre, elegí **Lite** en vez de Heavy.

1. Abrí <https://ollama.com/download/windows>.
2. Descargá el instalador oficial.
3. La documentación de Ollama indica que el instalador de Windows se instala en el directorio del usuario y no requiere administrador. Si el equipo aplica restricciones propias, respetalas.
4. Instalá Ollama y dejalo iniciado.
5. Abrí PowerShell y comprobá:

   ```powershell
   ollama --version
   ```

6. Descargá un modelo que el administrador del proyecto haya aprobado. Como ejemplo pequeño de la configuración de Fabrica247 aparece `qwen2.5-coder:3b`:

   ```powershell
   ollama pull qwen2.5-coder:3b
   ollama list
   ```

No descargues un modelo enorme sin comprobar antes espacio disponible y memoria. Heavy no significa automáticamente más rápido: depende del hardware.

## 7. Comprobar todas las herramientas

Abrí una PowerShell nueva y ejecutá:

```powershell
git --version
py -3 --version
opencode --version
ollama --version
ollama list
```

Para **Lite**, no necesitás Ollama ni descargar un modelo local. Sí necesitás OpenCode y un proveedor/API online configurado por el dueño de la cuenta.

## 8. Registrar esta PC como Worker

Antes de empezar, pedile al administrador:

- La dirección del Hub (URL de VPN privada o HTTPS).
- Una invitación individual de un solo uso.
- El `slug` exacto del proyecto.
- La URL Git del proyecto, si todavía no tenés una copia local.
- Qué permisos espera que aceptes.

Abrí la carpeta donde extrajiste Fabrica247 y hacé doble clic en:

- `install-windows-heavy.bat` para Heavy.
- `install-windows-lite.bat` para Lite.
- `install.bat` para que el asistente te pregunte qué edición preferís.

El asistente pregunta por Hub, invitación, nombre de PC, slug y repositorio. Si no tenés el repositorio descargado, dejá vacía la ruta local cuando la pregunte y después proporcioná la URL Git cuando la solicite.

El asistente pregunta dos permisos separados:

- **Aceptar tareas que modifiquen código:** elegí Sí solo si el dueño de esta PC acepta que el agente escriba cambios dentro del repositorio configurado.
- **Permitir control remoto administrativo:** elegí Sí solo si aceptás que el administrador pueda pausar/reanudar el Worker, actualizar instrucciones y solicitar cancelar una tarea en ejecución.

La ejecución de shell continúa desactivada por defecto. No habilites permisos que no entendés. Podés colaborar sin aceptar control administrativo remoto.

## 9. Comprobar la conexión y arrancar

En PowerShell, desde la carpeta `Fabrica247`:

```powershell
py -3 -m fabrica worker doctor
```

El diagnóstico debe mostrar OpenCode, el repositorio y la conexión con Hub como correctos. Para iniciar el Worker:

```powershell
py -3 -m fabrica worker run
```

Dejá esa ventana abierta mientras aportás capacidad. Para detener el Worker localmente, volvé a esa ventana y pulsá `Ctrl+C`. Eso no desinstala nada.

## 10. Qué hace el agente con tu PC

El Worker usa el repositorio local que indicaste. Para cada tarea crea una rama/worktree Git separado, ejecuta el agente, prepara un patch y lo manda al Hub.

El Hub **no recibe tu carpeta completa** ni puede controlar tu escritorio. Tampoco puede ejecutar comandos arbitrarios de administrador. Aun así, el agente corre como tu usuario de Windows: no compartas una carpeta que contenga archivos personales o proyectos que no quieras exponer al agente.

No compartas con nadie estos archivos:

- `%APPDATA%\Fabrica247\worker.token`
- `%APPDATA%\Fabrica247\.worker.env`
- Tu contraseña del Hub.
- Contraseñas, API keys, cookies o tokens de GitHub.

## 11. Errores frecuentes

**`No se encontró Git`:** cerrá y reabrí PowerShell después de configurar el PATH. Probá el comando temporal de la sección 2.

**`No se encontró Python`:** comprobá `py -3 --version`; reinstalá Python para tu usuario si hace falta.

**`No se encontró opencode`:** comprobá el nombre `opencode.exe` y agregá la carpeta que lo contiene al PATH de usuario.

**`No se pudo conectar al Hub`:** comprobá que el Hub siga encendido, que la URL esté bien escrita y que la VPN esté conectada. No intentes sustituir la URL por una IP pública HTTP.

**`Invitación inválida o usada`:** pedí otra invitación. Las invitaciones son de un solo uso y pueden caducar.

**`No es un repositorio Git válido`:** elegí la carpeta raíz que contiene la carpeta oculta `.git`, no `src`, `docs` ni otra subcarpeta.

**Ollama no encuentra el modelo:** ejecutá `ollama list`, revisá el nombre exacto y descargalo con `ollama pull nombre-del-modelo`.

**La tarea no modifica nada:** puede que el Worker esté en modo de solo lectura. Revisá con el dueño si aprobaste `allow_remote_code` y si la tarea es de tipo implementación.

---

## Enlaces oficiales

- Git para Windows y Portable: <https://git-scm.com/install/win>
- Python para Windows: <https://www.python.org/downloads/windows/>
- Documentación OpenCode: <https://opencode.ai/docs/>
- Descarga Ollama Windows: <https://ollama.com/download/windows>
