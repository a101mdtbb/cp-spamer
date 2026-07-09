# CP SPAMER v2.0

Bot de Discord para spamear mensajes con un solo click.

## Requisitos

- Python 3.10 o superior
- Un token de bot de Discord

## Configuración

1. Crea una aplicación en https://discord.com/developers/applications
2. En la pestaña **Bot**:
   - Dale clic a **Add Bot**
   - Copia el token
   - En **Privileged Gateway Intents**, activa **Message Content Intent**
3. Invita el bot a tu servidor con el scope `applications.commands`

## Ejecución

```bash
bash cp.sh
```

O sin el venv incluido:

```bash
pip install -r requirements.txt
python3 cp.py
```

Cuando lo pida, pega el token. El token se guarda en `token.json`.

También puedes usar una variable de entorno (prioritaria):

```bash
export DISCORD_TOKEN=tu_token
python3 cp.py
```

## Uso

Usa el comando `/spam mensaje:<texto> veces:<1-10>` en Discord.

## Seguridad

- `token.json` está en `.gitignore` — no se sube al repositorio.
- El token también se puede pasar por variable de entorno `DISCORD_TOKEN`.
- El botón de spam tiene un cooldown de 10s por usuario.
