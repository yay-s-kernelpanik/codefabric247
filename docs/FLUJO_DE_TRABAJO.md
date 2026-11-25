# Flujo de trabajo diario con Fabrica247

## Administrador

1. Inicia el Hub y entra al dashboard.
2. Comprueba que las PCs estén online.
3. Crea tareas pequeñas con criterios de aceptación y límites.
4. Revisa prioridad y qué Workers pueden recibir la tarea.
5. Espera el patch.
6. Descarga cada patch, comprueba `git apply --check`, lo revisa y corre tests.
7. Integra en una rama, hace commit/push y abre Pull Request.
8. Cuando se mergea, avisa a los Workers que actualicen su clon (`git pull --ff-only`) con el Worker detenido.

## Dueño de un Worker

1. Comprueba que la VPN y el Hub estén accesibles.
2. Actualiza el clon del proyecto si el administrador anunció un merge.
3. Comprueba Git, OpenCode y el proveedor local/online.
4. Inicia `worker doctor` para revisar la conexión.
5. Inicia `worker run`.
6. Puede pausar o detener localmente con `Ctrl+C`.
7. Informa al administrador de problemas del equipo o de recursos.

## Ejemplo de división de tareas

| Worker | Tarea posible | Riesgo de conflicto |
|---|---|---|
| A | Documentar `docs/` | Bajo si otros no editan esos documentos |
| B | Agregar tests de `src/parser/` | Bajo si trabaja en tests separados |
| C | Revisar rendimiento de `src/render/` (solo lectura) | Bajo |
| D | Refactorizar `src/parser/` | Alto si otro Worker también edita parser |

Antes de asignar tareas a varios equipos, verificá que no estén tocando los mismos archivos.
