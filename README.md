# Configuración del Bot de Discord

## 1. Crear la aplicación y el bot

1. Entra a https://discord.com/developers/applications
2. New Application > ponle nombre
3. Pestaña Bot > Add Bot
4. Copia el Token (lo usarás más adelante)

## 2. Activar los Intents

En la pestaña Bot, en Privileged Gateway Intents, activa:

- Server Members Intent
- Message Content Intent

## 3. Invitar el bot al servidor

1. Pestaña OAuth2 > URL Generator
2. Scopes: `bot`
3. Selecciona los permisos necesarios
4. Abre la URL generada y elige el servidor

## 4. Clonar el repositorio

```bash
git clone <URL-de-este-repositorio>
cd <nombre-de-la-carpeta>
```

## 5. Crear y activar entorno virtual

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

## 6. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 7. Ejecutar el bot

```bash
python cp.py
```

Cuando lo pida, pega el token del paso 1.
