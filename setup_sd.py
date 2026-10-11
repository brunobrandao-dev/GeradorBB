# setup_sd.py — Instalador automático do Stable Diffusion (Forge) para GeradorBB
#
# Detecta, instala e inicia o Stable Diffusion Forge localmente.
# Não requer nenhuma ação manual do cliente.

from __future__ import annotations

import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def _sd_dir() -> Path:
    """Pasta onde o SD será instalado: Documents/GeradorBB/stable-diffusion/"""
    if getattr(sys, "frozen", False):
        try:
            import ctypes, ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(0, 0x0005, 0, 0, buf)
            base = Path(buf.value)
        except Exception:
            base = Path.home() / "Documents"
    else:
        base = Path.home() / "Documents"
    return base / "GeradorBB" / "stable-diffusion"


SD_DIR        = _sd_dir()
SD_WEBUI_BAT  = SD_DIR / "webui-user.bat"
SD_WEBUI_EXE  = SD_DIR / "webui.bat"
SD_PORT       = 7860
SD_URL        = f"http://127.0.0.1:{SD_PORT}"

# URL do instalador Forge (release estável)
_FORGE_REPO   = "https://github.com/lllyasviel/stable-diffusion-webui-forge.git"


# ---------------------------------------------------------------------------
# Detecção
# ---------------------------------------------------------------------------

def sd_instalado() -> bool:
    """Retorna True se o Forge já está instalado na pasta local."""
    return SD_WEBUI_BAT.exists() or SD_WEBUI_EXE.exists()


def sd_rodando() -> bool:
    """Retorna True se o servidor SD está respondendo na porta 7860."""
    try:
        req = urllib.request.Request(f"{SD_URL}/sdapi/v1/sd-models",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _git_disponivel() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Instalação
# ---------------------------------------------------------------------------

def instalar_sd(
    on_progresso: Callable[[str, int], None],  # (mensagem, pct 0-100)
    on_fim: Callable[[bool, str], None],        # (sucesso, mensagem)
):
    """
    Instala o Stable Diffusion Forge em background.
    Chama on_progresso() durante o processo e on_fim() ao terminar.
    Deve ser chamado em thread daemon.
    """
    def _run():
        try:
            # 1. Verifica git
            on_progresso("Verificando pré-requisitos...", 5)
            if not _git_disponivel():
                on_fim(False,
                    "Git não encontrado.\n"
                    "Instale o Git em git-scm.com e tente novamente.")
                return

            # 2. Cria pasta pai
            on_progresso("Preparando pasta de instalação...", 10)
            SD_DIR.parent.mkdir(parents=True, exist_ok=True)

            # 3. Clona o repositório
            if not SD_DIR.exists():
                on_progresso("Baixando Stable Diffusion Forge (~500 MB)...", 15)
                result = subprocess.run(
                    ["git", "clone", "--depth=1", _FORGE_REPO, str(SD_DIR)],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    on_fim(False,
                        f"Erro ao baixar o Forge:\n{result.stderr[:300]}")
                    return
            else:
                on_progresso("Forge já baixado — atualizando...", 15)
                subprocess.run(["git", "-C", str(SD_DIR), "pull"],
                               capture_output=True)

            # 4. Configura webui-user.bat para iniciar sem abrir browser
            on_progresso("Configurando inicialização...", 60)
            bat = SD_DIR / "webui-user.bat"
            if bat.exists():
                content = bat.read_text(encoding="utf-8", errors="ignore")
                # Adiciona flag --nowebui se não tiver
                if "--api" not in content:
                    content = content.replace(
                        "set COMMANDLINE_ARGS=",
                        "set COMMANDLINE_ARGS=--api --listen",
                    )
                    if "COMMANDLINE_ARGS" not in content:
                        content += "\nset COMMANDLINE_ARGS=--api --listen\n"
                    bat.write_text(content, encoding="utf-8")

            on_progresso("Instalação concluída!", 100)
            on_fim(True,
                "Stable Diffusion instalado com sucesso!\n\n"
                "Clique em 'Iniciar SD' para baixar os modelos e começar a usar.\n"
                "(Primeiro start: ~4 GB de modelos, pode demorar alguns minutos)")

        except Exception as e:
            on_fim(False, f"Erro inesperado durante instalação:\n{e}")

    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Iniciar / Parar
# ---------------------------------------------------------------------------

_sd_processo: Optional[subprocess.Popen] = None


def iniciar_sd(
    on_status: Callable[[str], None],
    on_pronto: Callable[[], None],
):
    """
    Inicia o processo do Stable Diffusion em background.
    Chama on_status() com mensagens de progresso.
    Chama on_pronto() quando o servidor estiver respondendo.
    """
    global _sd_processo

    if sd_rodando():
        on_status("Stable Diffusion já está rodando.")
        on_pronto()
        return

    if not sd_instalado():
        on_status("SD não instalado. Instale primeiro.")
        return

    bat = SD_WEBUI_BAT if SD_WEBUI_BAT.exists() else SD_WEBUI_EXE

    def _run():
        global _sd_processo
        on_status("Iniciando Stable Diffusion...")
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            _sd_processo = subprocess.Popen(
                ["cmd", "/c", str(bat)],
                cwd=str(SD_DIR),
                creationflags=flags,
            )
        except Exception as e:
            on_status(f"Erro ao iniciar SD: {e}")
            return

        # Aguarda até o servidor responder (máx 3 minutos)
        import time
        for _ in range(180):
            time.sleep(1)
            if sd_rodando():
                on_status("✓ Stable Diffusion pronto!")
                on_pronto()
                return
            if _sd_processo.poll() is not None:
                on_status("SD encerrou inesperadamente. Verifique a instalação.")
                return

        on_status("Tempo esgotado aguardando o SD iniciar.")

    threading.Thread(target=_run, daemon=True).start()


def parar_sd():
    """Encerra o processo SD se foi iniciado pelo GeradorBB."""
    global _sd_processo
    if _sd_processo and _sd_processo.poll() is None:
        _sd_processo.terminate()
        _sd_processo = None
