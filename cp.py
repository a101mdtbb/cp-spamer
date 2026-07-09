import json
import logging
import os
import sys
import time
from pathlib import Path

import discord
from colorama import Fore, Style, init
from discord import app_commands
from discord.ext import commands

init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cp-spamer")

TOKEN_FILE = Path("token.json")
DEFAULT_COUNT = 5
MAX_COUNT = 10
BUTTON_COOLDOWN = 10

# ──────────────────────────── Token management ────────────────────────────


def save_token(token: str) -> None:
    TOKEN_FILE.write_text(json.dumps({"TOKEN": token}))


def load_token() -> str | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text()).get("TOKEN")
    except (json.JSONDecodeError, KeyError):
        return None


def get_token_from_env() -> str | None:
    return os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN")


def prompt_token() -> str:
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(Fore.CYAN + Style.BRIGHT + "╔══════════════════════════════╗")
        print(Fore.CYAN + Style.BRIGHT + "║       CP SPAMER  v2.0        ║")
        print(Fore.CYAN + Style.BRIGHT + "╚══════════════════════════════╝")
        print()
        print("  1. Ingresar token nuevo")
        print("  2. Cargar token guardado")
        print("  3. Salir")
        print()

        choice = input(Fore.YELLOW + "  Opción (1-3): ").strip()

        if choice == "1":
            token = input(Fore.GREEN + "  Token: ").strip()
            if token:
                save_token(token)
                print(Fore.GREEN + "  ✓ Token guardado correctamente!")
                return token
            print(Fore.RED + "  ✗ Token vacío.")
        elif choice == "2":
            token = load_token()
            if token:
                print(Fore.GREEN + f"  ✓ Token cargado: {token[:20]}...")
                return token
            print(Fore.RED + "  ✗ No hay token guardado.")
        elif choice == "3":
            print(Fore.YELLOW + "  Adiós!")
            sys.exit(0)

        input(Fore.YELLOW + "\n  Presiona Enter para continuar...")

# ──────────────────────────────── Bot setup ────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.last_button_use: dict[int, float] = {}

# ──────────────────────────────── Spam view ────────────────────────────────


class SpamView(discord.ui.View):
    def __init__(self, message: str, count: int = DEFAULT_COUNT):
        super().__init__(timeout=300)
        self.message = message
        self.count = count

    @discord.ui.button(label="Spam", style=discord.ButtonStyle.red)
    async def spam_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        uid = interaction.user.id
        now = time.time()
        last = bot.last_button_use.get(uid, 0)
        remaining = BUTTON_COOLDOWN - (now - last)

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Espera {remaining:.0f}s antes de usar el botón de nuevo.",
                ephemeral=True,
            )
            return

        bot.last_button_use[uid] = now
        await interaction.response.defer(ephemeral=True)

        for _ in range(self.count):
            await interaction.followup.send(self.message)

# ──────────────────────────────── Commands ────────────────────────────────


@bot.tree.command(name="spam", description="Spamea un mensaje N veces")
@app_commands.describe(
    mensaje="El mensaje a repetir",
    veces="Número de repeticiones (1-10, por defecto 5)",
)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def spam(
    interaction: discord.Interaction,
    mensaje: str,
    veces: app_commands.Range[int, 1, MAX_COUNT] = DEFAULT_COUNT,
) -> None:
    view = SpamView(mensaje, veces)
    await interaction.response.send_message(
        f"📨 Presiona el botón para spamear {veces} veces",
        view=view,
        ephemeral=True,
    )


# ──────────────────────────────── Events ────────────────────────────────


@bot.event
async def on_ready() -> None:
    assert bot.user is not None
    log.info("Conectado como %s  (ID: %s)", bot.user, bot.user.id)
    activity = discord.Activity(type=discord.ActivityType.playing, name="/spam")
    await bot.change_presence(activity=activity)

    try:
        synced = await bot.tree.sync()
        log.info("Comandos sincronizados: %d", len(synced))
    except Exception as e:
        log.error("Error al sincronizar comandos: %s", e)


# ──────────────────────────────── Main ────────────────────────────────


def main() -> None:
    token = get_token_from_env() or prompt_token()
    if not token:
        log.error("No se pudo obtener un token.")
        sys.exit(1)

    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        log.error("Token inválido. Revisa tu token e intenta de nuevo.")
        sys.exit(2)
    except KeyboardInterrupt:
        log.info("Apagando...")


if __name__ == "__main__":
    main()
