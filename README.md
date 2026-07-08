# Configuración

## 1. Crear la aplicación y el bot

1. Entra a https://discord.com/developers/applications
2. New Application > ponle nombre
3. Pestaña Bot > Add Bot
4. Copia el Token (lo usarás más adelante)

## 2. Activar los Intents

En la pestaña Bot, en Privileged Gateway Intents, activa:

- Server Members Intent
- Message Content Intent

## 3. Crear y activar entorno virtual

**Linux / macOS:**
```bash
python3 -m venv cp
source cp/bin/activate
```

**Windows:**
```bash
python -m venv cp
cp\Scripts\activate
```

## 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 5. Ejecutar el bot

```bash
python3 cp.py
```

Cuando lo pida, pega el token del paso 1.
