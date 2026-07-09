#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

try:
    import gi
except ImportError:
    _gi_paths = []
    for _p in ["/usr/lib/python3/dist-packages", "/usr/lib/python3.14/dist-packages",
               "/usr/lib/python3.13/dist-packages", "/usr/lib/python3.12/dist-packages",
               "/usr/lib/python3.11/dist-packages", "/usr/lib/python3.10/dist-packages"]:
        if os.path.isdir(_p):
            _gi_paths.append(_p)
    if _gi_paths:
        sys.path = _gi_paths + sys.path
    import gi

import discord
from discord import app_commands
from discord.ext import commands
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cp-gtk")

TOKEN_FILE = Path("token.json")
CONFIG_FILE = Path("config.json")

DEFAULT_COUNT = 5
MAX_COUNT = 10
BUTTON_COOLDOWN = 10

# ──────────────────────────── Token / Config helpers ────────────────────────────


def save_token(token: str) -> None:
    TOKEN_FILE.write_text(json.dumps({"TOKEN": token}))


def load_token() -> str | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text()).get("TOKEN")
    except (json.JSONDecodeError, KeyError):
        return None


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


# ──────────────────────────────── Spam view (shared) ────────────────────────────────


class SpamView(discord.ui.View):
    def __init__(
        self,
        message: str,
        count: int,
        cooldown_dict: dict[int, float],
        cooldown_seconds: int,
    ) -> None:
        super().__init__(timeout=300)
        self.message = message
        self.count = count
        self._cooldown_dict = cooldown_dict
        self._cooldown_seconds = cooldown_seconds

    @discord.ui.button(label="Spam", style=discord.ButtonStyle.red)
    async def spam_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        uid = interaction.user.id
        now = time.time()
        last = self._cooldown_dict.get(uid, 0)
        remaining = self._cooldown_seconds - (now - last)

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Espera {remaining:.0f}s antes de usar el botón de nuevo.",
                ephemeral=True,
            )
            return

        self._cooldown_dict[uid] = now
        await interaction.response.defer(ephemeral=True)

        for _ in range(self.count):
            await interaction.followup.send(self.message)


# ──────────────────────────────── Bot thread ────────────────────────────────


class BotRunner:
    def __init__(
        self,
        token: str,
        on_ready: callable,
        on_disconnect: callable,
        on_error: callable,
        default_count: int = 5,
        max_count: int = 10,
        cooldown: int = 10,
    ) -> None:
        self.token = token
        self.on_ready = on_ready
        self.on_disconnect = on_disconnect
        self.on_error = on_error
        self.default_count = default_count
        self.max_count = max_count
        self.cooldown = cooldown
        self.bot: commands.Bot | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot = bot
        bot.last_button_use: dict[int, float] = {}
        max_count = self.max_count
        cooldown = self.cooldown
        default_count = self.default_count

        @bot.tree.command(name="spam", description="Spamea un mensaje N veces")
        @app_commands.describe(
            mensaje="El mensaje a repetir",
            veces=f"Número de repeticiones (1-{max_count}, por defecto {default_count})",
        )
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        async def spam_cmd(
            interaction: discord.Interaction,
            mensaje: str,
            veces: app_commands.Range[int, 1, max_count] = default_count,
        ) -> None:
            view = SpamView(mensaje, veces, bot.last_button_use, cooldown)
            await interaction.response.send_message(
                f"📨 Presiona el botón para spamear {veces} veces",
                view=view,
                ephemeral=True,
            )

        @bot.event
        async def on_ready() -> None:
            assert bot.user is not None
            try:
                synced = await bot.tree.sync()
                log.info("Comandos sincronizados: %d", len(synced))
            except Exception as e:
                log.error("Error al sincronizar: %s", e)
            GLib.idle_add(self.on_ready, bot)

        @bot.event
        async def on_disconnect() -> None:
            GLib.idle_add(self.on_disconnect)

        try:
            bot.run(self.token, log_handler=None)
        except discord.LoginFailure:
            self._running = False
            GLib.idle_add(self.on_error, "Token inválido")
        except Exception as e:
            self._running = False
            GLib.idle_add(self.on_error, str(e).splitlines()[0] if str(e) else "Error desconocido")

    def stop(self) -> None:
        self._running = False
        bot = self.bot
        if bot and hasattr(bot, "loop") and bot.loop and bot.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
            except RuntimeError:
                pass


