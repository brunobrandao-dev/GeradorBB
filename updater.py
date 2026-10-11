# updater.py — Sistema de atualização automática do GeradorBB
#
# Para soltar uma atualização:
#   1. Gere o build (BUILD.bat)
#   2. Compacte: powershell Compress-Archive -Path * -DestinationPath ..\GeradorBB_vX.Y.zip
#   3. Hospede o zip (GitHub Releases, Google Drive, etc.)
#   4. No Supabase → tabela versoes:
#      INSERT INTO versoes (versao, url_download, notas)
#      VALUES ('2.1', 'https://...zip', 'O que mudou')

import json
import sys
import os
import threading
import zipfile
from pathlib import Path

VERSAO_LOCAL = "4.0"   # ← atualize a cada release

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
    # Pasta Documentos real (funciona em PT, EN e qualquer idioma do Windows)
    try:
        import ctypes.wintypes
        _buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0x0005, 0, 0, _buf)
        DATA_DIR = Path(_buf.value) / "GeradorBB"
    except Exception:
        DATA_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/Public")) / "Documents" / "GeradorBB"
else:
    APP_DIR  = Path(__file__).resolve().parent
    DATA_DIR = APP_DIR

VERSAO_FILE = APP_DIR / "versao.json"


def _sb():
    from supabase import create_client
    from auth import SUPABASE_URL, SUPABASE_KEY
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def versao_local() -> str:
    """Lê a versão instalada (versao.json tem precedência sobre a constante)."""
    if VERSAO_FILE.exists():
        try:
            return json.loads(VERSAO_FILE.read_text(encoding="utf-8")).get("versao", VERSAO_LOCAL)
        except Exception:
            pass
    return VERSAO_LOCAL


def _versao_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def verificar_atualizacao(on_resultado=None):
    """
    Verifica em background se há atualização disponível.
    on_resultado(info) chamado na thread principal se houver update.
    """
    def _check():
        try:
            resp = (
                _sb()
                .table("versoes")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not resp.data:
                return
            info = resp.data[0]
            servidor = info.get("versao", "0")
            if _versao_tuple(servidor) > _versao_tuple(versao_local()):
                if on_resultado:
                    on_resultado(info)
        except Exception:
            pass  # sem conexão — ignora silenciosamente

    threading.Thread(target=_check, daemon=True).start()


def baixar_e_instalar(url: str, versao: str, on_progresso=None, on_fim=None):
    """
    Baixa o zip, extrai e cria o script de instalação.

    on_progresso(pct: int, etapa: str)
        pct   — 0..100
        etapa — "baixando" | "extraindo" | "preparando"

    on_fim(ok: bool, resultado: str)
        ok=True  → resultado é o caminho do .bat; chame aplicar_atualizacao(resultado)
        ok=False → resultado é a mensagem de erro

    IMPORTANTE: esta função NÃO encerra o processo. Quem chama on_fim(True)
    deve chamar aplicar_atualizacao() quando quiser reiniciar o app.
    """
    def _run():
        try:
            import urllib.request
            zip_path = APP_DIR / f"_update_{versao}.zip"

            # ── 1. Download ──────────────────────────────────────────────
            def _prog(bloco, tam_bloco, tam_total):
                if on_progresso and tam_total > 0:
                    pct = min(99, int(bloco * tam_bloco * 100 / tam_total))
                    on_progresso(pct, "baixando")

            if on_progresso:
                on_progresso(0, "baixando")
            urllib.request.urlretrieve(url, zip_path, reporthook=_prog)

            # ── 2. Extração ──────────────────────────────────────────────
            if on_progresso:
                on_progresso(0, "extraindo")

            with zipfile.ZipFile(zip_path, "r") as z:
                nomes = z.namelist()
                raiz = nomes[0].split("/")[0] if nomes else ""
                tem_raiz = raiz and all(
                    n.startswith(raiz + "/") for n in nomes if n != raiz + "/"
                )
                tmp_dir = APP_DIR / "_update_tmp"
                if tmp_dir.exists():
                    import shutil
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                z.extractall(tmp_dir)

            src_dir = (tmp_dir / raiz) if tem_raiz else tmp_dir

            # ── 3. Preparação ────────────────────────────────────────────
            if on_progresso:
                on_progresso(0, "preparando")

            (src_dir / "versao.json").write_text(
                json.dumps({"versao": versao}, ensure_ascii=False),
                encoding="utf-8",
            )

            # ── 4. Cria o .bat que copia os arquivos após o app fechar ───
            exe_nome = Path(sys.executable).name
            bat = APP_DIR / "_updater_apply.bat"
            bat.write_text(
                f"@echo off\n"
                f"title Atualizando GeradorBB...\n"
                f":wait\n"
                f"timeout /t 1 /nobreak >nul\n"
                f"tasklist /fi \"imagename eq {exe_nome}\" 2>nul"
                f" | find /i \"{exe_nome}\" >nul\n"
                f"if not errorlevel 1 goto wait\n"
                f"xcopy /E /Y /I \"{src_dir}\\*\" \"{APP_DIR}\\\"\n"
                f"rmdir /S /Q \"{tmp_dir}\"\n"
                f"del \"{zip_path}\" 2>nul\n"
                f"del \"%~f0\"\n"
                f"start \"\" \"{APP_DIR / exe_nome}\"\n",
                encoding="utf-8",
            )

            # Avisa que está pronto — a UI decide quando fechar o app
            if on_fim:
                on_fim(True, str(bat))

        except Exception as e:
            if on_fim:
                on_fim(False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def aplicar_atualizacao(bat_path: str):
    """
    Lança o .bat de instalação e encerra o app imediatamente.
    Deve ser chamado da thread principal (ex: após contagem regressiva na UI).
    O .bat espera o exe fechar, copia os novos arquivos e reinicia o app.
    """
    import subprocess
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=flags)
    os._exit(0)
