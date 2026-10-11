# GeradorBB.spec — Configuração do PyInstaller
# Gera 2 executáveis dentro de dist/GeradorBB/:
#   GeradorBB.exe  — interface gráfica (app.py)
#   engine.exe     — engine de vídeo  (engine_runner.py → engine.py)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path
import sys

# ── Assets do customtkinter ────────────────────────────────────────────────────
ctk_datas = collect_data_files("customtkinter")

# ── Assets do faster_whisper ───────────────────────────────────────────────────
fw_datas = collect_data_files("faster_whisper")

# ── Arquivos de dados do app ───────────────────────────────────────────────────
app_datas = [
    ("geradorbb.ico",          "."),
    ("requirements.txt",       "."),
    ("supabase_migration.sql", "."),
    ("THIRD_PARTY_NOTICES.txt", "."),
    ("ia_crypto.py",           "."),
    ("ia_services.py",         "."),
    ("gui_ia.py",              "."),
    ("gui_config_ia.py",       "."),
]

all_datas = ctk_datas + fw_datas + app_datas

# ── Hidden imports ─────────────────────────────────────────────────────────────
hidden = [
    # CustomTkinter
    "customtkinter",
    # Supabase e dependências
    "supabase", "supabase_auth", "storage3", "realtime", "postgrest",
    "httpx", "httpcore", "h11", "anyio", "sniffio",
    # PIL
    "PIL", "PIL._tkinter_finder", "PIL.Image", "PIL.ImageTk",
    # faster-whisper
    "faster_whisper", "ctranslate2",
    # scipy
    "scipy", "scipy.signal", "scipy.io.wavfile",
    # tkinter
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.simpledialog",
    "tkinter.filedialog",
    # stdlib
    "json", "pathlib", "threading", "subprocess", "shutil", "zipfile",
    "urllib.request", "runpy",
    # IA — Gemini roteiro + voz
    "google.generativeai", "google.ai.generativelanguage",
    "cryptography", "cryptography.fernet", "cryptography.hazmat",
    # Kokoro (voz offline) — instalado via pip em runtime se necessário
    # "kokoro", "soundfile",  # comentado: instalados on-demand, não bundled
]

# ═══════════════════════════════════════════════════════════════════════════════
# 1. GeradorBB.exe — Interface gráfica
# ═══════════════════════════════════════════════════════════════════════════════
a_gui = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=all_datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["unittest", "test"],
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data)
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="GeradorBB",
    icon="geradorbb.ico",
    console=False,
    debug=False,
    upx=False,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. engine.exe — Engine de vídeo (chamado como subprocess pelo GUI)
# ═══════════════════════════════════════════════════════════════════════════════
a_engine = Analysis(
    ["engine_runner.py"],
    pathex=["."],
    binaries=[],
    datas=fw_datas + [("geradorbb.ico", ".")],
    hiddenimports=hidden + ["engine", "mascote", "personagem", "objetos"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["unittest", "test", "customtkinter", "tkinter"],
    noarchive=False,
)
pyz_engine = PYZ(a_engine.pure, a_engine.zipped_data)
exe_engine = EXE(
    pyz_engine,
    a_engine.scripts,
    [],
    exclude_binaries=True,
    name="engine",
    icon="geradorbb.ico",
    console=True,
    debug=False,
    upx=False,
)

# ═══════════════════════════════════════════════════════════════════════════════
# COLLECT — junta tudo em dist/GeradorBB/
# ═══════════════════════════════════════════════════════════════════════════════
coll = COLLECT(
    exe_gui,    a_gui.binaries,    a_gui.zipfiles,    a_gui.datas,
    exe_engine, a_engine.binaries, a_engine.zipfiles, a_engine.datas,
    strip=False,
    upx=False,
    name="GeradorBB",
)