# ──────────────────────────────── Settings dialog ────────────────────────────────


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, config: dict) -> None:
        super().__init__(
            title="Configuración",
            transient_for=parent,
            flags=0,
        )
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_border_width(12)
        self.set_resizable(False)

        box = self.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8, margin=10)
        box.add(grid)

        grid.attach(Gtk.Label(label="Repeticiones por defecto:"), 0, 0, 1, 1)
        self.count_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        self.count_spin.set_value(config.get("default_count", DEFAULT_COUNT))
        grid.attach(self.count_spin, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Máximo permitido:"), 0, 1, 1, 1)
        self.max_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        self.max_spin.set_value(config.get("max_count", MAX_COUNT))
        grid.attach(self.max_spin, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="Cooldown del botón (s):"), 0, 2, 1, 1)
        self.cooldown_spin = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.cooldown_spin.set_value(config.get("cooldown", BUTTON_COOLDOWN))
        grid.attach(self.cooldown_spin, 1, 2, 1, 1)

        self.show_all()

    def get_values(self) -> dict:
        return {
            "default_count": int(self.count_spin.get_value()),
            "max_count": int(self.max_spin.get_value()),
            "cooldown": int(self.cooldown_spin.get_value()),
        }


# ──────────────────────────────── Main window ────────────────────────────────


