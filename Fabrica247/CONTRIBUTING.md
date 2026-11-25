# Cómo aportar al repositorio Fabrica247

¡Gracias por ayudar! No necesitás conocer todo el sistema para aportar. Empezá con documentación, reportes de errores o pruebas pequeñas.

## Antes de editar

1. Leé `README.md`.
2. Buscá la guía que corresponda dentro de `docs/`.
3. Revisá `AGENTS.md` para conocer las reglas del repositorio.
4. No subas archivos locales, tokens, contraseñas, `.worker.env`, `worker.json`, `worker.token`, bases SQLite, worktrees ni logs.

## Preparar una copia

```bash
git clone https://github.com/OWNER/Fabrica247.git
cd Fabrica247
git switch -c docs/mi-aporte
```

Reemplazá `OWNER` por el dueño real del repositorio. Si no tenés permiso de escritura, creá un Fork en GitHub y cloná tu Fork.

## Hacer cambios

1. Cambiá solo los archivos relacionados con tu aporte.
2. Revisá los cambios:

   ```bash
   git status
   git diff
   ```

3. Ejecutá las pruebas disponibles:

   ```bash
   python -m unittest discover -s tests -v
   ```

4. Prepará el commit:

   ```bash
   git add README.md docs/ARCHIVO_QUE_CAMBIASTE.md
   git commit -m "docs: explica el flujo de Workers"
   ```

5. Subí tu rama:

   ```bash
   git push -u origin docs/mi-aporte
   ```

6. En GitHub, abrí un Pull Request hacia la rama principal. Describí qué cambiaste, por qué y qué pruebas corriste.

## Si no tenés Git instalado

En Windows sin permisos de administrador, seguí `docs/NOOBS_WINDOWS_SIN_ADMIN.md` y descargá la edición Portable oficial de Git.

## Reglas

- No hagas push directo a `main`.
- No agregues secretos ni archivos personales.
- No afirmes que un test pasó si no lo ejecutaste.
- No cambies los permisos de seguridad por defecto para hacer pasar un test.
- Un Pull Request pequeño y explicativo es más fácil de revisar.
