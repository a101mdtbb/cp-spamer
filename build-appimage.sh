#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP="cp-spamer"
ARCH="x86_64"
APPDIR="$SCRIPT_DIR/$APP.AppDir"
OUTPUT="$SCRIPT_DIR/${APP}-${ARCH}.AppImage"

info()  { echo -e "\e[34m•\e[0m $*"; }
ok()    { echo -e "\e[32m✓\e[0m $*"; }

rm -rf "$APPDIR" "$OUTPUT"
mkdir -p "$APPDIR/usr/share/$APP"
mkdir -p "$APPDIR/usr/lib"

# ── 1. App source ──
info "Copying application files..."
cp "$SCRIPT_DIR/cp-gtk.py" "$APPDIR/usr/share/$APP/"
ok "cp-gtk.py copied"

# ── 2. Python dependencies (from venv) ──
info "Copying Python packages from venv..."
VENV="$SCRIPT_DIR/cp"
SITEDIR="$APPDIR/usr/lib/python3/site-packages"
mkdir -p "$SITEDIR"
for pkg in "$VENV/lib/python3.14/site-packages/"*/; do
    cp -r "$pkg" "$SITEDIR/" 2>/dev/null || true
done
# also copy dist-info packages not in dirs
for pkg in "$VENV/lib/python3.14/site-packages/"*.dist-info; do
    cp -r "$pkg" "$SITEDIR/" 2>/dev/null || true
done
ok "Python packages copied"

# ── 3. PyGObject from system ──
info "Bundling PyGObject (gi) from system..."
SYSTEM_GI=$(python3 -c "import gi; print(gi.__file__)" 2>/dev/null) || SYSTEM_GI=""
if [ -n "$SYSTEM_GI" ]; then
    GI_DIR=$(dirname "$SYSTEM_GI")
    cp -r "$GI_DIR" "$SITEDIR/"
    # Find and copy _gi C extension .so
    find "$GI_DIR" -name "_gi*.so" -exec cp {} "$SITEDIR/gi/" \; 2>/dev/null || true
    ok "PyGObject bundled from $GI_DIR"
else
    err "PyGObject not found on system. Install python3-gi."
fi

# ── 4. Bundle C shared libraries for GTK ──
info "Bundling GTK/Glib shared libraries..."
LIBDIR="$APPDIR/usr/lib/gi-libs"
mkdir -p "$LIBDIR"

_so_deps() {
    find "$SITEDIR/gi" -name "*.so" 2>/dev/null | while read -r so; do
        ldd "$so" 2>/dev/null | awk '{print $3}' | grep -v '^$' | grep -v '('
    done
}

# Bundle libs that gi .so files need
_so_deps | sort -u | while read -r lib; do
    [ -f "$lib" ] && cp -n "$lib" "$LIBDIR/" 2>/dev/null || true
done

# Also bundle common GTK libs that might be indirect deps
for libdir in /usr/lib/x86_64-linux-gnu /usr/lib /lib/x86_64-linux-gnu /lib64; do
    [ -d "$libdir" ] || continue
    for libpattern in libgobject-2.0.so* libglib-2.0.so* libgio-2.0.so* \
                      libgmodule-2.0.so* libffi.so* libgthread-2.0.so* \
                      libgtk-3.so* libgdk-3.so* libpango-1.0.so* \
                      libpangocairo-1.0.so* libgdk_pixbuf-2.0.so* \
                      libcairo.so* libcairo-gobject.so* libatk-1.0.so* \
                      libepoxy.so* libX11.so* libxcb.so* libXrender.so* \
                      libXext.so* libXfixes.so* libXi.so* libXrandr.so* \
                      libXcursor.so* libXcomposite.so* libXdamage.so* \
                      libfreetype.so* libfontconfig.so* libharfbuzz.so* \
                      libfribidi.so* libpng16.so* libpixman-1.so* \
                      libz.so* libbz2.so* libexpat.so* libuuid.so* \
                      libdatrie.so* libthai.so* libxkbcommon.so* \
                      libwayland-client.so* libwayland-cursor.so* \
                      libwayland-egl.so* libEGL.so* libGLdispatch.so*; do
        for f in "$libdir"/$libpattern; do
            [ -f "$f" ] && cp -n "$f" "$LIBDIR/" 2>/dev/null || true
        done
    done
done
ok "Shared libraries bundled ($(ls "$LIBDIR" | wc -l) files)"

# ── 5. Desktop file & icon ──
cp "$SCRIPT_DIR/cp-spamer.desktop" "$APPDIR/"
cp "$SCRIPT_DIR/cp-spamer.png" "$APPDIR/"

# ── 6. AppRun ──
cat > "$APPDIR/AppRun" << 'RUNEOF'
#!/usr/bin/env bash
set -euo pipefail
APPDIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$APPDIR/usr/bin:$PATH"
export PYTHONPATH="$APPDIR/usr/lib/python3/site-packages:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$APPDIR/usr/lib/gi-libs:${LD_LIBRARY_PATH:-}"
export PYTHONNOUSERSITE=1
exec python3 "$APPDIR/usr/share/cp-spamer/cp-gtk.py"
RUNEOF
chmod +x "$APPDIR/AppRun"
ok "AppRun created"

# ── 7. Download appimagetool ──
APPIMAGETOOL="/tmp/appimagetool-${ARCH}.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    info "Downloading appimagetool..."
    wget -q --show-progress \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi
ok "appimagetool ready"

# ── 8. Build ──
info "Building AppImage..."
export ARCH="$ARCH"
APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

ok "AppImage created: $OUTPUT"
ls -lh "$OUTPUT"
