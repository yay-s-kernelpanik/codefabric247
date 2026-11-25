# Conectar el repositorio de desarrollo y configurar el contexto

Esta guía sirve para conectar **el repositorio donde se programa** a Fabrica247 y enseñar a los agentes cómo trabajar en él.

## 1. Elegí el repositorio correcto

Fabrica247 y el proyecto objetivo son dos cosas distintas:

- Fabrica247 administra Workers y tareas.
- El proyecto objetivo es el repositorio que los Workers van a clonar y modificar.

Ejemplo que venías usando en conversaciones anteriores (confirmá que sigue siendo el elegido):

```text
https://github.com/yay-s-kernelpanik/VIctory-CachyOS.git
```

Si el proyecto cambió, usá la URL Git del repositorio actual.

## 2. Asegurá el acceso GitHub

### Repositorio público

El Worker puede clonarlo sin credenciales. Para hacer push de la rama de integración, el administrador necesita iniciar sesión en GitHub desde su propia PC.

### Repositorio privado

El dueño del repo debe dar a cada PC el acceso mínimo que necesite para clonar/actualizarlo. La credencial se administra localmente en esa PC. No pegues un Personal Access Token dentro de `worker.json`, `.worker.env`, el prompt del Hub o WhatsApp.

El Worker devuelve patches al Hub; no necesita permiso de escritura en GitHub para ese flujo. Es mejor que el dueño integre los patches desde su propia PC.

## 3. Clonar el repo en la PC Mother

En una carpeta de trabajo:

```bash
git clone https://github.com/USUARIO/REPO.git
git -C REPO status
```

Reemplazá `USUARIO/REPO` por la dirección real. Entrá a la carpeta del repo y comprobá que la rama base esté actualizada:

```bash
cd REPO
git status
git pull --ff-only
```

No ejecutes `git reset --hard` para solucionar un error si no entendés qué cambios locales perderías.

## 4. Configurar el proyecto en el dashboard

Creá un proyecto en el Hub y elegí un slug estable, por ejemplo `mi-proyecto`. Usá exactamente ese slug en todos los Workers.

El slug no es la URL GitHub. Es el nombre interno que conecta las tareas del Hub con una entrada local dentro del Worker.

## 5. Clonar o seleccionar el mismo repo en cada Worker

Cada computadora debe tener su propio clon. Al ejecutar el instalador Worker, indicá:

- Hub URL.
- Código de invitación individual.
- Nombre de la PC.
- Slug del proyecto (idéntico al del Hub).
- Ruta local del clon, o URL Git para que el asistente lo clone.

Ejemplo de configuración local en Windows:

```json
{
  "projects": {
    "mi-proyecto": {
      "path": "C:\\Users\\Ana\\Projects\\mi-proyecto",
      "enabled": true
    }
  }
}
```

Ejemplo en Linux:

```json
{
  "projects": {
    "mi-proyecto": {
      "path": "/home/ana/Projects/mi-proyecto",
      "enabled": true
    }
  }
}
```

El `worker.json` está en la carpeta de datos local de Fabrica247; no lo copies de un amigo ni lo subas a GitHub porque contiene el ID, URL y configuración privada del Worker.

## 6. Crear el archivo de contexto AGENTS.md

OpenCode lee `AGENTS.md` para recibir instrucciones permanentes del proyecto. La ubicación recomendada es la raíz del repositorio objetivo:

```text
mi-proyecto/
├── AGENTS.md
├── README.md
├── src/
├── tests/
└── ...
```

Pasos:

1. Abrí `AGENTS.md.example` de este paquete.
2. Copialo al repo objetivo y renombralo `AGENTS.md`.
3. Reemplazá los campos `[COMPLETAR]` con información real.
4. Enumerá los comandos que de verdad funcionan para compilar, probar y validar.
5. Documentá arquitectura, carpetas, reglas de compatibilidad y archivos generados.
6. Guardá y hacé commit/push del archivo para que todas las PCs reciban la misma guía.

También podés abrir OpenCode dentro del repo y ejecutar `/init` para generar un borrador. No aceptes el resultado sin leerlo: una IA puede equivocarse sobre la arquitectura o los comandos.

