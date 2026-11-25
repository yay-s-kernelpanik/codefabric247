# Proveedores y APIs

Fabrica247 separa el coordinador central del proveedor de IA. Cada Worker configura su propio proveedor, modelo y claves. El Hub nunca necesita las API keys.

## Requisitos de compatibilidad

El generador usa el formato OpenCode V2 documentado actualmente: `providers`, `package` y `settings.baseURL`, con `@opencode/ai/providers/openai-compatible`. Para cada API necesitás conocer, desde la documentación oficial del proveedor:

- La URL base exacta, normalmente terminada en `/v1`.
- El identificador exacto del modelo.
- Si requiere API key, y qué variable local la contendrá.
- Límites de solicitudes, contexto, concurrencia y condiciones de uso.

No inventes la URL ni el identificador del modelo. Un proxy que usa un protocolo distinto necesita un adaptador específico y no será compatible solo por añadirlo a `worker.json`.

## Configurar un proveedor

```json
{
  "id": "router",
  "name": "Mi router",
  "package": "@opencode/ai/providers/openai-compatible",
  "base_url": "https://SERVIDOR-REAL/v1",
  "api_key_env": "FABRICA_ROUTER_API_KEY",
  "models": {
    "ID-REAL-DEL-MODELO": {"name": "Nombre visible"}
  }
}
```

En `agent.model` se referencia como `router/ID-REAL-DEL-MODELO`.

En `.worker.env`:

```dotenv
FABRICA_ROUTER_API_KEY=PEGAR_LA_CLAVE_SOLO_EN_ESTA_PC
```

No agregues claves a `worker.json`, al repositorio Git ni al dashboard. El archivo `.worker.env` está excluido de `.gitignore`.

## Ollama local

```json
{
  "id": "ollama",
  "name": "Ollama local",
  "package": "@opencode/ai/providers/openai-compatible",
  "base_url": "http://127.0.0.1:11434/v1",
  "api_key_env": "",
  "models": {
    "qwen2.5-coder:3b": {"name": "Qwen 2.5 Coder 3B"}
  }
}
```

Luego usá `"model": "ollama/qwen2.5-coder:3b"`, siempre que ese sea el modelo descargado y servido por Ollama.

## OpenCode, gateways y proxies

OpenCode, Kiro Gateway, Freebuff u otros gateways pueden tener formas distintas de autenticación, endpoints, cuotas y protocolos. La edición Lite actual usa proveedores OpenAI-compatible configurados mediante URL base, ID de modelo y variable de API key. **No importa automáticamente sesiones OAuth ni cuentas iniciadas dentro de OpenCode**, y no incluye adaptadores específicos para Freebuff o Kiro. Esos servicios solo se pueden usar cuando su documentación confirma que exponen una API compatible o se incorpora el adaptador correspondiente.

No asumimos que un nombre comercial, una cuenta o un paquete estén disponibles, sean gratuitos o tengan una ruta API específica. Consultá la documentación del proveedor y usa únicamente tus cuentas autorizadas. No envíes credenciales personales al Hub ni a otros participantes.