class SpamApp(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="CP SPAMER v2.0")
        self.set_default_size(520, 520)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self._on_destroy)

        self.config = load_config()
        self.bot_runner: BotRunner | None = None
        self.token_visible = False

        self._build_ui()
        self._load_token_into_entry()

    # ── UI builder ──

    def _build_ui(self) -> None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(vbox)

        # header
        header = Gtk.Label()
        header.set_markup('<span size="xx-large" weight="bold">CP SPAMER</span>')
        vbox.pack_start(header, False, False, 0)

        # ── Token section ──
        token_frame = Gtk.Frame(label="Token")
        vbox.pack_start(token_frame, False, False, 0)

        token_grid = Gtk.Grid(column_spacing=6, row_spacing=6, margin=8)
        token_frame.add(token_grid)

        self.token_entry = Gtk.Entry()
        self.token_entry.set_placeholder_text("Pega el token de tu bot aquí...")
        self.token_entry.set_width_chars(40)
        self.token_entry.set_visibility(False)
        token_grid.attach(self.token_entry, 0, 0, 3, 1)

        self.toggle_btn = Gtk.Button(label="👁")
        self.toggle_btn.set_tooltip_text("Mostrar / ocultar token")
        self.toggle_btn.connect("clicked", self._on_toggle_token)
        token_grid.attach(self.toggle_btn, 3, 0, 1, 1)

        save_btn = Gtk.Button(label="💾 Guardar")
        save_btn.connect("clicked", lambda _: self._save_token())
        token_grid.attach(save_btn, 0, 1, 1, 1)

        load_btn = Gtk.Button(label="📂 Cargar")
        load_btn.connect("clicked", lambda _: self._load_token_into_entry())
        token_grid.attach(load_btn, 1, 1, 1, 1)

        clear_btn = Gtk.Button(label="🗑 Limpiar")
        clear_btn.connect("clicked", lambda _: self.token_entry.set_text(""))
        token_grid.attach(clear_btn, 2, 1, 1, 1)

        # ── Status section ──
        status_frame = Gtk.Frame(label="Estado")
        vbox.pack_start(status_frame, False, False, 0)

        status_grid = Gtk.Grid(column_spacing=8, row_spacing=4, margin=8)
        status_frame.add(status_grid)

        self.status_label = Gtk.Label()
        self.status_label.set_markup("⚪  Desconectado")
        status_grid.attach(self.status_label, 0, 0, 1, 1)

        self.connect_btn = Gtk.Button(label="🔌 Conectar")
        self.connect_btn.connect("clicked", self._on_connect_toggle)
        status_grid.attach(self.connect_btn, 1, 0, 1, 1)

        self.settings_btn = Gtk.Button(label="⚙")
        self.settings_btn.set_tooltip_text("Configuración")
        self.settings_btn.connect("clicked", self._on_settings)
        status_grid.attach(self.settings_btn, 2, 0, 1, 1)

        self.bot_info_label = Gtk.Label(label="Bot:  —")
        self.bot_info_label.set_ellipsize(Pango.EllipsizeMode.END)
        status_grid.attach(self.bot_info_label, 0, 1, 3, 1)

        # ── Quick spam section ──
        spam_frame = Gtk.Frame(label="Spam rápido (desde Discord)")
        vbox.pack_start(spam_frame, False, False, 0)

        spam_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin=8)
        spam_frame.add(spam_box)

        spam_box.pack_start(Gtk.Label(label="Comando:"), False, False, 0)

        cmd_label = Gtk.Label()
        cmd_label.set_markup('<span font_family="monospace" size="large">/spam mensaje:&lt;texto&gt; veces:&lt;1-10&gt;</span>')
        spam_box.pack_start(cmd_label, False, False, 0)

        # ── Log section ──
        log_frame = Gtk.Frame(label="Log")
        vbox.pack_start(log_frame, True, True, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_frame.add(scrolled)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_left_margin(6)
        self.log_view.set_right_margin(6)
        scrolled.add(self.log_view)

    # ── Token ──

    def _on_toggle_token(self, _btn: Gtk.Button) -> None:
        self.token_visible = not self.token_visible
        self.token_entry.set_visibility(self.token_visible)
        self.toggle_btn.set_label("👁" if not self.token_visible else "👁‍🗨")

    def _save_token(self) -> None:
        token = self.token_entry.get_text().strip()
        if token:
            save_token(token)
            self._log("Token guardado")

    def _load_token_into_entry(self) -> None:
        token = load_token()
        if token:
            self.token_entry.set_text(token)
            self._log("Token cargado")
        else:
            self._log("No hay token guardado")

    # ── Connection ──

    def _on_connect_toggle(self, _btn: Gtk.Button) -> None:
        if self.bot_runner and self.bot_runner.is_running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        token = self.token_entry.get_text().strip()
        if not token:
            self._log("Error: Token vacío")
            return

        self.bot_runner = BotRunner(
            token,
            on_ready=self._on_bot_ready,
            on_disconnect=self._on_bot_disconnect,
            on_error=self._on_bot_error,
            default_count=self.config.get("default_count", DEFAULT_COUNT),
            max_count=self.config.get("max_count", MAX_COUNT),
            cooldown=self.config.get("cooldown", BUTTON_COOLDOWN),
        )
        self.bot_runner.start()
        self._set_ui_connected(False)
        self._log("🟡 Conectando...")

    def _disconnect(self) -> None:
        if self.bot_runner:
            self._set_ui_connected(False, status_text="⏹ Desconectando...")
            self._log("⏹ Desconectando...")
            self.bot_runner.stop()

    # ── Bot callbacks (called from bot thread via GLib.idle_add) ──

    def _on_bot_ready(self, bot: commands.Bot) -> None:
        assert bot.user is not None
        self._set_ui_connected(True)
        self.bot_info_label.set_text(f"Bot:  {bot.user}  (ID: {bot.user.id})")
        self._log(f"🟢 Conectado como {bot.user}")

    def _on_bot_disconnect(self) -> None:
        self._set_ui_connected(False)
        self.bot_info_label.set_text("Bot:  —")
        self._log("⚪ Desconectado")

    def _on_bot_error(self, error: str) -> None:
        self._set_ui_connected(False)
        self._log(f"🔴 Error: {error}")

    # ── UI helpers ──

    def _set_ui_connected(self, connected: bool, status_text: str | None = None) -> None:
        if status_text:
            self.status_label.set_markup(status_text)
        elif connected:
            self.status_label.set_markup("🟢  Conectado")
        else:
            self.status_label.set_markup("⚪  Desconectado")

        self.connect_btn.set_label("⏹ Desconectar" if connected else "🔌 Conectar")
        self.token_entry.set_sensitive(not connected)
        self.toggle_btn.set_sensitive(not connected)

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        GLib.idle_add(self._append_log, f"[{timestamp}] {message}\n")

    def _append_log(self, text: str) -> None:
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, text)
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)

    # ── Settings ──

    def _on_settings(self, _btn: Gtk.Button) -> None:
        dialog = SettingsDialog(self, self.config)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.config = dialog.get_values()
            save_config(self.config)
            self._log(f"Configuración guardada: {self.config}")
        dialog.destroy()

    # ── Cleanup ──

    def _on_destroy(self, _window: Gtk.Window) -> None:
        if self.bot_runner and self.bot_runner.is_running:
            self.bot_runner.stop()
        Gtk.main_quit()


# ──────────────────────────────── Entry point ────────────────────────────────


def main() -> None:
    app = SpamApp()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