## 7. Plantilla de AGENTS.md

```markdown
# Instrucciones del proyecto

## Propósito
[COMPLETAR: qué hace el proyecto y para quién]

## Estado del proyecto
[COMPLETAR: rama estable, versión, funciones terminadas y pendientes]

## Arquitectura
[COMPLETAR: módulos principales y responsabilidades]

## Entorno y requisitos
[COMPLETAR: SO, lenguajes, versiones, dependencias]

## Comandos oficiales
- Instalar: [COMPLETAR]
- Ejecutar: [COMPLETAR]
- Tests: [COMPLETAR]
- Linter/formato: [COMPLETAR]
- Build: [COMPLETAR]

## Reglas de desarrollo
- Antes de cambiar código, inspeccionar la implementación y los tests existentes.
- Hacer el cambio mínimo que resuelva el objetivo.
- No inventar APIs, opciones, dependencias ni comandos.
- No borrar ni sobrescribir trabajo preexistente del usuario.
- No modificar archivos generados a mano; modificar su fuente y regenerar si corresponde.
- Mantener compatibilidad con las plataformas que el proyecto soporte.
- No agregar dependencias sin justificar por qué son necesarias.
- No introducir secretos, tokens, contraseñas o claves API al repositorio.

## Pruebas y aceptación
- Ejecutar las pruebas relevantes después de cada cambio.
- Agregar tests para errores corregidos y funcionalidad nueva.
- Informar exactamente qué tests se ejecutaron y cuáles no se pudieron ejecutar.
- No afirmar que algo funciona si solo se revisó el código sin ejecutarlo.

## Límites de los agentes
- Trabajar solo en el objetivo asignado y dentro del repositorio.
- No ejecutar comandos destructivos, borrar datos o cambiar configuraciones del equipo sin autorización explícita.
- No hacer push ni merge a la rama principal sin revisión humana.
- Presentar resumen, archivos modificados, pruebas y riesgos al terminar.
```

## 8. Cómo se combina el contexto

En una tarea de Fabrica247, OpenCode puede recibir:

1. `AGENTS.md`: reglas permanentes compartidas por el repositorio.
2. Prompt del proyecto en el dashboard: objetivo global y decisiones del proyecto.
3. Prompt por Worker: instrucciones para una computadora/agente determinado; solo se envía si ese dueño aceptó control remoto.
4. Prompt de tarea: requisitos de ese trabajo específico.
5. Objetivo de la tarea y límites de archivos/tipo.

No pongas API keys en ningún prompt. Los secretos de proveedores van únicamente al archivo `.worker.env` local de la PC que los usa.

## 9. Ciclo para mantener las PCs al día

La v3.0 usa clones independientes y no hace `git pull` automático en cada Worker tras integrar un patch. Después de que el administrador integre un cambio:

1. Detené el Worker con `Ctrl+C` en esa PC.
2. Abrí una terminal en el clon local del proyecto objetivo.
3. Ejecutá `git status` y asegurate de que no haya cambios locales pendientes.
4. Ejecutá `git pull --ff-only`.
5. Volvé a iniciar `py -3 -m fabrica worker run` (Windows) o `python3 -m fabrica worker run` (Linux).

No hagas `git pull` mientras un agente esté usando un worktree de ese clon.

## 10. Integrar un patch

Descargá el patch del dashboard y, desde un clon limpio/actualizado de integración, corré:

```bash
git apply --check /ruta/al/task-123.patch
git apply /ruta/al/task-123.patch
git diff --check
git diff --stat
git diff
```

Ejecutá los tests. Si todo pasa, creá una rama, commit y push; abrí un Pull Request. Si `git apply --check` falla, no fuerces el patch: puede estar basado en otra versión.

## 11. Reglas para evitar conflictos

- Un Worker por tarea activa sobre un conjunto de archivos, cuando sea posible.
- Separá tareas por módulo, documentación o tests.
- No repartas dos tareas que modifiquen el mismo archivo al mismo tiempo.
- Integrá un patch y actualizá clones antes de lanzar tareas que dependan de esos cambios.
- El merge final siempre necesita revisión humana.
