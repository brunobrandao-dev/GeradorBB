# gui_main.py — Janela principal pós-login
#
# Layout: sidebar 230px à esquerda + área de conteúdo à direita.
# Cada "tela" é um CTkFrame; o controlador troca via _mostrar_tela().

from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
import datetime
from pathlib import Path

import customtkinter as ctk
from gui_theme import (
    BG, BG2, BG3, BG4, BG5, ACCENT, ACCENT2, ACCENT3,
    SUCCESS, SUCCESS_HOVER, SUCCESS_TEXT, WARNING, DANGER, DANGER_HOVER, INFO,
    ACCENT_GHOST_HOVER,
    TEXT, SUBTEXT, BORDER, BORDER2,
    COLOR_LOGO, COLOR_LEGENDA, COLOR_PERSONAGEM, COLOR_BORDA,
    BG_ROW_SUCCESS,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL,
    FONT_SIZE_XXL, FONT_TITLE, FONT_H2, FONT_BODY, FONT_SMALL, FONT_MONO,
    SIDEBAR_W, CORNER_R, PAD,
    BTN_H, BTN_H_LG, BTN_H_SM, ENTRY_H,
)
import auth
import gui_templates as _gt
import gui_ajuda as _gaj
try:
    from updater import versao_local as _versao_local
except Exception:
    def _versao_local(): return "?"

# ---------------------------------------------------------------------------
# Caminhos base — separa arquivos do app dos dados do usuário
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Executando como .exe — app fica onde está o exe
    APP_DIR  = Path(sys.executable).parent
    # Pasta Documentos real do Windows (funciona em PT, EN e qualquer idioma)
    try:
        import ctypes.wintypes
        _buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0x0005, 0, 0, _buf)  # CSIDL_PERSONAL
        _docs = Path(_buf.value)
    except Exception:
        _docs = Path(os.environ.get("USERPROFILE", "C:/Users/Public")) / "Documents"
    DATA_DIR = _docs / "GeradorBB"
else:
    # Em desenvolvimento ambos apontam para a pasta do projeto
    APP_DIR  = Path(__file__).parent
    DATA_DIR = APP_DIR

# Alias para compatibilidade com código existente
BASE_DIR    = DATA_DIR
CONFIG_FILE = DATA_DIR / "config_app.json"


# ---------------------------------------------------------------------------
# Config padrão
# ---------------------------------------------------------------------------
CONFIG_PADRAO = {
    "largura": 1080,
    "altura": 1920,
    "fps": 30,
    "fundo": "preto",
    "fonte": "Arial",
    "tamanho_fonte": 64,
    "cor_legenda": "amarelo",
    "posicao_legenda": 300,
    "personagem_ativo": True,
    "personagem_tamanho": 100,
    "engine_path": "",   # onde fica engine.py (engine)
    "canais_dir":      "",    # vazio = BASE_DIR/canais
    "projeto_ativo":   "",    # vazio = "default"
    # avançado
    "whisper_modelo":       "small",  # tiny|base|small|medium|large
    "palavras_por_legenda": 5,
    "zoom_maximo":          0.06,
    "volume_musica":        0.10,
}

def _inicializar_dados():
    """
    Cria toda a estrutura de pastas e config padrão na primeira vez.
    Seguro de chamar sempre — usa exist_ok=True em tudo.
    """
    # Migração: renomeia pasta antiga "banco" → "canais" automaticamente
    _pasta_antiga = DATA_DIR / "banco"
    _pasta_nova   = DATA_DIR / "canais"
    if _pasta_antiga.exists() and not _pasta_nova.exists():
        try:
            _pasta_antiga.rename(_pasta_nova)
        except Exception:
            pass  # se falhar, cria a nova normalmente abaixo

    # Pastas raiz
    for pasta in ("canais", "videos"):
        (DATA_DIR / pasta).mkdir(parents=True, exist_ok=True)

    # Projeto padrão "default" com toda a estrutura interna
    projeto_default = DATA_DIR / "canais" / "default" / "projeto"
    for sub in (
        "cenas", "audio", "roteiro", "musica",
        "imagens", "logos", "temas",
        "personagem", "objetos", "bordas",
    ):
        (projeto_default / sub).mkdir(parents=True, exist_ok=True)

    # Pastas de ajuste de imagens e vídeos
    (DATA_DIR / "canais" / "default" / "ajuste" / "entrada").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "canais" / "default" / "ajuste" / "saida").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "canais" / "default" / "videos").mkdir(parents=True, exist_ok=True)

    # Pastas de IA (roteiro e exemplos)
    (DATA_DIR / "canais" / "default" / "projeto" / "ia" / "exemplos").mkdir(parents=True, exist_ok=True)

    # Templates — cria o "Vídeo Único" padrão se necessário
    try:
        import gui_templates as _gt_init
        _gt_init.inicializar_templates()
    except Exception:
        pass

    # Config padrão — só cria se não existir ainda
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            json.dumps(CONFIG_PADRAO, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Flag para saber que já foi inicializado
    flag = DATA_DIR / ".inicializado"
    primeiro_acesso = not flag.exists()
    flag.touch()
    return primeiro_acesso   # True só na primeira vez


# Executa na importação — cria tudo que faltar, ignora o que já existe
_PRIMEIRO_ACESSO = _inicializar_dados()


def _carregar_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            dados = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**CONFIG_PADRAO, **dados}
        except Exception:
            pass
    return dict(CONFIG_PADRAO)

def _salvar_config(dados: dict):
    CONFIG_FILE.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

def _notificar_windows(titulo: str, mensagem: str):
    """Dispara uma notificação toast do Windows sem dependências externas."""
    import subprocess, sys
    if sys.platform != "win32":
        return
    # Usa PowerShell + Windows.UI.Notifications via Add-Type (funciona no Win 10+)
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows, ContentType=WindowsRuntime] | Out-Null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows, ContentType=WindowsRuntime] | Out-Null; "
        "$xml = [Windows.Data.Xml.Dom.XmlDocument]::new(); "
        f"$xml.LoadXml('<toast><visual><binding template=\"ToastText02\">"
        f"<text id=\"1\">{titulo}</text>"
        f"<text id=\"2\">{mensagem}</text>"
        f"</binding></visual></toast>'); "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('GeradorBB').Show($toast);"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden",
             "-Command", script],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception:
        pass  # notificação é best-effort

# ---------------------------------------------------------------------------
# Helpers de path — separados em engine (engine.py) e projeto (dados)
# ---------------------------------------------------------------------------

def _banco_dir() -> Path:
    """Pasta raiz que contém todos os projetos."""
    cfg = _carregar_config()
    bd = cfg.get("banco_dir", "")
    return Path(bd) if bd else BASE_DIR / "banco"

def _projeto_ativo() -> str:
    """Nome do projeto atualmente selecionado."""
    cfg = _carregar_config()
    return cfg.get("projeto_ativo") or "default"

def _projeto_dir() -> Path:
    """Pasta raiz do projeto ativo (banco/<nome>)."""
    return _banco_dir() / _projeto_ativo()

def _engine_dir() -> Path:
    """Pasta onde engine.py / engine.exe estão instalados."""
    cfg = _carregar_config()
    p = cfg.get("engine_path")
    if p and Path(p).exists():
        return Path(p)
    return BASE_DIR


def _engine_cmd(args: list) -> list:
    """
    Retorna o comando para chamar o engine como subprocess.
    - Em desenvolvimento: [python, engine.py, ...args]
    - Frozen (PyInstaller):  [_internal/engine.exe, ...args]
    """
    if getattr(sys, "frozen", False):
        exe = APP_DIR / "_internal" / "engine.exe"
        return [str(exe)] + args
    else:
        script = _engine_dir() / "engine.py"
        return [sys.executable, str(script)] + args

def _listar_projetos() -> list[str]:
    """Retorna lista de nomes de projetos em _banco_dir()."""
    bd = _banco_dir()
    if not bd.exists():
        return []
    return sorted(
        p.name for p in bd.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )

def _criar_projeto(nome: str) -> Path:
    """Cria a estrutura de pastas de um novo projeto."""
    proj = _banco_dir() / nome
    for sub in ("projeto/cenas", "projeto/roteiro", "projeto/audio",
                "projeto/musica", "projeto/imagens", "projeto/temas",
                "projeto/logos", "projeto/personagem",
                "projeto/objetos", "projeto/bordas",
                "projeto/ia/exemplos",
                "videos", "ajuste/entrada", "ajuste/saida"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    return proj


def _duplicar_projeto(origem: str, destino: str) -> Path:
    """
    Copia o projeto 'origem' para 'destino'.
    Cria a estrutura base do destino e depois copia os arquivos relevantes:
    cenas, roteiro, audio, musica, personagem — sem copiar vídeos gerados.
    """
    import shutil
    src = _banco_dir() / origem
    dst = _banco_dir() / destino

    # Cria estrutura do destino primeiro
    _criar_projeto(destino)

    # Subpastas para copiar (exclui videos/ e ajuste/ para não inflar o projeto)
    _COPIAR = (
        "projeto/cenas", "projeto/roteiro", "projeto/audio",
        "projeto/musica", "projeto/imagens", "projeto/temas",
        "projeto/logos",  "projeto/personagem", "projeto/objetos",
        "projeto/bordas", "projeto/ia",
    )
    for sub in _COPIAR:
        src_sub = src / sub
        dst_sub = dst / sub
        if src_sub.exists():
            dst_sub.mkdir(parents=True, exist_ok=True)
            for item in src_sub.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src_sub)
                    destino_arq = dst_sub / rel
                    destino_arq.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(destino_arq))

    return dst

def _rankadorama_dir() -> Path:
    """Alias mantido para compatibilidade."""
    return _engine_dir()

def _imagens_dir() -> Path:
    return _projeto_dir() / "projeto" / "cenas"

def _layouts_dir() -> Path:
    return _projeto_dir() / "projeto" / "layouts"

def _audio_dir() -> Path:
    return _projeto_dir() / "projeto" / "audio"

def _roteiro_dir() -> Path:
    return _projeto_dir() / "projeto" / "roteiro"

def _videos_dir() -> Path:
    return _projeto_dir() / "videos"

def _personagem_cfg_path() -> Path:
    return _projeto_dir() / "projeto" / "personagem" / "personagem_config.json"

def _mascote_cfg_path() -> Path:
    return _projeto_dir() / "projeto" / "mascote" / "mascote_config.json"

def _personagem_dir() -> Path:
    return _projeto_dir() / "projeto" / "personagem"

def _mascote_dir() -> Path:
    return _projeto_dir() / "projeto" / "mascote"

# ---------------------------------------------------------------------------
# Helpers de widget
# ---------------------------------------------------------------------------

def _sep(master):
    return ctk.CTkFrame(master, height=1, fg_color=BORDER)

def _card(master, **kwargs):
    defaults = dict(fg_color=BG3, corner_radius=CORNER_R,
                    border_width=1, border_color=BORDER)
    return ctk.CTkFrame(master, **{**defaults, **kwargs})

def _label(master, text, size=FONT_SIZE_MD, bold=False, color=TEXT, **kwargs):
    weight = "bold" if bold else "normal"
    return ctk.CTkLabel(master, text=text,
                        font=(FONT_FAMILY, size, weight),
                        text_color=color, **kwargs)

def _btn(master, text, command, accent=True, width=160, height=40, **kwargs):
    fg = ACCENT if accent else "transparent"
    hv = ACCENT3 if accent else BG3
    bc = ACCENT if not accent else None
    bw = 1 if not accent else 0
    extra = {}
    if bc:
        extra["border_color"] = bc
        extra["border_width"] = bw
    return ctk.CTkButton(
        master, text=text, command=command,
        width=width, height=height,
        fg_color=fg, hover_color=hv,
        text_color=TEXT if accent else ACCENT,
        corner_radius=CORNER_R,
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        **extra, **kwargs,
    )

def _section_title(parent, titulo: str):
    """Título de seção com barra colorida à esquerda."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(16, 8))
    # Barra accent vertical
    ctk.CTkFrame(row, width=4, height=22, corner_radius=2, fg_color=ACCENT).pack(side="left", padx=(0, 10))
    _label(row, titulo, size=FONT_SIZE_LG, bold=True).pack(side="left", anchor="w")

# ===========================================================================
# Janela Principal
# ===========================================================================

class JanelaPrincipal(ctk.CTk):
    def __init__(self, user: dict, licenca: dict):
        super().__init__()
        self._user    = user
        self._licenca = licenca

        self.title("GeradorBB")
        self.geometry("1140x720")
        self.minsize(920, 620)
        self.configure(fg_color=BG)

        # Centraliza
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - 1140) // 2
        y  = (sh - 720) // 2
        self.geometry(f"1140x720+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._sair)
        self.lift()
        self.focus_force()

        self._tela_atual: str = ""
        self._build_ui()
        self.update()
        self.after(200, lambda: self._mostrar_tela("inicio"))

        # Atalhos de teclado — controle geral
        self.bind("<F5>",        lambda e: self._reload_tela())
        self.bind("<Control-r>", lambda e: self._reload_tela())
        self.bind("<Control-F5>", lambda e: self._reiniciar_app())
        self.bind("<F11>",       lambda e: self._toggle_fullscreen())

        # Atalhos de teclado — navegação (Ctrl+1..9+0)
        _nav_atalhos = {
            "1": "inicio",  "2": "projetos",   "3": "gerar",
            "4": "cenas",   "6": "preview",
            "7": "templates","9": "imagens",
            "0": "config",
        }
        for _k, _t in _nav_atalhos.items():
            self.bind(f"<Control-Key-{_k}>", lambda e, t=_t: self._mostrar_tela(t))

    # ------------------------------------------------------------------
    # Estrutura principal
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Wrapper: sidebar + conteúdo + status bar
        main_wrapper = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main_wrapper.pack(fill="both", expand=True)

        # Sidebar
        self._sidebar = ctk.CTkFrame(main_wrapper, width=SIDEBAR_W,
                                     fg_color=BG2, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Separador vertical entre sidebar e conteúdo
        ctk.CTkFrame(main_wrapper, width=1, fg_color=BORDER).pack(side="left", fill="y")

        # Área de conteúdo
        content_wrapper = ctk.CTkFrame(main_wrapper, fg_color=BG, corner_radius=0)
        content_wrapper.pack(side="left", fill="both", expand=True)

        self._content = ctk.CTkFrame(content_wrapper, fg_color=BG, corner_radius=0)
        self._content.pack(fill="both", expand=True)

        # Status bar no fundo
        self._status_bar = ctk.CTkFrame(self, height=28, fg_color=BG4,
                                        corner_radius=0)
        self._status_bar.pack(fill="x", side="bottom")
        self._status_bar.pack_propagate(False)
        self._build_status_bar()

        # Frames das telas — construídos um a um para manter o event loop
        # responsivo durante o carregamento (evita "não respondendo")
        self._telas: dict[str, ctk.CTkFrame] = {}
        for _chave, _cls in [
            ("inicio",     TelaDashboard),
            ("projetos",   TelaGerenciarProjetos),
            ("gerar",      TelaGerarVideo),
            ("cenas",      TelaCenas),
            ("preview",    TelaPreview),
            ("templates",  _gt.TelaTemplates),
            ("config",     TelaConfiguracoes),
            ("videos",     TelaMeusVideos),
        ]:
            self._telas[_chave] = _cls(self._content, self)
            self.update()
        if self._user.get("is_admin"):
            self._telas["admin"] = TelaAdmin(self._content, self)
            self.update()

        # Painel flutuante do assistente
        self._painel_assistente = _gaj.PainelAssistente(self._content)
        # Sobrescreve o comando do botão "ajuda" (painel já existe aqui)
        self._fixar_btn_assistente()

    def _build_status_bar(self):
        sb = self._status_bar
        ctk.CTkLabel(sb, text=f"GeradorBB v{_versao_local()}",
                     font=(FONT_FAMILY, 10), text_color=SUBTEXT).pack(side="left", padx=12)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="left", fill="y", pady=6)
        self._proj_status_lbl = ctk.CTkLabel(
            sb, text=f"  {_projeto_ativo()}",
            font=(FONT_FAMILY, 10, "bold"), text_color=INFO)
        self._proj_status_lbl.pack(side="left", padx=(4, 0))
        self._status_lbl = ctk.CTkLabel(sb, text="Pronto",
                                        font=(FONT_FAMILY, 10), text_color=SUCCESS)
        self._status_lbl.pack(side="right", padx=8)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="right", fill="y", pady=6)
        self._clock_lbl = ctk.CTkLabel(sb, text="",
                                       font=(FONT_FAMILY, 10), text_color=SUBTEXT)
        self._clock_lbl.pack(side="right", padx=(0, 8))
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="right", fill="y", pady=6)
        self._atualizar_relogio()

    def _atualizar_relogio(self):
        agora = datetime.datetime.now().strftime("%H:%M:%S")
        self._clock_lbl.configure(text=agora)
        self.after(1000, self._atualizar_relogio)

    def _toggle_fullscreen(self):
        """F11 — alterna entre janela maximizada e normal."""
        try:
            if self.state() == "zoomed":
                self.state("normal")
                self._fs_btn.configure(
                    text="  ⛶   Tela cheia  (F11)", text_color=SUBTEXT)
            else:
                self.state("zoomed")
                self._fs_btn.configure(
                    text="  ⊟   Janela  (F11)", text_color=INFO)
        except Exception:
            pass

    def set_status(self, texto: str, cor: str = SUCCESS):
        """Atualiza o texto da status bar — chamado pelas telas filhas."""
        try:
            self._status_lbl.configure(text=texto, text_color=cor)
        except Exception:
            pass

    def _build_sidebar(self):
        sb = self._sidebar

        # ── Faixa de marca no topo ─────────────────────────────────────────────
        topo = ctk.CTkFrame(sb, fg_color=ACCENT, corner_radius=0, height=4)
        topo.pack(fill="x")
        topo.pack_propagate(False)

        # ── Logo / Brand ───────────────────────────────────────────────────────
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=PAD, pady=(16, 0))
        ctk.CTkLabel(brand, text="GeradorBB",
                     font=(FONT_FAMILY, 20, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(brand, text=f" v{_versao_local()}",
                     font=(FONT_FAMILY, 10),
                     text_color=SUBTEXT).pack(side="left", pady=(6, 0))

        _sep(sb).pack(fill="x", padx=PAD, pady=(12, 0))

        # ── Perfil ─────────────────────────────────────────────────────────────
        perfil = ctk.CTkFrame(sb, fg_color=BG2, corner_radius=CORNER_R,
                              border_width=1, border_color=BORDER)
        perfil.pack(fill="x", padx=10, pady=(10, 0))

        perfil_inner = ctk.CTkFrame(perfil, fg_color="transparent")
        perfil_inner.pack(fill="x", padx=12, pady=10)

        avatar_frame = ctk.CTkFrame(perfil_inner, width=46, height=46,
                                    corner_radius=23, fg_color=ACCENT,
                                    border_width=2, border_color=ACCENT2)
        avatar_frame.pack_propagate(False)
        avatar_frame.pack(side="left")
        inicial = (self._user.get("nome") or "?")[0].upper()
        ctk.CTkLabel(avatar_frame, text=inicial,
                     font=(FONT_FAMILY, 20, "bold"),
                     text_color=TEXT).place(relx=0.5, rely=0.5, anchor="center")

        info_col = ctk.CTkFrame(perfil_inner, fg_color="transparent")
        info_col.pack(side="left", padx=(10, 0), fill="x", expand=True)
        nome = self._user.get("nome", "Usuário")
        ctk.CTkLabel(info_col, text=nome,
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        badge_txt, badge_cor = self._badge_licenca()
        ctk.CTkLabel(info_col, text=badge_txt,
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=badge_cor, anchor="w").pack(anchor="w")

        # ── Projeto ────────────────────────────────────────────────────────────
        proj_card = ctk.CTkFrame(sb, fg_color=BG2, corner_radius=CORNER_R,
                                 border_width=1, border_color=BORDER)
        proj_card.pack(fill="x", padx=10, pady=(8, 0))

        proj_inner = ctk.CTkFrame(proj_card, fg_color="transparent")
        proj_inner.pack(fill="x", padx=12, pady=(8, 8))
        ctk.CTkLabel(proj_inner, text="CANAL",
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=SUBTEXT).pack(anchor="w", pady=(0, 4))

        proj_row = ctk.CTkFrame(proj_inner, fg_color="transparent")
        proj_row.pack(fill="x")

        projetos = _listar_projetos() or ["default"]
        ativo = _projeto_ativo()
        if ativo not in projetos:
            projetos = [ativo] + projetos

        self._seletor_proj = ctk.CTkOptionMenu(
            proj_row,
            values=projetos,
            command=self._trocar_projeto,
            width=SIDEBAR_W - 80,
            height=30,
            fg_color=BG3,
            button_color=ACCENT,
            button_hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            corner_radius=8,
        )
        self._seletor_proj.set(ativo)
        self._seletor_proj.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            proj_row, text="+",
            command=lambda: self._mostrar_tela("projetos"),
            width=28, height=30,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(side="left", padx=(4, 0))

        # ── Navegação ──────────────────────────────────────────────────────────
        _sep(sb).pack(fill="x", padx=10, pady=(12, 8))

        # Nav: strings = rótulo de grupo; tuplas = item navegável
        nav_items = [
            "GERAL",
            ("inicio",     "🏠", "Início",           None,  "1"),
            ("projetos",   "📺", "Canais",             None,  "2"),
            "PRODUÇÃO",
            ("gerar",      "🎬", "Gerar Vídeo",       ACCENT,"3"),
            ("cenas",      "🎞️", "Organizar Cenas",   None,  "4"),
            ("preview",    "👁️", "Preview Layout",    None,  "6"),
            ("templates",  "📋", "Templates",         None,  "7"),
            "SISTEMA",
            ("videos",     "📁", "Meus Vídeos",       None,  None),
            ("config",     "⚙️", "Configurações",     None,  "0"),
            ("ajuda",      "💬", "Assistente",        None,  None),
        ]
        if self._user.get("is_admin"):
            nav_items += ["ADMIN", ("admin", "🛡️", "Painel Admin", WARNING, None)]

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._nav_indicators: dict[str, ctk.CTkFrame] = {}

        for item in nav_items:
            if item is None:
                ctk.CTkFrame(sb, height=1, fg_color=BORDER).pack(
                    fill="x", padx=14, pady=3)
                continue
            if isinstance(item, str):
                grp = ctk.CTkFrame(sb, fg_color="transparent")
                grp.pack(fill="x", padx=16, pady=(8, 1))
                ctk.CTkLabel(grp, text=item,
                             font=(FONT_FAMILY, 8, "bold"),
                             text_color=BORDER2).pack(side="left")
                continue
            # item é tupla (chave, icone, rotulo, cor_destaque[, shortcut])
            if len(item) == 5:
                chave, icone, rotulo, cor_destaque, sc = item
            else:
                chave, icone, rotulo, cor_destaque = item
                sc = None

            row = ctk.CTkFrame(sb, fg_color="transparent", height=40)
            row.pack(fill="x", padx=6, pady=1)
            row.pack_propagate(False)

            indicator = ctk.CTkFrame(row, width=3, fg_color="transparent", corner_radius=2)
            indicator.pack(side="left", fill="y", padx=(2, 0))
            self._nav_indicators[chave] = indicator

            if sc:
                ctk.CTkLabel(row, text=f"^{sc}",
                             font=(FONT_FAMILY, 8),
                             text_color=BORDER2,
                             width=24).pack(side="right", padx=(0, 6))

            # Container de largura fixa garante alinhamento independente do emoji
            cor_txt = cor_destaque if cor_destaque else SUBTEXT
            _icon_box = ctk.CTkFrame(row, width=28, fg_color="transparent")
            _icon_box.pack(side="left", padx=(6, 0))
            _icon_box.pack_propagate(False)
            ctk.CTkLabel(
                _icon_box, text=icone,
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=cor_txt,
            ).pack(expand=True)

            btn = ctk.CTkButton(
                row, text=rotulo,
                command=lambda c=chave: self._mostrar_tela(c),
                anchor="w", height=40, corner_radius=8,
                fg_color="transparent", hover_color=BG3,
                text_color=cor_txt,
                font=(FONT_FAMILY, FONT_SIZE_MD),
            )
            btn.pack(side="left", fill="both", expand=True)
            self._nav_btns[chave] = btn

        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="y", expand=True)
        _sep(sb).pack(fill="x", padx=10, pady=(0, 4))

        # Botão janela/tela cheia
        self._fs_btn = ctk.CTkButton(
            sb, text="  ⛶   Tela cheia  (F11)",
            command=self._toggle_fullscreen,
            height=36, anchor="w", corner_radius=8,
            fg_color="transparent", hover_color=BG3,
            text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        self._fs_btn.pack(fill="x", padx=6, pady=(0, 2))

        sair_btn = ctk.CTkButton(
            sb, text="  ⏻  Sair",
            command=self._sair, height=36, anchor="w", corner_radius=8,
            fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
            text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        sair_btn.pack(fill="x", padx=6, pady=(0, 10))
        sair_btn.bind("<Enter>", lambda _: sair_btn.configure(text_color=DANGER))
        sair_btn.bind("<Leave>", lambda _: sair_btn.configure(text_color=SUBTEXT))

    def _trocar_projeto(self, nome: str):
        cfg = _carregar_config()
        cfg["projeto_ativo"] = nome
        _salvar_config(cfg)
        try:
            self._proj_status_lbl.configure(text=f"  {nome}")
        except Exception:
            pass
        # Recarrega a tela atual
        if self._tela_atual and hasattr(self._telas.get(self._tela_atual, None), "ao_exibir"):
            self._telas[self._tela_atual].ao_exibir()

    def _atualizar_seletor_projeto(self):
        projetos = _listar_projetos() or ["default"]
        ativo = _projeto_ativo()
        if ativo not in projetos:
            projetos = [ativo] + projetos
        try:
            self._seletor_proj.configure(values=projetos)
            self._seletor_proj.set(ativo)
        except Exception:
            pass

    def _badge_licenca(self) -> tuple[str, str]:
        if self._user.get("is_admin"):
            return ("★ Administrador", ACCENT)
        lic = self._licenca
        if lic.get("tipo") == "vitalicio":
            return ("✓ Vitalício", SUCCESS)
        dias = lic.get("dias_restantes")
        if dias is None:
            return ("✗ Sem licença", DANGER)
        if dias <= 7:
            return (f"⚠ {dias} dias restantes", DANGER)
        if dias <= 15:
            return (f"⏳ {dias} dias restantes", WARNING)
        return (f"✓ {dias} dias restantes", SUCCESS)

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    def _mostrar_tela(self, chave: str):
        if chave not in self._telas:
            return  # itens de painel (ex: "ajuda") não têm tela
        if self._tela_atual == chave:
            return
        # Esconde todas
        for t in self._telas.values():
            t.pack_forget()
        # Atualiza estilo dos botões de nav
        _nav_cores = {
            "gerar": ACCENT,
            "admin": WARNING,
        }
        for k, btn in self._nav_btns.items():
            if k == chave:
                btn.configure(fg_color=BG3, text_color=TEXT)
                self._nav_indicators[k].configure(fg_color=ACCENT)
            else:
                btn.configure(fg_color="transparent",
                              text_color=_nav_cores.get(k, SUBTEXT))
                self._nav_indicators[k].configure(fg_color="transparent")
        # Mostra a tela selecionada
        self._telas[chave].pack(fill="both", expand=True)
        self._tela_atual = chave
        self.update_idletasks()
        # Recarrega se a tela suportar
        if hasattr(self._telas[chave], "ao_exibir"):
            self._telas[chave].ao_exibir()

    # ------------------------------------------------------------------
    # Ações globais
    # ------------------------------------------------------------------

    def _reload_tela(self):
        """F5 / Ctrl+R — recarrega a tela atual (chama ao_exibir se existir)."""
        chave = self._tela_atual
        if not chave:
            return
        tela = self._telas.get(chave)
        if tela and hasattr(tela, "ao_exibir"):
            tela.ao_exibir()
            self.set_status("Tela recarregada", SUCCESS)
        else:
            self.set_status("Nada para recarregar", SUBTEXT)

    def _reiniciar_app(self):
        """Ctrl+F5 — reinicia o processo Python do zero (recarrega todo o código)."""
        import subprocess
        # Lança uma nova instância e encerra a atual
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    def _fixar_btn_assistente(self):
        btn = self._nav_btns.get("ajuda")
        if btn:
            btn.configure(command=lambda: self._painel_assistente.toggle(self._content))

    def _sair(self):
        auth.logout()
        sys.exit(0)


# ===========================================================================
# Controller para uso com janela externa (master já existente)
# ===========================================================================

class _PrincipalController:
    """
    Constrói a UI principal dentro de `master` (janela CTk existente).
    Não herda de CTk — apenas usa master como container.
    """

    def __init__(self, master, user: dict, licenca: dict):
        self._master  = master
        self._user    = user
        self._licenca = licenca
        self._tela_atual: str = ""
        self._build_ui()
        self._master.update()
        self._master.after(200, lambda: self._mostrar_tela("inicio"))

        # Atalhos de teclado — controle geral
        self._master.bind("<F5>",         lambda e: self._reload_tela())
        self._master.bind("<Control-r>",  lambda e: self._reload_tela())
        self._master.bind("<Control-F5>", lambda e: self._reiniciar_app())
        self._master.bind("<F11>",        lambda e: self._toggle_fullscreen())

        # Atalhos de teclado — navegação (Ctrl+1..9+0)
        _nav_atalhos = {
            "1": "inicio",  "2": "projetos",   "3": "gerar",
            "4": "cenas",   "6": "preview",
            "7": "templates","9": "imagens",
            "0": "config",
        }
        for _k, _t in _nav_atalhos.items():
            self._master.bind(f"<Control-Key-{_k}>",
                              lambda e, t=_t: self._mostrar_tela(t))

    # ------------------------------------------------------------------
    # Estrutura principal
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Status bar PRIMEIRO (side="bottom") para funcionar corretamente no tkinter
        self._status_bar = ctk.CTkFrame(self._master, height=28, fg_color=BG4,
                                        corner_radius=0)
        self._status_bar.pack(fill="x", side="bottom")
        self._status_bar.pack_propagate(False)
        self._build_status_bar()

        # Wrapper: sidebar + conteúdo
        main_wrapper = ctk.CTkFrame(self._master, fg_color=BG, corner_radius=0)
        main_wrapper.pack(fill="both", expand=True)

        # Sidebar
        self._sidebar = ctk.CTkFrame(main_wrapper, width=SIDEBAR_W,
                                     fg_color=BG2, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Separador vertical entre sidebar e conteúdo
        ctk.CTkFrame(main_wrapper, width=1, fg_color=BORDER).pack(side="left", fill="y")

        # Área de conteúdo
        content_wrapper = ctk.CTkFrame(main_wrapper, fg_color=BG, corner_radius=0)
        content_wrapper.pack(side="left", fill="both", expand=True)

        self._content = ctk.CTkFrame(content_wrapper, fg_color=BG, corner_radius=0)
        self._content.pack(fill="both", expand=True)

        # Frames das telas — construídos um a um para manter o event loop
        # responsivo durante o carregamento (evita "não respondendo")
        self._telas: dict[str, ctk.CTkFrame] = {}
        for _chave, _cls in [
            ("inicio",     TelaDashboard),
            ("projetos",   TelaGerenciarProjetos),
            ("gerar",      TelaGerarVideo),
            ("cenas",      TelaCenas),
            ("preview",    TelaPreview),
            ("templates",  _gt.TelaTemplates),
            ("config",     TelaConfiguracoes),
            ("videos",     TelaMeusVideos),
        ]:
            self._telas[_chave] = _cls(self._content, self)
            self._master.update()
        if self._user.get("is_admin"):
            self._telas["admin"] = TelaAdmin(self._content, self)
            self._master.update()

        # Painel flutuante do assistente
        self._painel_assistente = _gaj.PainelAssistente(self._content)
        # Sobrescreve o comando do botão "ajuda" (painel já existe aqui)
        self._fixar_btn_assistente()

    def _build_status_bar(self):
        sb = self._status_bar
        ctk.CTkLabel(sb, text=f"GeradorBB v{_versao_local()}",
                     font=(FONT_FAMILY, 10), text_color=SUBTEXT).pack(side="left", padx=12)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="left", fill="y", pady=6)
        self._proj_status_lbl = ctk.CTkLabel(
            sb, text=f"  {_projeto_ativo()}",
            font=(FONT_FAMILY, 10, "bold"), text_color=INFO)
        self._proj_status_lbl.pack(side="left", padx=(4, 0))
        self._status_lbl = ctk.CTkLabel(sb, text="Pronto",
                                        font=(FONT_FAMILY, 10), text_color=SUCCESS)
        self._status_lbl.pack(side="right", padx=8)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="right", fill="y", pady=6)
        self._clock_lbl = ctk.CTkLabel(sb, text="",
                                       font=(FONT_FAMILY, 10), text_color=SUBTEXT)
        self._clock_lbl.pack(side="right", padx=(0, 8))
        ctk.CTkFrame(sb, width=1, fg_color=BORDER).pack(side="right", fill="y", pady=6)
        self._atualizar_relogio()

    def _atualizar_relogio(self):
        agora = datetime.datetime.now().strftime("%H:%M:%S")
        self._clock_lbl.configure(text=agora)
        self._master.after(1000, self._atualizar_relogio)

    def _toggle_fullscreen(self):
        """F11 — alterna entre janela maximizada e normal."""
        try:
            if self._master.state() == "zoomed":
                self._master.state("normal")
                self._fs_btn.configure(
                    text="  ⛶   Tela cheia  (F11)", text_color=SUBTEXT)
            else:
                self._master.state("zoomed")
                self._fs_btn.configure(
                    text="  ⊟   Janela  (F11)", text_color=INFO)
        except Exception:
            pass

    def set_status(self, texto: str, cor: str = SUCCESS):
        """Atualiza o texto da status bar — chamado pelas telas filhas."""
        try:
            self._status_lbl.configure(text=texto, text_color=cor)
        except Exception:
            pass

    def _build_sidebar(self):
        sb = self._sidebar

        # ── Faixa de marca no topo ─────────────────────────────────────────────
        topo = ctk.CTkFrame(sb, fg_color=ACCENT, corner_radius=0, height=4)
        topo.pack(fill="x")
        topo.pack_propagate(False)

        # ── Logo / Brand ───────────────────────────────────────────────────────
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=PAD, pady=(16, 0))
        ctk.CTkLabel(brand, text="GeradorBB",
                     font=(FONT_FAMILY, 20, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(brand, text=f" v{_versao_local()}",
                     font=(FONT_FAMILY, 10),
                     text_color=SUBTEXT).pack(side="left", pady=(6, 0))

        _sep(sb).pack(fill="x", padx=PAD, pady=(12, 0))

        # ── Perfil ─────────────────────────────────────────────────────────────
        perfil = ctk.CTkFrame(sb, fg_color=BG2, corner_radius=CORNER_R,
                              border_width=1, border_color=BORDER)
        perfil.pack(fill="x", padx=10, pady=(10, 0))

        perfil_inner = ctk.CTkFrame(perfil, fg_color="transparent")
        perfil_inner.pack(fill="x", padx=12, pady=10)

        # Avatar
        avatar_frame = ctk.CTkFrame(perfil_inner, width=46, height=46,
                                    corner_radius=23, fg_color=ACCENT,
                                    border_width=2, border_color=ACCENT2)
        avatar_frame.pack_propagate(False)
        avatar_frame.pack(side="left")
        inicial = (self._user.get("nome") or "?")[0].upper()
        ctk.CTkLabel(avatar_frame, text=inicial,
                     font=(FONT_FAMILY, 20, "bold"),
                     text_color=TEXT).place(relx=0.5, rely=0.5, anchor="center")

        # Info do usuário
        info_col = ctk.CTkFrame(perfil_inner, fg_color="transparent")
        info_col.pack(side="left", padx=(10, 0), fill="x", expand=True)

        nome = self._user.get("nome", "Usuário")
        ctk.CTkLabel(info_col, text=nome,
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")

        badge_txt, badge_cor = self._badge_licenca()
        ctk.CTkLabel(info_col, text=badge_txt,
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=badge_cor, anchor="w").pack(anchor="w")

        # ── Projeto ────────────────────────────────────────────────────────────
        proj_card = ctk.CTkFrame(sb, fg_color=BG2, corner_radius=CORNER_R,
                                 border_width=1, border_color=BORDER)
        proj_card.pack(fill="x", padx=10, pady=(8, 0))

        proj_inner = ctk.CTkFrame(proj_card, fg_color="transparent")
        proj_inner.pack(fill="x", padx=12, pady=(8, 8))

        ctk.CTkLabel(proj_inner, text="CANAL",
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=SUBTEXT).pack(anchor="w", pady=(0, 4))

        proj_row = ctk.CTkFrame(proj_inner, fg_color="transparent")
        proj_row.pack(fill="x")

        projetos = _listar_projetos() or ["default"]
        ativo = _projeto_ativo()
        if ativo not in projetos:
            projetos = [ativo] + projetos

        self._seletor_proj = ctk.CTkOptionMenu(
            proj_row,
            values=projetos,
            command=self._trocar_projeto,
            width=SIDEBAR_W - 80,
            height=30,
            fg_color=BG3,
            button_color=ACCENT,
            button_hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            corner_radius=8,
        )
        self._seletor_proj.set(ativo)
        self._seletor_proj.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            proj_row, text="+",
            command=lambda: self._mostrar_tela("projetos"),
            width=28, height=30,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(side="left", padx=(4, 0))

        # ── Navegação ──────────────────────────────────────────────────────────
        _sep(sb).pack(fill="x", padx=10, pady=(12, 8))

        # Nav: strings = rótulo de grupo; tuplas = item navegável
        nav_items = [
            "GERAL",
            ("inicio",     "🏠", "Início",           None,  "1"),
            ("projetos",   "📺", "Canais",             None,  "2"),
            "PRODUÇÃO",
            ("gerar",      "🎬", "Gerar Vídeo",       ACCENT,"3"),
            ("cenas",      "🎞️", "Organizar Cenas",   None,  "4"),
            ("preview",    "👁️", "Preview Layout",    None,  "6"),
            ("templates",  "📋", "Templates",         None,  "7"),
            "SISTEMA",
            ("videos",     "📁", "Meus Vídeos",       None,  None),
            ("config",     "⚙️", "Configurações",     None,  "0"),
            ("ajuda",      "💬", "Assistente",        None,  None),
        ]
        if self._user.get("is_admin"):
            nav_items += ["ADMIN", ("admin", "🛡️", "Painel Admin", WARNING, None)]

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._nav_indicators: dict[str, ctk.CTkFrame] = {}

        for item in nav_items:
            if item is None:
                ctk.CTkFrame(sb, height=1, fg_color=BORDER).pack(
                    fill="x", padx=14, pady=3)
                continue
            if isinstance(item, str):
                grp = ctk.CTkFrame(sb, fg_color="transparent")
                grp.pack(fill="x", padx=16, pady=(8, 1))
                ctk.CTkLabel(grp, text=item,
                             font=(FONT_FAMILY, 8, "bold"),
                             text_color=BORDER2).pack(side="left")
                continue
            # item é tupla (chave, icone, rotulo, cor_destaque[, shortcut])
            if len(item) == 5:
                chave, icone, rotulo, cor_destaque, sc = item
            else:
                chave, icone, rotulo, cor_destaque = item
                sc = None

            row = ctk.CTkFrame(sb, fg_color="transparent", height=40)
            row.pack(fill="x", padx=6, pady=1)
            row.pack_propagate(False)

            indicator = ctk.CTkFrame(row, width=3, fg_color="transparent",
                                     corner_radius=2)
            indicator.pack(side="left", fill="y", padx=(2, 0))
            self._nav_indicators[chave] = indicator

            if sc:
                ctk.CTkLabel(row, text=f"^{sc}",
                             font=(FONT_FAMILY, 8),
                             text_color=BORDER2,
                             width=24).pack(side="right", padx=(0, 6))

            btn = ctk.CTkButton(
                row,
                text=f"  {icone}   {rotulo}",
                command=lambda c=chave: self._mostrar_tela(c),
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                hover_color=BG3,
                text_color=cor_destaque if cor_destaque else SUBTEXT,
                font=(FONT_FAMILY, FONT_SIZE_MD),
            )
            btn.pack(side="left", fill="both", expand=True)
            self._nav_btns[chave] = btn

        # ── Rodapé da sidebar ──────────────────────────────────────────────────
        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="y", expand=True)
        _sep(sb).pack(fill="x", padx=10, pady=(0, 4))

        # Botão janela/tela cheia
        self._fs_btn = ctk.CTkButton(
            sb, text="  ⛶   Tela cheia  (F11)",
            command=self._toggle_fullscreen,
            height=36, anchor="w", corner_radius=8,
            fg_color="transparent", hover_color=BG3,
            text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        self._fs_btn.pack(fill="x", padx=6, pady=(0, 2))

        bottom_row = ctk.CTkFrame(sb, fg_color="transparent")
        bottom_row.pack(fill="x", padx=6, pady=(0, 10))

        sair_btn = ctk.CTkButton(
            bottom_row, text="  ⏻  Sair",
            command=self._sair,
            height=36, anchor="w",
            corner_radius=8,
            fg_color="transparent",
            hover_color=ACCENT_GHOST_HOVER,
            text_color=SUBTEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        sair_btn.pack(fill="x")
        sair_btn.bind("<Enter>", lambda _: sair_btn.configure(text_color=DANGER))
        sair_btn.bind("<Leave>", lambda _: sair_btn.configure(text_color=SUBTEXT))

    def _trocar_projeto(self, nome: str):
        cfg = _carregar_config()
        cfg["projeto_ativo"] = nome
        _salvar_config(cfg)
        try:
            self._proj_status_lbl.configure(text=f"  {nome}")
        except Exception:
            pass
        # Recarrega a tela atual
        if self._tela_atual and hasattr(self._telas.get(self._tela_atual, None), "ao_exibir"):
            self._telas[self._tela_atual].ao_exibir()

    def _atualizar_seletor_projeto(self):
        projetos = _listar_projetos() or ["default"]
        ativo = _projeto_ativo()
        if ativo not in projetos:
            projetos = [ativo] + projetos
        try:
            self._seletor_proj.configure(values=projetos)
            self._seletor_proj.set(ativo)
        except Exception:
            pass

    def _badge_licenca(self) -> tuple[str, str]:
        if self._user.get("is_admin"):
            return ("★ Administrador", ACCENT)
        lic = self._licenca
        if lic.get("tipo") == "vitalicio":
            return ("✓ Vitalício", SUCCESS)
        dias = lic.get("dias_restantes")
        if dias is None:
            return ("✗ Sem licença", DANGER)
        if dias <= 7:
            return (f"⚠ {dias} dias restantes", DANGER)
        if dias <= 15:
            return (f"⏳ {dias} dias restantes", WARNING)
        return (f"✓ {dias} dias restantes", SUCCESS)

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    def _mostrar_tela(self, chave: str):
        if chave not in self._telas:
            return  # itens de painel (ex: "ajuda") não têm tela
        if self._tela_atual == chave:
            return
        # Esconde todas
        for t in self._telas.values():
            t.pack_forget()
        # Atualiza estilo dos botões de nav
        _nav_cores = {
            "gerar": ACCENT,
            "admin": WARNING,
        }
        for k, btn in self._nav_btns.items():
            if k == chave:
                btn.configure(fg_color=BG3, text_color=TEXT)
                self._nav_indicators[k].configure(fg_color=ACCENT)
            else:
                btn.configure(fg_color="transparent",
                              text_color=_nav_cores.get(k, SUBTEXT))
                self._nav_indicators[k].configure(fg_color="transparent")
        # Mostra a tela selecionada
        self._telas[chave].pack(fill="both", expand=True)
        self._tela_atual = chave
        self._master.update_idletasks()
        # Recarrega se a tela suportar
        if hasattr(self._telas[chave], "ao_exibir"):
            self._telas[chave].ao_exibir()

    # ------------------------------------------------------------------
    # Ações globais
    # ------------------------------------------------------------------

    def _reload_tela(self):
        """F5 / Ctrl+R — recarrega a tela atual (chama ao_exibir se existir)."""
        chave = self._tela_atual
        if not chave:
            return
        tela = self._telas.get(chave)
        if tela and hasattr(tela, "ao_exibir"):
            tela.ao_exibir()
            self.set_status("Tela recarregada", SUCCESS)
        else:
            self.set_status("Nada para recarregar", SUBTEXT)

    def _reiniciar_app(self):
        """Ctrl+F5 — relança o processo Python do zero (recarrega todo o código)."""
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    def _fixar_btn_assistente(self):
        btn = self._nav_btns.get("ajuda")
        if btn:
            btn.configure(command=lambda: self._painel_assistente.toggle(self._content))

    def _sair(self):
        auth.logout()
        sys.exit(0)


def _garantir_ffmpeg(on_progresso=None) -> bool:
    """
    Garante que o FFmpeg esteja disponível.
    Ordem de busca:
      1. PATH do sistema
      2. Bundleado junto ao .exe (_internal/ffmpeg.exe ou pasta do exe)
      3. Instalação prévia em DATA_DIR/ffmpeg/
      4. Download direto dos binários (sem depender de winget)
    on_progresso(pct, texto) é chamado durante o download (pct 0..100).
    Retorna True se encontrado/instalado, False se falhou.
    """
    import shutil as _sh

    # 1. Já está no PATH?
    if _sh.which("ffmpeg"):
        return True

    # 2. Bundleado com o .exe?
    for candidato in (
        APP_DIR / "_internal" / "ffmpeg.exe",
        APP_DIR / "ffmpeg.exe",
    ):
        if candidato.exists():
            os.environ["PATH"] = str(candidato.parent) + os.pathsep + os.environ.get("PATH", "")
            return True

    # 3. Instalado anteriormente em DATA_DIR/ffmpeg/
    ff_local = DATA_DIR / "ffmpeg" / "ffmpeg.exe"
    if ff_local.exists():
        os.environ["PATH"] = str(ff_local.parent) + os.pathsep + os.environ.get("PATH", "")
        return True

    # 4. Download direto — sem winget, funciona em qualquer Windows
    try:
        import urllib.request
        import zipfile

        URL_FFMPEG = (
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        )
        ffmpeg_dir = DATA_DIR / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        zip_path = DATA_DIR / "_ffmpeg_setup.zip"

        if on_progresso:
            on_progresso(0, "Conectando ao servidor...")

        def _hook(bloco, tam_bloco, tam_total):
            if on_progresso and tam_total > 0:
                pct = min(98, int(bloco * tam_bloco * 100 / tam_total))
                mb_feito = bloco * tam_bloco / 1_048_576
                mb_total = tam_total / 1_048_576
                on_progresso(pct, f"Baixando... {mb_feito:.0f} MB / {mb_total:.0f} MB")

        urllib.request.urlretrieve(URL_FFMPEG, zip_path, reporthook=_hook)

        if on_progresso:
            on_progresso(99, "Extraindo arquivos...")

        # Extrai apenas ffmpeg.exe e ffprobe.exe do zip
        with zipfile.ZipFile(zip_path, "r") as z:
            for nome in z.namelist():
                base = nome.rsplit("/", 1)[-1]
                if base in ("ffmpeg.exe", "ffprobe.exe"):
                    data = z.read(nome)
                    (ffmpeg_dir / base).write_bytes(data)

        try:
            zip_path.unlink()
        except Exception:
            pass

        if (ffmpeg_dir / "ffmpeg.exe").exists():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
            if on_progresso:
                on_progresso(100, "FFmpeg instalado com sucesso!")
            return True

    except Exception:
        pass

    return False


def _whisper_modelo_cacheado() -> bool:
    """Retorna True se o modelo Whisper configurado já está no cache local."""
    cfg = _carregar_config()
    modelo = cfg.get("whisper_modelo", "small")
    cache_hub = DATA_DIR / "cache" / "torch" / "hub"
    model_dir = cache_hub / f"models--Systran--faster-whisper-{modelo}"
    snapshots = model_dir / "snapshots"
    if not snapshots.exists():
        return False
    try:
        return any(snapshots.iterdir())
    except Exception:
        return False


def _verificar_whisper(master):
    """
    Verifica se o modelo Whisper (IA de transcrição) está cacheado.
    Se não estiver, faz o download em background mostrando progresso.
    Só precisa baixar uma vez — fica salvo em Documents/GeradorBB/cache/.
    """
    import tkinter.messagebox as _mb

    # Garante que HF_HOME aponte para nosso cache persistente
    whisper_cache = DATA_DIR / "cache" / "torch"
    os.environ.setdefault("HF_HOME",    str(whisper_cache))
    os.environ.setdefault("TORCH_HOME", str(whisper_cache))

    if _whisper_modelo_cacheado():
        return

    cfg = _carregar_config()
    modelo = cfg.get("whisper_modelo", "small")
    tamanhos = {"tiny": "~75 MB", "base": "~145 MB", "small": "~300 MB",
                "medium": "~1.5 GB", "large": "~3 GB"}
    tam_str = tamanhos.get(modelo, "~300 MB")

    # ── Popup de download ─────────────────────────────────────────────────────
    popup = ctk.CTkToplevel(master)
    popup.title("GeradorBB — Configuração Inicial")
    popup.geometry("440x240")
    popup.resizable(False, False)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)

    ctk.CTkLabel(
        popup, text=f"🤖  Baixando modelo de inteligência artificial ({tam_str})... (2/3)",
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=TEXT,
    ).pack(pady=(24, 4))
    ctk.CTkLabel(
        popup, text="Modelo de transcrição de áudio. Só acontece uma vez.",
        font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
    ).pack(pady=(0, 10))

    lbl_status = ctk.CTkLabel(
        popup, text="Conectando ao servidor...",
        font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
    )
    lbl_status.pack()

    bar = ctk.CTkProgressBar(popup, height=16, corner_radius=6, mode="indeterminate")
    bar.pack(fill="x", padx=28, pady=10)
    bar.start()

    lbl_mb = ctk.CTkLabel(
        popup, text="Não feche o app durante o download.",
        font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
    )
    lbl_mb.pack()
    popup.update()

    def _atualizar_status(msg):
        master.after(0, lambda: lbl_status.configure(text=msg))

    def _atualizar_mb():
        """Mostra quantos MB foram baixados, lendo o diretório de cache."""
        try:
            hub_dir = whisper_cache / "hub" / f"models--Systran--faster-whisper-{modelo}"
            if hub_dir.exists():
                total = sum(f.stat().st_size for f in hub_dir.rglob("*") if f.is_file())
                master.after(0, lambda: lbl_mb.configure(
                    text=f"Baixando... {total / 1_048_576:.0f} MB recebidos de {tam_str}"
                ))
        except Exception:
            pass
        if popup.winfo_exists():
            master.after(2000, _atualizar_mb)

    def _baixar():
        erro_msg = ""
        try:
            _atualizar_status("Conectando ao servidor de modelos...")
            # Usa huggingface_hub (já é dep transitiva de faster-whisper)
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{modelo}",
                    cache_dir=str(whisper_cache / "hub"),
                    local_files_only=False,
                    ignore_patterns=["*.bin.index.json"],
                )
            except Exception:
                # Fallback: instancia WhisperModel (baixa e descarta da RAM)
                _atualizar_status("Baixando modelo de inteligência artificial...")
                from faster_whisper import WhisperModel
                WhisperModel(modelo, device="cpu", compute_type="int8")
                del WhisperModel

            _atualizar_status("✅  Configuração concluída!")
        except Exception as e:
            erro_msg = str(e)

        def _ui():
            bar.stop()
            popup.destroy()
            if erro_msg:
                _mb.showwarning(
                    "GeradorBB — Configuração",
                    "Não foi possível baixar o modelo de IA automaticamente.\n\n"
                    "Verifique sua conexão com a internet e reinicie o GeradorBB.\n\n"
                    "Se o problema persistir, entre em contato com o suporte."
                )
        master.after(0, _ui)

    threading.Thread(target=_baixar, daemon=True).start()
    master.after(3000, _atualizar_mb)




def _verificar_ambiente(master):
    """
    Verifica/instala dependências na primeira vez:
    1. FFmpeg  — baixa ~80 MB com barra de progresso real
    2. Whisper — baixa modelo de IA ~300 MB (encadeado após FFmpeg)
    3. Kokoro  — instala motor de voz offline ~300 MB (encadeado após Whisper)
    A verificação inicial roda em background para não bloquear a UI.
    """
    import tkinter.messagebox as _mb

    # ── Primeiro acesso ────────────────────────────────────────────────────────
    if _PRIMEIRO_ACESSO:
        master.after(800, lambda: _mb.showinfo(
            "GeradorBB",
            "✅  Ambiente configurado com sucesso!\n\n"
            f"Seus arquivos ficam em:\n{DATA_DIR}\n\n"
            "Você pode acessar essa pasta diretamente\n"
            "pelo Explorador de Arquivos > Documentos > GeradorBB"
        ))

    # ── Verificação de FFmpeg em background (não bloqueia a UI) ───────────────
    def _checar_ffmpeg():
        import shutil as _sh
        ffmpeg_ok = bool(_sh.which("ffmpeg"))
        if not ffmpeg_ok:
            ff_local = DATA_DIR / "ffmpeg" / "ffmpeg.exe"
            if ff_local.exists():
                os.environ["PATH"] = (
                    str(ff_local.parent) + os.pathsep + os.environ.get("PATH", "")
                )
                ffmpeg_ok = True
        if ffmpeg_ok:
            master.after(0, lambda: _verificar_whisper(master))
        else:
            master.after(0, lambda: _mostrar_popup_ffmpeg(master))

    threading.Thread(target=_checar_ffmpeg, daemon=True).start()
    return

def _mostrar_popup_ffmpeg(master):
    """Popup de download do FFmpeg — chamado da thread de verificação."""
    import tkinter.messagebox as _mb

    popup = ctk.CTkToplevel(master)
    popup.title("GeradorBB — Configuração Inicial")
    popup.geometry("420x220")
    popup.resizable(False, False)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)

    ctk.CTkLabel(
        popup, text="⚙️  Baixando componentes de áudio... (1/3)",
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=TEXT,
    ).pack(pady=(28, 4))
    ctk.CTkLabel(
        popup, text="Configurando o GeradorBB pela primeira vez. Não feche o app.",
        font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
    ).pack(pady=(0, 12))

    lbl_status = ctk.CTkLabel(
        popup, text="Conectando...",
        font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
    )
    lbl_status.pack()

    bar = ctk.CTkProgressBar(popup, height=16, corner_radius=6)
    bar.set(0)
    bar.pack(fill="x", padx=28, pady=10)

    lbl_pct = ctk.CTkLabel(
        popup, text="0%",
        font=(FONT_FAMILY, FONT_SIZE_SM, "bold"), text_color=TEXT,
    )
    lbl_pct.pack()
    popup.update()

    def _progresso(pct, texto):
        def _ui():
            bar.set(pct / 100)
            lbl_pct.configure(text=f"{pct}%")
            lbl_status.configure(text=texto)
            popup.update()
        master.after(0, _ui)

    def _instalar():
        ok = _garantir_ffmpeg(on_progresso=_progresso)
        def _ui():
            popup.destroy()
            if not ok:
                _mb.showwarning(
                    "GeradorBB — FFmpeg",
                    "Não foi possível baixar os componentes de áudio automaticamente.\n\n"
                    "Verifique sua conexão com a internet e reinicie o GeradorBB.\n\n"
                    "Se o problema persistir, entre em contato com o suporte."
                )
            else:
                master.after(500, lambda: _verificar_whisper(master))
        master.after(0, _ui)

    threading.Thread(target=_instalar, daemon=True).start()


def construir_principal(master, user: dict, licenca: dict):
    """Constrói a UI principal dentro da janela `master` existente."""
    ctrl = _PrincipalController(master, user, licenca)
    master.after(1000, lambda: _verificar_ambiente(master))
    return ctrl


# ===========================================================================
# Header reutilizável de seção
# ===========================================================================

class SectionHeader(ctk.CTkFrame):
    """Barra horizontal de cabeçalho da área de conteúdo."""

    def __init__(self, master, icone: str, titulo: str, subtitulo: str = ""):
        super().__init__(master, fg_color=BG3, corner_radius=0,
                         border_width=0, height=72)
        self.pack_propagate(False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")

        ctk.CTkLabel(inner, text=icone,
                     font=(FONT_FAMILY, 28)).pack(side="left", padx=(0, 12))

        txt_col = ctk.CTkFrame(inner, fg_color="transparent")
        txt_col.pack(side="left")
        ctk.CTkLabel(txt_col, text=titulo,
                     font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
                     text_color=TEXT).pack(anchor="w")
        if subtitulo:
            ctk.CTkLabel(txt_col, text=subtitulo,
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=SUBTEXT).pack(anchor="w")


# ===========================================================================
# Tela: Dashboard (Início)
# ===========================================================================

class TelaDashboard(ctk.CTkFrame):
    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela = janela
        self._build_ui()

    def _build_ui(self):
        def _ir(tela):
            if hasattr(self._janela, "_mostrar_tela"):
                self._janela._mostrar_tela(tela)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0,
                                        scrollbar_button_color=BG3,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(scroll, fg_color="transparent")
        inner.pack(fill="x", padx=32, pady=24)

        # ── Hero ──────────────────────────────────────────────────────────────
        hero = ctk.CTkFrame(inner, fg_color=BG2, corner_radius=12,
                            border_width=1, border_color=BORDER)
        hero.pack(fill="x", pady=(0, 20))
        ctk.CTkFrame(hero, fg_color=ACCENT, height=3, corner_radius=0).pack(fill="x")

        hb = ctk.CTkFrame(hero, fg_color="transparent")
        hb.pack(fill="x", padx=24, pady=20)
        hb.columnconfigure(0, weight=1)

        hl = ctk.CTkFrame(hb, fg_color="transparent")
        hl.grid(row=0, column=0, sticky="w")
        nome = self._janela._user.get("nome", "Usuário")
        ctk.CTkLabel(hl, text=f"Olá, {nome}",
                     font=(FONT_FAMILY, 26, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(hl, text="Crie vídeos verticais automáticos em PT e EN.",
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT, anchor="w").pack(anchor="w", pady=(3, 16))
        ctk.CTkButton(hl, text="▶  Gerar Vídeo Agora",
                      command=lambda: _ir("gerar"),
                      height=42, width=200,
                      fg_color=ACCENT, hover_color=ACCENT3,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_MD, "bold")).pack(anchor="w")

        lic = self._janela._licenca
        if lic.get("tipo") == "vitalicio":
            lic_txt, lic_cor = "Vitalício", SUCCESS
        elif lic.get("dias_restantes") is not None:
            d = lic["dias_restantes"]
            lic_cor = DANGER if d <= 7 else WARNING if d <= 15 else SUCCESS
            lic_txt = f"{d} dias restantes"
        else:
            lic_txt, lic_cor = "Sem licença", DANGER

        hr = ctk.CTkFrame(hb, fg_color=BG3, corner_radius=8,
                          border_width=1, border_color=lic_cor)
        hr.grid(row=0, column=1, sticky="ne", padx=(20, 0))
        ctk.CTkLabel(hr, text="LICENÇA", font=(FONT_FAMILY, 8, "bold"),
                     text_color=SUBTEXT).pack(padx=18, pady=(12, 2))
        ctk.CTkLabel(hr, text=lic_txt,
                     font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
                     text_color=lic_cor).pack(padx=18, pady=(0, 12))

        # ── Prontidão + Projeto ───────────────────────────────────────────────
        mid = ctk.CTkFrame(inner, fg_color="transparent")
        mid.pack(fill="x", pady=(0, 20))
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=0)

        # Card de prontidão (esquerda)
        chk_card = ctk.CTkFrame(mid, fg_color=BG2, corner_radius=12,
                                border_width=1, border_color=BORDER)
        chk_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        chk_top = ctk.CTkFrame(chk_card, fg_color="transparent")
        chk_top.pack(fill="x", padx=18, pady=(16, 12))
        ctk.CTkLabel(chk_top, text="Prontidão para geração",
                     font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
                     text_color=TEXT).pack(side="left")
        self._chk_status_lbl = ctk.CTkLabel(chk_top, text="",
                                             font=(FONT_FAMILY, FONT_SIZE_SM),
                                             text_color=SUBTEXT)
        self._chk_status_lbl.pack(side="left", padx=10)
        ctk.CTkButton(chk_top, text="▶  Gerar",
                      command=lambda: _ir("gerar"),
                      height=30, width=88,
                      fg_color=ACCENT, hover_color=ACCENT3,
                      text_color=TEXT, corner_radius=6,
                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold")).pack(side="right")

        # Separador
        ctk.CTkFrame(chk_card, fg_color=BORDER, height=1).pack(fill="x", padx=18)

        # Grid de pastas do projeto (3 colunas × 3 linhas)
        self._chk_items: dict[str, dict] = {}
        _pastas_grid = [
            ("audio",      "🔊", "Áudio"),
            ("bordas",     "🔲", "Bordas"),
            ("cenas",      "🎞️", "Cenas"),
            ("imagens",    "🖼️", "Imagens"),
            ("logos",      "🏷️", "Logos"),
            ("musica",     "🎵", "Música"),
            ("personagem", "🎭", "Personagem"),
            ("roteiro",    "📝", "Roteiro"),
            ("temas",      "🎨", "Temas"),
        ]

        def _abrir_pasta_projeto(subfolder: str):
            p = _projeto_dir() / "projeto" / subfolder
            p.mkdir(parents=True, exist_ok=True)
            os.startfile(str(p))

        grid_frame = ctk.CTkFrame(chk_card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=14, pady=(10, 14))
        for col in range(3):
            grid_frame.columnconfigure(col, weight=1)

        for idx, (key, icone, label) in enumerate(_pastas_grid):
            r, c = divmod(idx, 3)
            card = ctk.CTkFrame(grid_frame, fg_color=BG3, corner_radius=8,
                                border_width=1, border_color=BORDER)
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=8, pady=(8, 2))

            dot = ctk.CTkLabel(top_row, text="●", width=12,
                               font=(FONT_FAMILY, 10, "bold"),
                               text_color=BG4)
            dot.pack(side="left")

            ctk.CTkLabel(top_row, text=f"{icone} {label}",
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=TEXT, anchor="w").pack(side="left", padx=(4, 0))

            detalhe = ctk.CTkLabel(card, text="...",
                                   font=(FONT_FAMILY, 9),
                                   text_color=SUBTEXT, anchor="w")
            detalhe.pack(anchor="w", padx=8)

            ctk.CTkButton(card, text="📂 Abrir",
                          command=lambda k=key: _abrir_pasta_projeto(k),
                          height=22,
                          fg_color="transparent", hover_color=BG4,
                          text_color=SUBTEXT, corner_radius=4,
                          border_width=1, border_color=BORDER,
                          font=(FONT_FAMILY, 9)).pack(anchor="e", padx=8, pady=(4, 8))

            self._chk_items[key] = {"dot": dot, "detalhe": detalhe}

        # Card projeto ativo (direita)
        proj_card = ctk.CTkFrame(mid, fg_color=BG2, corner_radius=12,
                                 border_width=1, border_color=BORDER,
                                 width=220)
        proj_card.grid(row=0, column=1, sticky="nsew")
        proj_card.grid_propagate(False)

        ctk.CTkLabel(proj_card, text="CANAL ATIVO",
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=SUBTEXT).pack(anchor="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(proj_card, text=_projeto_ativo(),
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=ACCENT, wraplength=180,
                     justify="left").pack(anchor="w", padx=18)

        _tmpl_ativo = None
        try:
            import gui_templates as _gt_dash
            _cfg_dash = _carregar_config()
            _tid_dash = _cfg_dash.get("template_id", "")
            _tmpl_ativo = _gt_dash.carregar_template_por_id(_tid_dash)
            if not _tmpl_ativo:
                _todos = _gt_dash.carregar_templates()
                _tmpl_ativo = (next((t for t in _todos if t.get("padrao")), None)
                               or (_todos[0] if _todos else None))
        except Exception:
            pass

        ctk.CTkFrame(proj_card, fg_color=BORDER, height=1).pack(fill="x", padx=18, pady=(12, 10))
        ctk.CTkLabel(proj_card, text="TEMPLATE",
                     font=(FONT_FAMILY, 9, "bold"),
                     text_color=SUBTEXT).pack(anchor="w", padx=18)

        tmpl_nome = f"{_tmpl_ativo.get('icone','🎬')}  {_tmpl_ativo.get('nome','')}" if _tmpl_ativo else "Nenhum selecionado"
        tmpl_cor  = INFO if _tmpl_ativo else SUBTEXT
        ctk.CTkLabel(proj_card, text=tmpl_nome,
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=tmpl_cor).pack(anchor="w", padx=18, pady=(4, 0))

        ctk.CTkFrame(proj_card, fg_color="transparent").pack(expand=True, fill="both")

        ctk.CTkButton(proj_card, text="📂  Abrir pasta do projeto",
                      command=lambda: os.startfile(str(_projeto_dir()))
                                      if _projeto_dir().exists() else None,
                      height=30, anchor="w",
                      fg_color="transparent", hover_color=BG3,
                      border_color=BORDER, border_width=1,
                      text_color=TEXT, corner_radius=6,
                      font=(FONT_FAMILY, FONT_SIZE_SM)).pack(fill="x", padx=18, pady=(0, 18))

        # ── Últimas gerações ─────────────────────────────────────────────────
        ug_hdr = ctk.CTkFrame(inner, fg_color="transparent")
        ug_hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(ug_hdr, text="Últimas gerações",
                     font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(ug_hdr, text="Ver todos →",
                      command=lambda: _ir("videos"),
                      height=28, width=88,
                      fg_color="transparent", hover_color=BG3,
                      text_color=ACCENT, corner_radius=6,
                      border_width=0,
                      font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="right")

        self._ultimas_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._ultimas_frame.pack(fill="x", pady=(0, 8))

        # Dica rápida de atalhos
        dica = ctk.CTkFrame(inner, fg_color=BG2, corner_radius=8,
                            border_width=1, border_color=BORDER)
        dica.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(dica,
                     text="💡  Ctrl+3 Gerar  •  Ctrl+4 Cenas  •  Ctrl+6 Preview  •  F11 Tela cheia  •  F5 Recarregar",
                     font=(FONT_FAMILY, 10), text_color=SUBTEXT).pack(padx=16, pady=8)

        # Dicts de compatibilidade (usados em _atualizar_checklist/_atualizar_stats)
        self._stat_labels:  dict = {}
        self._chk_labels:   dict = {}
        self._chk_frames:   dict = {}

    def _atualizar_ultimas(self):
        """Mostra até 4 vídeos mais recentes."""
        for w in self._ultimas_frame.winfo_children():
            w.destroy()

        vid_dir = _videos_dir()
        videos: list[Path] = []
        if vid_dir.exists():
            videos = sorted(vid_dir.rglob("*.mp4"),
                            key=lambda p: p.stat().st_mtime, reverse=True)[:4]

        if not videos:
            ctk.CTkLabel(
                self._ultimas_frame,
                text="Nenhum vídeo gerado ainda. Clique em 'Gerar Vídeo' para começar!",
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=SUBTEXT,
            ).pack(anchor="w", pady=(0, 8))
            return

        grid = ctk.CTkFrame(self._ultimas_frame, fg_color="transparent")
        grid.pack(fill="x")
        for col in range(min(len(videos), 4)):
            grid.columnconfigure(col, weight=1)

        for col, vid in enumerate(videos):
            try:
                stat = vid.stat()
                data = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m  %H:%M")
                mb   = stat.st_size / (1024 * 1024)
            except Exception:
                data, mb = "—", 0

            # Detecta idioma pelo nome
            stem = vid.stem.lower()
            lang_cor  = INFO    if "_pt_" in stem or stem.endswith("_pt") else (
                         WARNING if "_en_" in stem or stem.endswith("_en") else SUBTEXT)
            lang_txt  = "PT" if "_pt_" in stem or stem.endswith("_pt") else (
                         "EN" if "_en_" in stem or stem.endswith("_en") else "—")

            card = ctk.CTkFrame(grid, fg_color=BG2, corner_radius=10,
                                border_width=1, border_color=BORDER,
                                cursor="hand2")
            card.grid(row=0, column=col, padx=(0, 8) if col < 3 else 0, sticky="ew")
            card.bind("<Button-1>", lambda e, p=vid: os.startfile(str(p)))

            # Topo colorido com badge de idioma
            top = ctk.CTkFrame(card, fg_color=BG3, corner_radius=0, height=52)
            top.pack(fill="x")
            top.pack_propagate(False)
            top.bind("<Button-1>", lambda e, p=vid: os.startfile(str(p)))
            ctk.CTkLabel(top, text="🎬", font=(FONT_FAMILY, 26)).place(relx=0.5, rely=0.5, anchor="center")

            badge = ctk.CTkFrame(top, fg_color=lang_cor, corner_radius=4, height=18, width=28)
            badge.place(relx=1.0, x=-8, y=6, anchor="ne")
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=lang_txt, font=(FONT_FAMILY, 8, "bold"),
                         text_color="#000000").place(relx=0.5, rely=0.5, anchor="center")

            # Nome do vídeo
            nome = vid.stem
            if len(nome) > 20:
                nome = nome[:19] + "…"
            ctk.CTkLabel(card, text=nome,
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=TEXT, wraplength=160,
                         justify="center").pack(padx=10, pady=(10, 2))
            ctk.CTkLabel(card, text=f"{data}   {mb:.0f} MB",
                         font=(FONT_FAMILY, 9),
                         text_color=SUBTEXT).pack(pady=(0, 12))

    def ao_exibir(self):
        self._atualizar_stats()
        self._atualizar_checklist()
        self._atualizar_ultimas()

    def _atualizar_checklist(self):
        """Verifica cada pasta do projeto e atualiza os cards."""
        proj_dir = _projeto_dir() / "projeto"
        _pastas = [
            "audio", "bordas", "cenas", "imagens",
            "logos", "musica", "personagem", "roteiro", "temas",
        ]

        n_ok = 0
        for key in _pastas:
            item = self._chk_items.get(key)
            if not item:
                continue
            pasta = proj_dir / key
            try:
                arquivos = [
                    f for f in pasta.iterdir()
                    if f.is_file() and not f.name.endswith("_config.json")
                ] if pasta.exists() else []
                n = len(arquivos)
            except Exception:
                n = 0

            ok = n > 0
            if ok:
                n_ok += 1
                item["dot"].configure(text_color=SUCCESS)
                item["detalhe"].configure(
                    text=f"{n} arquivo{'s' if n != 1 else ''}",
                    text_color=SUCCESS)
            else:
                item["dot"].configure(text_color=BG4)
                item["detalhe"].configure(text="Vazia", text_color=SUBTEXT)

        n_total = len(_pastas)
        try:
            if n_ok == n_total:
                self._chk_status_lbl.configure(
                    text="✓  Todas preenchidas", text_color=SUCCESS)
            else:
                vazias = n_total - n_ok
                self._chk_status_lbl.configure(
                    text=f"⚠  {vazias} pasta{'s' if vazias > 1 else ''} vazia{'s' if vazias > 1 else ''}",
                    text_color=WARNING if n_ok > 0 else SUBTEXT)
        except Exception:
            pass

    def _atualizar_stats(self):
        pass  # stats integrados no checklist


# ===========================================================================
# Tela: Gerar Vídeo
# ===========================================================================

class TelaGerarVideo(ctk.CTkFrame):
    def __init__(self, master, janela: JanelaPrincipal):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela  = janela
        self._proc    = None
        self._gerando = False
        self._build_ui()

    def _build_ui(self):
        # Header da seção
        header = SectionHeader(self, "🎬", "Gerar Vídeo",
                               "Verifique os arquivos e clique em Gerar.")
        header.pack(fill="x")

        # Separador
        _sep(self).pack(fill="x")

        # Área de conteúdo
        scroll = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=PAD * 2, pady=PAD)

        # ---- Atalho: Organizar Cenas ----
        cenas_banner = ctk.CTkFrame(scroll, fg_color=BG2, corner_radius=CORNER_R,
                                    border_width=1, border_color=ACCENT)
        cenas_banner.pack(fill="x", pady=(0, 16))
        cenas_inner = ctk.CTkFrame(cenas_banner, fg_color="transparent")
        cenas_inner.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(cenas_inner, text="🎞️  Antes de gerar:",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(cenas_inner,
                     text="  Organize as imagens de cada cena do roteiro",
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(side="left")
        ctk.CTkButton(
            cenas_inner, text="🎞️  Organizar Cenas →",
            command=lambda: self._janela._mostrar_tela("cenas")
                    if hasattr(self._janela, "_mostrar_tela") else None,
            height=32, width=180,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="right")

        # ---- Cards de status ----
        ctk.CTkLabel(scroll, text="Status dos arquivos",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=SUBTEXT).pack(anchor="w", pady=(0, 8))

        cards_row = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 20))
        cards_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="col")

        self._cards: dict[str, dict] = {}
        infos_cards = [
            ("imagens",    "🖼️",  "Imagens"),
            ("audio_pt",   "🔊",  "Áudio PT"),
            ("audio_en",   "🔊",  "Áudio EN"),
            ("roteiro_pt", "📄",  "Roteiro PT"),
            ("roteiro_en", "📄",  "Roteiro EN"),
        ]
        for col, (chave, icone, titulo) in enumerate(infos_cards):
            card_frame = ctk.CTkFrame(cards_row, fg_color=BG3,
                                      corner_radius=10,
                                      border_width=1, border_color=BORDER)
            card_frame.grid(row=0, column=col, padx=4, sticky="ew")

            # Ícone grande
            ctk.CTkLabel(card_frame, text=icone,
                         font=(FONT_FAMILY, 28)).pack(pady=(14, 0))

            # Label do card
            ctk.CTkLabel(card_frame, text=titulo,
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=SUBTEXT).pack()

            # Valor
            val_lbl = ctk.CTkLabel(card_frame, text="—",
                                   font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                                   text_color=WARNING)
            val_lbl.pack(pady=(4, 4))

            # Ícone de estado (✓ / ✗)
            estado_lbl = ctk.CTkLabel(card_frame, text="",
                                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                                      text_color=SUBTEXT)
            estado_lbl.pack(pady=(0, 10))

            self._cards[chave] = {
                "frame": card_frame,
                "val":   val_lbl,
                "estado": estado_lbl,
            }

        # ---- Seletor de Template ----
        self._seletor_template = _gt.SeletorTemplate(
            scroll,
            on_change=self._ao_trocar_template,
        )
        self._seletor_template.pack(fill="x", pady=(0, 10))
        # Carrega o template salvo no projeto
        _tid_salvo = _carregar_config().get("template_id", "")
        self._seletor_template.atualizar(_tid_salvo)

        # ---- Seletor de modelo de layout ----
        layout_row = ctk.CTkFrame(scroll, fg_color=BG2,
                                  corner_radius=CORNER_R,
                                  border_width=1, border_color=BORDER)
        layout_row.pack(fill="x", pady=(0, 10))
        layout_inner = ctk.CTkFrame(layout_row, fg_color="transparent")
        layout_inner.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(layout_inner, text="🎨  Modelo de layout:",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT).pack(side="left", padx=(0, 10))
        self._v_layout_modelo = ctk.StringVar(value="Padrão")
        self._menu_layout = ctk.CTkOptionMenu(
            layout_inner,
            variable=self._v_layout_modelo,
            values=["Padrão"],
            command=self._ao_selecionar_layout,
            width=200, height=32,
            fg_color=BG3, button_color=ACCENT,
            button_hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        )
        self._menu_layout.pack(side="left")
        ctk.CTkLabel(layout_inner,
                     text="  (posição de logo, legenda e personagem)",
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(side="left")

        # ---- Botões de ação ----
        btns_frame = ctk.CTkFrame(scroll, fg_color=BG2,
                                  corner_radius=CORNER_R,
                                  border_width=1, border_color=BORDER)
        btns_frame.pack(fill="x", pady=(0, 16))

        btns_inner = ctk.CTkFrame(btns_frame, fg_color="transparent")
        btns_inner.pack(fill="x", padx=16, pady=14)

        # Lado esquerdo: botões de geração
        btns_left = ctk.CTkFrame(btns_inner, fg_color="transparent")
        btns_left.pack(side="left")

        # Lado direito: botão auxiliar
        btns_right = ctk.CTkFrame(btns_inner, fg_color="transparent")
        btns_right.pack(side="right")

        ctk.CTkButton(
            btns_right, text="🎞️  Ajustar Cenas",
            command=lambda: self._janela._mostrar_tela("cenas"),
            height=50, width=160,
            fg_color="transparent", hover_color=BG3,
            border_color=INFO, border_width=1,
            text_color=INFO, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(side="left")

        self._btn_pt_en = ctk.CTkButton(
            btns_left, text="▶  Gerar PT + EN",
            command=lambda: self._iniciar("pt+en"),
            height=50, width=200,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
        )
        self._btn_pt_en.pack(side="left", padx=(0, 10))

        self._btn_pt = ctk.CTkButton(
            btns_left, text="▶  Só PT",
            command=lambda: self._iniciar("pt"),
            height=50, width=120,
            fg_color="transparent", hover_color=BG3,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        self._btn_pt.pack(side="left", padx=(0, 8))

        self._btn_en = ctk.CTkButton(
            btns_left, text="▶  Só EN",
            command=lambda: self._iniciar("en"),
            height=50, width=120,
            fg_color="transparent", hover_color=BG3,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        self._btn_en.pack(side="left", padx=(0, 8))

        self._btn_parar = ctk.CTkButton(
            btns_left, text="■  Parar",
            command=self._parar,
            height=50, width=100,
            fg_color=DANGER, hover_color=DANGER_HOVER,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            state="disabled",
        )
        self._btn_parar.pack(side="left")
        # Oculta o botão parar inicialmente
        self._btn_parar.pack_forget()

        self._label_status = _label(scroll, "Pronto.", size=FONT_SIZE_SM, color=SUBTEXT)
        self._label_status.pack(anchor="w", pady=(0, 4))

        # ---- Barra de progresso ----
        self._progress = ctk.CTkProgressBar(
            scroll, mode="indeterminate", height=6,
            fg_color=BG4, progress_color=ACCENT,
            corner_radius=3,
        )
        self._progress.pack(fill="x", pady=(0, 10))
        self._progress.pack_forget()  # oculta inicialmente

        # ---- Botão abrir pasta de vídeos (aparece após sucesso) ----
        self._btn_abrir_videos = ctk.CTkButton(
            scroll, text="📂  Abrir pasta de vídeos",
            command=lambda: os.startfile(str(_videos_dir()))
                            if _videos_dir().exists() else None,
            height=38, width=220,
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        # oculta inicialmente
        self._btn_abrir_videos.pack_forget()

        # ---- Log ----
        log_header = ctk.CTkFrame(scroll, fg_color="transparent")
        log_header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(log_header, text="📋  Log de execução",
                     font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
                     text_color=TEXT).pack(side="left")

        ctk.CTkButton(
            log_header, text="📋  Copiar",
            command=self._copiar_log,
            height=28, width=90,
            fg_color=BG2, hover_color=BG3,
            text_color=SUBTEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            log_header, text="🗑  Limpar",
            command=self._limpar_log,
            height=28, width=90,
            fg_color=BG2, hover_color=BG3,
            text_color=SUBTEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="right")

        self._log = ctk.CTkTextbox(
            scroll, height=240,
            fg_color=BG4, text_color=TEXT,
            font=FONT_MONO,
            corner_radius=CORNER_R,
            border_width=1, border_color=BORDER,
            state="disabled",
        )
        self._log.pack(fill="x")

        # Configura tags de cor no widget de texto
        self._log.tag_config("ok",      foreground=SUCCESS)
        self._log.tag_config("erro",    foreground=DANGER)
        self._log.tag_config("warning", foreground=WARNING)
        self._log.tag_config("normal",  foreground=TEXT)

    def ao_exibir(self):
        self._atualizar_cards()
        self._atualizar_menu_layout()
        try:
            _tid = _carregar_config().get("template_id", "")
            self._seletor_template.atualizar(_tid)
        except Exception:
            pass

    def _atualizar_menu_layout(self):
        d = _layouts_dir()
        d.mkdir(parents=True, exist_ok=True)
        nomes = ["Padrão"] + sorted(
            p.stem for p in d.glob("*.json") if p.stem != "Padrão"
        )
        self._menu_layout.configure(values=nomes)
        # Mantém seleção atual se ainda existe
        atual = self._v_layout_modelo.get()
        if atual not in nomes:
            self._v_layout_modelo.set("Padrão")

    def _ao_selecionar_layout(self, nome: str):
        _PADRAO_FIXO = {
            "logo_x": 20, "logo_y": 248, "logo_largura": 340,
            "posicao_legenda": 300, "tamanho_fonte": 64,
            "pers_lado": "esquerda", "pers_largura_pct": 0.22,
            "pers_margem_fundo": 40, "pers_margem_esq": 20, "pers_margem_dir": 20,
        }
        if nome == "Padrão":
            d = _PADRAO_FIXO
        else:
            p = _layouts_dir() / f"{nome}.json"
            if not p.exists():
                return
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return

        # Grava config_video.json
        cv = {
            "logo_x":          d.get("logo_x", 20),
            "logo_y":          d.get("logo_y", 248),
            "logo_largura":    d.get("logo_largura", 340),
            "logo_ativo":      d.get("logo_ativo", True),
            "posicao_legenda": d.get("posicao_legenda", 300),
            "tamanho_fonte":   d.get("tamanho_fonte", 64),
            "legenda_ativa":   d.get("legenda_ativa", True),
            "personagem_ativo":d.get("personagem_ativo", True),
            "borda_arquivo":   d.get("borda_arquivo", "Nenhuma"),
            "borda_ativa":     d.get("borda_ativa", False),
        }
        out = _projeto_dir() / "config_video.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cv, ensure_ascii=False, indent=2), encoding="utf-8")

        # Grava personagem_config.json + mascote_config.json
        pers_upd = {
            "lado":            d.get("pers_lado", "esquerda"),
            "largura_pct":     d.get("pers_largura_pct", 0.22),
            "margem_fundo":    d.get("pers_margem_fundo", 40),
            "margem_esquerda": d.get("pers_margem_esq", 20),
            "margem_direita":  d.get("pers_margem_dir", 20),
        }
        for cfg_path, defaults in ((_personagem_cfg_path(), _PERS_DEFAULTS),
                                   (_mascote_cfg_path(), _MASC_DEFAULTS)):
            existing = _ler_cfg_json(cfg_path, defaults)
            existing.update(pers_upd)
            _salvar_cfg_json(cfg_path, existing)

    def _atualizar_cards(self):
        # Resolve quantas imagens são esperadas baseado no template ativo
        tmpl = None
        try:
            tmpl = self._seletor_template.template_ativo()
        except Exception:
            pass

        if tmpl:
            tipo = tmpl.get("tipo", "livre")
            if tipo == "numerado":
                _esperado = tmpl.get("n_itens", 10)
            elif tipo == "secoes":
                _esperado = len([s for s in tmpl.get("secoes", []) if s.get("obrigatorio", True)])
                _esperado = max(_esperado, 1)
            else:  # livre
                _esperado = 1
            # Adiciona abertura e fechamento se ativos
            if tmpl.get("abertura"):
                _esperado += 1
            if tmpl.get("fechamento"):
                _esperado += 1
        else:
            _esperado = 12  # fallback legado

        # Imagens
        img_dir = _imagens_dir()
        n_img = 0
        if img_dir.exists():
            for ext in ("png", "jpg", "jpeg", "webp"):
                n_img += len(list(img_dir.glob(f"*.{ext}")))
        ok_img = n_img >= _esperado
        self._set_card("imagens", f"{n_img}/{_esperado}",
                       SUCCESS if ok_img else WARNING, ok_img)

        # Áudios
        audio_dir = _audio_dir()
        for lang in ("pt", "en"):
            encontrou = False
            if audio_dir.exists():
                for ext in ("mp3", "wav", "ogg", "m4a"):
                    if list(audio_dir.glob(f"*{lang}*.{ext}")):
                        encontrou = True
                        break
            self._set_card(f"audio_{lang}", "OK" if encontrou else "Falta",
                           SUCCESS if encontrou else WARNING, encontrou)

        # Roteiros
        rot_dir = _roteiro_dir()
        for lang in ("pt", "en"):
            encontrou = (rot_dir / f"roteiro_{lang}.txt").exists() if rot_dir.exists() else False
            self._set_card(f"roteiro_{lang}", "OK" if encontrou else "Falta",
                           SUCCESS if encontrou else WARNING, encontrou)

    def _set_card(self, chave, texto, cor, ok: bool | None = None):
        info = self._cards.get(chave)
        if not info:
            return
        info["val"].configure(text=texto, text_color=cor)
        # Borda e ícone de estado
        if ok is True:
            info["frame"].configure(border_color=SUCCESS)
            info["estado"].configure(text="✓ OK", text_color=SUCCESS)
        elif ok is False:
            info["frame"].configure(border_color=DANGER)
            info["estado"].configure(text="✗ Falta", text_color=DANGER)
        else:
            info["frame"].configure(border_color=WARNING)
            info["estado"].configure(text="⏳ ...", text_color=WARNING)

    # ---- Geração ----

    def _iniciar(self, modo: str):
        if self._gerando:
            return
        self._gerando = True
        self._limpar_log()
        self._set_btns_estado(False)
        self._label_status.configure(text="Gerando vídeo...", text_color=WARNING)
        if hasattr(self._janela, "set_status"):
            self._janela.set_status("Gerando vídeo...", WARNING)
        # Mostra progress bar, oculta botão de vídeos
        self._progress.pack(fill="x", pady=(0, 10), before=self._label_status)
        self._progress.start()
        self._btn_abrir_videos.pack_forget()

        t = threading.Thread(target=self._thread_gerar, args=(modo,), daemon=True)
        t.start()

    def _ao_trocar_template(self, template: dict):
        """Salva o template escolhido na config do projeto e atualiza os cards."""
        cfg = _carregar_config()
        cfg["template_id"] = template.get("id", "")
        _salvar_config(cfg)
        self._atualizar_cards()

    def _thread_gerar(self, modo: str):
        proj_dir = _projeto_dir()
        proj_dir.mkdir(parents=True, exist_ok=True)

        args_idioma = {
            "pt+en": ["--linguas", "pt", "en"],
            "pt":    ["--linguas", "pt"],
            "en":    ["--linguas", "en"],
        }.get(modo, [])

        # Exporta o template ativo para um arquivo que o engine vai ler
        args_template = []
        try:
            t = self._seletor_template.template_ativo()
            if t:
                tmpl_file = proj_dir / "template_ativo.json"
                tmpl_file.write_text(
                    json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                args_template = ["--template-file", str(tmpl_file)]
        except Exception as _e_tmpl:
            self._log_linha(f"[AVISO] Não foi possível carregar template: {_e_tmpl}", "warning")

        cmd = _engine_cmd(["--projeto-dir", str(proj_dir)] + args_idioma + args_template)

        # Ambiente herdado + variáveis essenciais para o subprocess
        _env = os.environ.copy()
        _env["PYTHONUNBUFFERED"]  = "1"   # força flush imediato de cada print()
        _env["PYTHONIOENCODING"]  = "utf-8"
        _env["PYTHONUTF8"]        = "1"
        _env["GERADORBB_DATA_DIR"] = str(DATA_DIR)  # cache persistente do Whisper

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,   # evita bloqueio em app sem console
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_env,
                cwd=str(_engine_dir()),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for linha in self._proc.stdout:
                self._log_linha(linha.rstrip())
            self._proc.wait()
            ok = self._proc.returncode == 0
        except Exception as e:
            self._log_linha(f"[ERRO] {e}", "erro")
            ok = False

        self._proc = None
        self._finalizar(ok, modo)

    def _finalizar(self, ok: bool, modo: str = "pt+en"):
        # Gera thumbnails em background antes de atualizar a UI
        if ok:
            proj_dir = _projeto_dir()
            def _thumbs():
                try:
                    from thumbnail import gerar_thumbnails_pos_geracao
                    gerar_thumbnails_pos_geracao(proj_dir, modo)
                except Exception:
                    pass
            threading.Thread(target=_thumbs, daemon=True).start()

        def _ui():
            self._gerando = False
            self._set_btns_estado(True)
            try:
                self._progress.stop()
            except Exception:
                pass
            try:
                self._progress.pack_forget()
            except Exception:
                pass
            if ok:
                self._label_status.configure(
                    text="Concluido com sucesso!", text_color=SUCCESS)
                if hasattr(self._janela, "set_status"):
                    self._janela.set_status("Concluido!", SUCCESS)
                self._btn_abrir_videos.pack(anchor="w", pady=(0, 10))
                _notificar_windows("GeradorBB", "Video gerado com sucesso!")
            else:
                self._label_status.configure(
                    text="Concluido com erros. Veja o log.", text_color=DANGER)
                if hasattr(self._janela, "set_status"):
                    self._janela.set_status("Erro na geracao", DANGER)
                self._btn_abrir_videos.pack_forget()
                _notificar_windows("GeradorBB", "Erro durante a geracao do video.")
        self.after(0, _ui)

    def _parar(self):
        if self._proc:
            self._proc.terminate()
        self._label_status.configure(text="⚠️  Interrompido.", text_color=WARNING)
        if hasattr(self._janela, "set_status"):
            self._janela.set_status("Interrompido", WARNING)

    def _set_btns_estado(self, ativo: bool):
        st     = "normal" if ativo else "disabled"
        st_par = "disabled" if ativo else "normal"
        for btn in (self._btn_pt_en, self._btn_pt, self._btn_en):
            btn.configure(state=st)
        self._btn_parar.configure(state=st_par)
        # Mostra/oculta botão parar
        if not ativo:
            self._btn_parar.pack(side="left")
        else:
            self._btn_parar.pack_forget()

    def _log_linha(self, linha: str, tag: str | None = None):
        def _ui():
            # Detecta tag automaticamente se não fornecida
            t = tag
            low = linha.lower()
            if t is None:
                if "✅" in linha or "sucesso" in low or "concluído" in low:
                    t = "ok"
                elif "❌" in linha or "erro" in low or "[erro]" in low or "error" in low:
                    t = "erro"
                elif "⚠" in linha or "warning" in low or "aviso" in low:
                    t = "warning"
                else:
                    t = "normal"

            self._log.configure(state="normal")
            self._log.insert("end", linha + "\n", t)
            self._log.see("end")
            self._log.configure(state="disabled")

            # Atualiza status imediatamente ao detectar conclusão no log
            # (o processo pode continuar rodando pós-processamento após imprimir sucesso)
            if "gerado" in low and "sucesso" in low:
                self._label_status.configure(
                    text="Concluido com sucesso!", text_color=SUCCESS)
                self._progress.stop()
                self._progress.pack_forget()
                if hasattr(self._janela, "set_status"):
                    self._janela.set_status("Concluido!", SUCCESS)
            elif ("[erro]" in low or "error" in low) and "erro" not in (tag or ""):
                # Não sobrescreve status se já for de erro explícito
                pass

        self.after(0, _ui)

    def _limpar_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _copiar_log(self):
        try:
            conteudo = self._log.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(conteudo)
        except Exception:
            pass


# ===========================================================================
# Tela: Configurações
# ===========================================================================

class TelaConfiguracoes(ctk.CTkFrame):
    def __init__(self, master, janela: JanelaPrincipal):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela = janela
        self._vars: dict = {}
        self._build_ui()

    def _build_ui(self):
        self.winfo_toplevel().bind("<Control-s>", lambda e: self._salvar())

        header = SectionHeader(self, "⚙️", "Configurações",
                               "Ajuste as opções de geração de vídeo.")
        header.pack(fill="x")
        _sep(self).pack(fill="x")

        # Área de conteúdo (scrollável)
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0,
                                        scrollbar_button_color=BG3,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.pack(fill="both", expand=True, padx=PAD * 2, pady=PAD)

        cfg = _carregar_config()

        # ---- Seção Vídeo ----
        self._secao_card(scroll, "🎬  Vídeo", lambda c: (
            self._row_campos(c, [
                ("Largura (px)", "largura", "int", cfg),
                ("Altura (px)",  "altura",  "int", cfg),
                ("FPS",          "fps",     "int", cfg),
            ]),
            self._row_opt_campos(c, [
                ("Fundo", "fundo", cfg, ["preto", "desfocado"]),
                ("Caminho do engine", "engine_path", cfg,
                 [str(_engine_dir())], True),
            ]),
        ))

        # ---- Seção Legenda ----
        _fontes_legenda = [
            "Arial", "Arial Black", "Arial Narrow",
            "Impact", "Verdana", "Tahoma",
            "Segoe UI", "Segoe UI Black",
            "Times New Roman", "Georgia",
            "Calibri", "Calibri Bold",
            "Comic Sans MS", "Trebuchet MS",
        ]
        self._secao_card(scroll, "📝  Legenda", lambda c: (
            self._row_opt_campos(c, [
                ("Fonte", "fonte", cfg, _fontes_legenda),
                ("Cor",   "cor_legenda", cfg,
                 ["amarelo", "branco", "ciano", "verde", "rosa", "laranja"]),
            ]),
            self._row_campos(c, [
                ("Tamanho (px)",         "tamanho_fonte",      "int", cfg),
                ("Posição do fundo (px)","posicao_legenda",    "int", cfg),
                ("Palavras por bloco",   "palavras_por_legenda","int", cfg),
            ]),
        ))

        # ---- Seção Áudio & Transcrição ----
        self._secao_card(scroll, "🎙️  Áudio & Transcrição", lambda c: (
            self._row_opt_campos(c, [
                ("Modelo Whisper", "whisper_modelo", cfg,
                 ["tiny", "base", "small", "medium", "large"]),
            ]),
            self._row_campos(c, [
                ("Volume música de fundo (0.0–1.0)", "volume_musica", "float", cfg),
            ]),
        ))

        # ---- Seção Avançado ----
        self._secao_card(scroll, "⚙️  Avançado", lambda c: (
            self._row_campos(c, [
                ("Zoom máximo (ex: 0.06 = 6%)", "zoom_maximo", "float", cfg),
            ]),
            self._build_canais_dir_row(c, cfg),
        ))

        # ---- Seção Personagem ----
        self._secao_card(scroll, "🎭  Personagem", lambda c: (
            self._row_bool_int(c, cfg),
        ))

        # Rodapé fixo
        rodape = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0,
                              border_width=1, border_color=BORDER, height=64)
        rodape.pack(fill="x", side="bottom")
        rodape.pack_propagate(False)

        inner = ctk.CTkFrame(rodape, fg_color="transparent")
        inner.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")

        ctk.CTkButton(
            inner, text="💾  Salvar  (Ctrl+S)",
            command=self._salvar,
            height=40, width=200,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(side="left")

        ctk.CTkButton(
            inner, text="🔧  Testar FFmpeg",
            command=self._testar_ffmpeg,
            height=40, width=160,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(10, 0))

        self._msg = ctk.CTkLabel(inner, text="",
                                 font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                                 text_color=SUCCESS)
        self._msg.pack(side="left", padx=(16, 0))

    def _secao_card(self, parent, titulo: str, builder_fn):
        card = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=CORNER_R,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 14))

        # Título da seção com barra accent
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(14, 10))
        ctk.CTkFrame(title_row, width=4, height=18, corner_radius=2,
                     fg_color=ACCENT).pack(side="left", padx=(0, 10))
        _label(title_row, titulo, size=FONT_SIZE_LG, bold=True).pack(side="left")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=(0, 14))
        builder_fn(content)

    def _row_campos(self, parent, campos: list):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        for i, (rotulo, chave, tipo, cfg) in enumerate(campos):
            f = ctk.CTkFrame(row, fg_color="transparent")
            f.grid(row=0, column=i, padx=(0, 12), sticky="ew")
            row.columnconfigure(i, weight=1)
            _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
            raw = cfg.get(chave, "")
            var = ctk.StringVar(value=str(raw))
            self._vars[chave] = (tipo, var)
            ctk.CTkEntry(f, textvariable=var, height=38, corner_radius=CORNER_R,
                         fg_color=BG3, border_color=BORDER, border_width=1,
                         text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _row_opt_campos(self, parent, campos: list):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        for i, item in enumerate(campos):
            if len(item) == 4:
                rotulo, chave, cfg, opcoes = item
                editable = False
            else:
                rotulo, chave, cfg, opcoes, editable = item
            f = ctk.CTkFrame(row, fg_color="transparent")
            f.grid(row=0, column=i, padx=(0, 12), sticky="ew")
            row.columnconfigure(i, weight=1)
            _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
            valor_atual = str(cfg.get(chave, opcoes[0] if opcoes else ""))
            if editable:
                var = ctk.StringVar(value=valor_atual)
                self._vars[chave] = ("str", var)
                ctk.CTkEntry(f, textvariable=var, height=38, corner_radius=CORNER_R,
                             fg_color=BG3, border_color=BORDER, border_width=1,
                             text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")
            else:
                var = ctk.StringVar(value=valor_atual if valor_atual in opcoes else opcoes[0])
                self._vars[chave] = ("str", var)
                ctk.CTkOptionMenu(f, values=opcoes, variable=var, height=38,
                                  fg_color=BG3, button_color=ACCENT,
                                  button_hover_color=ACCENT3,
                                  text_color=TEXT,
                                  font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _row_bool_int(self, parent, cfg):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        # Switch ativo
        f1 = ctk.CTkFrame(row, fg_color="transparent")
        f1.grid(row=0, column=0, padx=(0, 12), sticky="ew")
        row.columnconfigure(0, weight=1)
        _label(f1, "Ativo", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var_bool = ctk.BooleanVar(value=bool(cfg.get("personagem_ativo", True)))
        self._vars["personagem_ativo"] = ("bool", var_bool)
        ctk.CTkSwitch(f1, text="", variable=var_bool,
                      progress_color=ACCENT, button_color=TEXT).pack(anchor="w", pady=(6, 0))

        # Tamanho
        f2 = ctk.CTkFrame(row, fg_color="transparent")
        f2.grid(row=0, column=1, padx=(0, 12), sticky="ew")
        row.columnconfigure(1, weight=1)
        _label(f2, "Tamanho (%)", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var_int = ctk.StringVar(value=str(cfg.get("personagem_tamanho", 100)))
        self._vars["personagem_tamanho"] = ("int", var_int)
        ctk.CTkEntry(f2, textvariable=var_int, height=38, corner_radius=CORNER_R,
                     fg_color=BG3, border_color=BORDER, border_width=1,
                     text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _secao(self, parent, titulo):
        _sep(parent).pack(fill="x", pady=(8, 12))
        _label(parent, titulo, size=FONT_SIZE_LG, bold=True).pack(anchor="w", pady=(0, 8))

    def _campo_int(self, parent, rotulo, chave, cfg, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.columnconfigure(col, weight=1)
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var = ctk.StringVar(value=str(cfg.get(chave, "")))
        self._vars[chave] = ("int", var)
        ctk.CTkEntry(f, textvariable=var, height=38, corner_radius=CORNER_R,
                     fg_color=BG2, border_color=BORDER, border_width=1,
                     text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _campo_str(self, parent, rotulo, chave, cfg, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.columnconfigure(col, weight=1)
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var = ctk.StringVar(value=str(cfg.get(chave, "")))
        self._vars[chave] = ("str", var)
        ctk.CTkEntry(f, textvariable=var, height=38, corner_radius=CORNER_R,
                     fg_color=BG2, border_color=BORDER, border_width=1,
                     text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _campo_opt(self, parent, rotulo, chave, cfg, opcoes, col, editable=False):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.columnconfigure(col, weight=1)
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        valor_atual = str(cfg.get(chave, opcoes[0] if opcoes else ""))
        if editable:
            var = ctk.StringVar(value=valor_atual)
            self._vars[chave] = ("str", var)
            ctk.CTkEntry(f, textvariable=var, height=38, corner_radius=CORNER_R,
                         fg_color=BG2, border_color=BORDER, border_width=1,
                         text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")
        else:
            var = ctk.StringVar(value=valor_atual if valor_atual in opcoes else opcoes[0])
            self._vars[chave] = ("str", var)
            ctk.CTkOptionMenu(f, values=opcoes, variable=var, height=38,
                              fg_color=BG2, button_color=BG3,
                              button_hover_color=BG3,
                              text_color=TEXT,
                              font=(FONT_FAMILY, FONT_SIZE_MD)).pack(fill="x")

    def _campo_bool(self, parent, rotulo, chave, cfg, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.columnconfigure(col, weight=1)
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var = ctk.BooleanVar(value=bool(cfg.get(chave, True)))
        self._vars[chave] = ("bool", var)
        ctk.CTkSwitch(f, text="", variable=var,
                      progress_color=ACCENT, button_color=TEXT).pack(anchor="w", pady=(6, 0))

    def _build_canais_dir_row(self, parent, cfg):
        """Row para selecionar a pasta do banco com botão browse."""
        import tkinter.filedialog as _fd
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=(0, 8))
        _label(f, "Pasta dos canais  (vazio = padrão)",
               size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x")
        var = ctk.StringVar(value=str(cfg.get("canais_dir", "") or cfg.get("banco_dir", "")))
        self._vars["canais_dir"] = ("str", var)
        ctk.CTkEntry(row, textvariable=var, height=38, corner_radius=CORNER_R,
                     fg_color=BG3, border_color=BORDER, border_width=1,
                     text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD),
                     ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="📂",
            command=lambda: (
                lambda d: var.set(d) if d else None
            )(_fd.askdirectory(title="Escolher pasta dos canais")),
            width=42, height=38,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=CORNER_R,
        ).pack(side="left", padx=(6, 0))

    def _testar_ffmpeg(self):
        """Testa se o FFmpeg está disponível e mostra a versão."""
        import subprocess as _sp
        try:
            r = _sp.run(
                ["ffmpeg", "-version"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            primeira_linha = r.stdout.splitlines()[0] if r.stdout else "OK"
            self._msg.configure(text=f"✓ {primeira_linha[:60]}", text_color=SUCCESS)
        except FileNotFoundError:
            self._msg.configure(
                text="✗ FFmpeg não encontrado. Instale via: winget install Gyan.FFmpeg",
                text_color=DANGER)
        except Exception as e:
            self._msg.configure(text=f"✗ Erro: {e}", text_color=DANGER)
        self.after(6000, lambda: self._msg.configure(text=""))

    def _salvar(self):
        cfg = _carregar_config()
        for chave, (tipo, var) in self._vars.items():
            val = var.get()
            if tipo == "int":
                try:
                    cfg[chave] = int(val)
                except ValueError:
                    pass
            elif tipo == "float":
                try:
                    cfg[chave] = float(val)
                except ValueError:
                    pass
            elif tipo == "bool":
                cfg[chave] = bool(val)
            else:
                cfg[chave] = val
        _salvar_config(cfg)
        self._msg.configure(text="✓ Configurações salvas!", text_color=SUCCESS)
        self.after(3000, lambda: self._msg.configure(text=""))


# ===========================================================================
# Tela: Meus Vídeos
# ===========================================================================

class TelaMeusVideos(ctk.CTkFrame):
    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._todos_videos: list[Path] = []
        self._build_ui()

    def _build_ui(self):
        # Header da seção com botão atualizar no canto
        self._header_frame = ctk.CTkFrame(self, fg_color=BG3,
                                          corner_radius=0, height=72)
        self._header_frame.pack(fill="x")
        self._header_frame.pack_propagate(False)

        inner = ctk.CTkFrame(self._header_frame, fg_color="transparent")
        inner.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")
        ctk.CTkLabel(inner, text="📁", font=(FONT_FAMILY, 28)).pack(side="left", padx=(0, 12))
        txt_col = ctk.CTkFrame(inner, fg_color="transparent")
        txt_col.pack(side="left")
        ctk.CTkLabel(txt_col, text="Meus Vídeos",
                     font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
                     text_color=TEXT).pack(anchor="w")
        self._header_sub = ctk.CTkLabel(txt_col, text="Vídeos gerados pelo GeradorBB",
                                         font=(FONT_FAMILY, FONT_SIZE_SM),
                                         text_color=SUBTEXT)
        self._header_sub.pack(anchor="w")

        ctk.CTkButton(
            self._header_frame, text="↺  Atualizar",
            command=self.ao_exibir,
            height=34, width=120,
            fg_color=BG2, hover_color=BG3,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).place(relx=1, rely=0.5, x=-(PAD * 2), anchor="e")

        _sep(self).pack(fill="x")

        # ── Barra de busca ────────────────────────────────────────────────────
        busca_bar = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=44)
        busca_bar.pack(fill="x")
        busca_bar.pack_propagate(False)

        bb = ctk.CTkFrame(busca_bar, fg_color="transparent")
        bb.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")

        ctk.CTkLabel(bb, text="🔍", font=(FONT_FAMILY, 16)).pack(side="left", padx=(0, 6))
        self._busca_var = ctk.StringVar()
        self._busca_var.trace_add("write", lambda *_: self._filtrar())
        ctk.CTkEntry(bb, textvariable=self._busca_var,
                     placeholder_text="Buscar por nome...",
                     width=280, height=30, corner_radius=8,
                     fg_color=BG3, border_color=BORDER, text_color=TEXT,
                     font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")

        ctk.CTkButton(bb, text="✕", command=lambda: self._busca_var.set(""),
                      width=28, height=28, corner_radius=6,
                      fg_color="transparent", hover_color=BG3,
                      text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(bb, text="Ordenar:",
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(side="left", padx=(20, 6))
        self._sort_var = ctk.StringVar(value="Data ↓")
        self._sort_var.trace_add("write", lambda *_: self._filtrar())
        ctk.CTkOptionMenu(
            bb,
            variable=self._sort_var,
            values=["Data ↓", "Data ↑", "Nome A→Z", "Nome Z→A", "Tamanho ↓"],
            command=lambda _: self._filtrar(),
            width=140, height=30,
            fg_color=BG3, button_color=ACCENT,
            button_hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left")

        _sep(self).pack(fill="x")

        # ── Lista ─────────────────────────────────────────────────────────────
        self._scroll_lista = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color=BG3,
            scrollbar_button_hover_color=ACCENT,
        )
        self._scroll_lista.pack(fill="both", expand=True, padx=PAD * 2, pady=(0, PAD))

    def _coletar_videos(self) -> list[Path]:
        vid_dir = _videos_dir()
        videos: list[Path] = []
        if vid_dir.exists():
            for pasta in sorted(vid_dir.iterdir(), reverse=True):
                if pasta.is_dir():
                    for f in sorted(pasta.rglob("*.mp4"), reverse=True):
                        videos.append(f)
            for f in sorted(vid_dir.glob("*.mp4"), reverse=True):
                videos.append(f)
        return videos

    def _filtrar(self):
        termo   = self._busca_var.get().strip().lower()
        filtrados = [v for v in self._todos_videos
                     if not termo or termo in v.name.lower()]
        ordem = getattr(self, "_sort_var", None)
        if ordem:
            key = ordem.get()
            if key == "Data ↓":
                filtrados.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            elif key == "Data ↑":
                filtrados.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
            elif key == "Nome A→Z":
                filtrados.sort(key=lambda p: p.name.lower())
            elif key == "Nome Z→A":
                filtrados.sort(key=lambda p: p.name.lower(), reverse=True)
            elif key == "Tamanho ↓":
                filtrados.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
        self._renderizar(filtrados)

    def _renderizar(self, videos: list[Path]):
        for w in self._scroll_lista.winfo_children():
            w.destroy()

        if not videos:
            inner = ctk.CTkFrame(self._scroll_lista, fg_color="transparent")
            inner.pack(expand=True, pady=60)
            ctk.CTkLabel(inner, text="🎬", font=(FONT_FAMILY, 56)).pack()
            _label(inner, "Nenhum vídeo encontrado", size=FONT_SIZE_LG,
                   bold=True, color=SUBTEXT).pack(pady=(12, 0))
            if not self._busca_var.get():
                _label(inner, "Os vídeos gerados aparecerão aqui automaticamente.",
                       size=FONT_SIZE_SM, color=SUBTEXT).pack(pady=(4, 0))
                ctk.CTkLabel(inner, text=f"Pasta: {_videos_dir()}",
                             font=(FONT_FAMILY, FONT_SIZE_SM),
                             text_color=BG3).pack(pady=(8, 0))
            return

        for vid in videos[:200]:
            try:
                stat = vid.stat()
                tamanho_mb = stat.st_size / (1024 * 1024)
                data_mod   = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
            except Exception:
                tamanho_mb = 0
                data_mod   = "—"

            row = ctk.CTkFrame(self._scroll_lista, fg_color=BG2,
                               corner_radius=CORNER_R,
                               border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4)

            # Thumbnail placeholder
            thumb = ctk.CTkFrame(row, width=64, height=64,
                                 corner_radius=8, fg_color=BG3)
            thumb.pack(side="left", padx=(12, 10), pady=10)
            thumb.pack_propagate(False)
            ctk.CTkLabel(thumb, text="🎬", font=(FONT_FAMILY, 28)).place(
                relx=0.5, rely=0.5, anchor="center")

            # Info textual
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=10)
            _label(info, vid.name, size=FONT_SIZE_MD, bold=True).pack(anchor="w")
            ctk.CTkLabel(info, text=f"📅 {data_mod}   💾 {tamanho_mb:.1f} MB",
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=SUBTEXT).pack(anchor="w", pady=(3, 0))
            ctk.CTkLabel(info, text=str(vid.parent),
                         font=(FONT_FAMILY, 9),
                         text_color=BORDER).pack(anchor="w", pady=(2, 0))

            # Botões
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.pack(side="right", padx=12, pady=10)

            ctk.CTkButton(
                btns, text="▶  Abrir",
                command=lambda p=vid: os.startfile(str(p)),
                width=90, height=32,
                fg_color=ACCENT, hover_color=ACCENT3,
                text_color=TEXT, corner_radius=8,
                font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btns, text="📁  Pasta",
                command=lambda p=vid: subprocess.Popen(
                    ["explorer", "/select,", str(p)],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                ),
                width=82, height=32,
                fg_color=BG3, hover_color=BG2,
                border_color=BORDER, border_width=1,
                text_color=TEXT, corner_radius=8,
                font=(FONT_FAMILY, FONT_SIZE_SM),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btns, text="🗑",
                command=lambda p=vid, r=row: self._confirmar_delete(p, r),
                width=32, height=32,
                fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
                text_color=DANGER, border_color=BORDER, border_width=1,
                corner_radius=8, font=(FONT_FAMILY, FONT_SIZE_SM),
            ).pack(side="left")

    def _confirmar_delete(self, vid: Path, row_widget):
        import tkinter.messagebox as _mb
        ok = _mb.askyesno(
            "Excluir vídeo",
            f"Excluir permanentemente?\n\n{vid.name}",
            icon="warning",
        )
        if not ok:
            return
        try:
            vid.unlink()
            row_widget.destroy()
            self._todos_videos = [v for v in self._todos_videos if v != vid]
            self._atualizar_subtitulo()
        except Exception as e:
            _mb.showerror("Erro", f"Não foi possível excluir:\n{e}")

    def _atualizar_subtitulo(self):
        total = len(self._todos_videos)
        tamanho = sum(v.stat().st_size for v in self._todos_videos
                      if v.exists()) / (1024 * 1024)
        self._header_sub.configure(
            text=f"{total} vídeo{'s' if total != 1 else ''}  •  {tamanho:.0f} MB no total")

    def ao_exibir(self):
        self._todos_videos = self._coletar_videos()
        self._atualizar_subtitulo()
        self._busca_var.set("")
        self._renderizar(self._todos_videos)


# ===========================================================================
# Tela: Personagem
# ===========================================================================

_PERS_DEFAULTS = {
    "ativo": True,
    "largura_pct": 0.22,
    "lado": "esquerda",
    "margem_direita": 20,
    "margem_esquerda": 20,
    "margem_fundo": 40,
    "contorno_px": 0,
    "sombra_ativa": False,
    "sombra_offset_x": 5,
    "sombra_offset_y": 8,
    "sombra_blur": 6,
    "sombra_alpha": 0.65,
    "acenando_inicial": False,
    "apontando_ativo": True,
    "bob_amplitude_px": 3,
    "bob_hz": 0.5,
    "chromakey_cor": "0x1AE811",
    "chromakey_similaridade": 0.12,
    "chromakey_suavizacao": 0.08,
    "despill_ativo": True,
    "despill_fator": 0.8,
    "crossfade_s": 0.15,
    "fade_saida_s": 0.20,
    "volume_limite_boca": 0.03,
    "pausa_min_s": 0.30,
}

_MASC_DEFAULTS = {
    "ativo": True,
    "largura_pct": 0.22,
    "lado": "esquerda",
    "margem_esquerda": 20,
    "margem_direita": 20,
    "margem_fundo": 0,
    "volume_limite": 0.03,
    "pausa_min_s": 0.09,
    "bob_amplitude_px": 4,
    "bob_hz": 0.7,
    "pulo_amplitude_px": 18,
    "pulo_duracao_s": 0.30,
}


def _ler_cfg_json(path: Path, defaults: dict) -> dict:
    c = dict(defaults)
    if path.exists():
        try:
            c.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items()
                      if not k.startswith("_")})
        except Exception:
            pass
    return c


def _salvar_cfg_json(path: Path, dados: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

class TelaPreview(ctk.CTkFrame):
    """
    Canvas em escala 1:4 do vídeo (1080×1920 → 270×480).
    Elementos arrastáveis: logo, legenda, personagem.
    Painel direito mostra coordenadas em px reais que atualizam em tempo real.
    Salvar → grava config_video.json no projeto + personagem_config.json + mascote_config.json.
    """

    # ------------------------------------------------------------------ init

    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela      = janela
        self._drag_info   = None
        self._dragging    = False   # bloqueia redesenho via trace durante drag
        self._tk_imgs     = {}   # mantém referências (anti-GC)
        self._preset_ativo: str = "Padrão"
        # Dimensões do canvas — atualizam com o resize da janela
        self._VW = 360
        self._VH = 640
        self._SX = 360 / 1080
        self._SY = 640 / 1920
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        import tkinter as tk

        header = SectionHeader(self, "👁️", "Preview / Layout",
                               "Arraste logo, legenda e personagem para posicioná-los.")
        header.pack(fill="x")
        _sep(self).pack(fill="x")

        # ---- Barra de modelos (presets) ----
        preset_bar = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=52)
        preset_bar.pack(fill="x")
        preset_bar.pack_propagate(False)

        pb = ctk.CTkFrame(preset_bar, fg_color="transparent")
        pb.place(relx=0, rely=0.5, x=PAD*2, anchor="w")

        _label(pb, "Modelo:", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left", padx=(0, 8))

        self._preset_var = ctk.StringVar(value=self._preset_ativo)
        self._preset_menu = ctk.CTkOptionMenu(
            pb, variable=self._preset_var,
            values=["Padrão"],
            command=self._ao_selecionar_preset,
            width=180, height=32,
            fg_color=BG3, button_color=ACCENT,
            button_hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        )
        self._preset_menu.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            pb, text="💾  Salvar como...",
            command=self._dialog_salvar_como,
            height=32, width=130,
            fg_color=BG3, hover_color=BG4,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            pb, text="✏️",
            command=self._dialog_renomear,
            height=32, width=34,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            pb, text="🗑️",
            command=self._dialog_deletar,
            height=32, width=34,
            fg_color=BG3, hover_color=ACCENT_GHOST_HOVER,
            border_color=BORDER, border_width=1,
            text_color=DANGER, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left")

        _sep(self).pack(fill="x")

        # IMPORTANTE: rodapé ANTES do body (tkinter pack: side=bottom deve vir antes do expand)
        rodape = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0,
                              border_width=1, border_color=BORDER, height=58)
        rodape.pack(fill="x", side="bottom")
        rodape.pack_propagate(False)

        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True, padx=PAD * 2, pady=PAD)

        # Coluna esquerda — canvas
        left = ctk.CTkFrame(body, fg_color=BG2, corner_radius=CORNER_R,
                            border_width=1, border_color=BORDER)
        left.pack(side="left", fill="y", padx=(0, PAD))
        self._left_frame = left
        left.bind("<Configure>", self._on_left_resize)

        # Título com legenda de cores
        header_cv = ctk.CTkFrame(left, fg_color="transparent")
        header_cv.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header_cv, text="Prévia do vídeo",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=SUBTEXT).pack(side="left")

        # Legenda de cores
        legend_row = ctk.CTkFrame(left, fg_color="transparent")
        legend_row.pack(fill="x", padx=12, pady=(0, 4))
        for cor, nome_elem in ((COLOR_LOGO, "Logo"), (COLOR_LEGENDA, "Legenda"), (COLOR_PERSONAGEM, "Personagem"), (COLOR_BORDA, "Borda")):
            f = ctk.CTkFrame(legend_row, fg_color="transparent")
            f.pack(side="left", padx=(0, 10))
            ctk.CTkFrame(f, width=10, height=10, corner_radius=2,
                         fg_color=cor).pack(side="left", padx=(0, 3))
            ctk.CTkLabel(f, text=nome_elem,
                         font=(FONT_FAMILY, 9), text_color=SUBTEXT).pack(side="left")

        self._canvas = tk.Canvas(
            left,
            width=self._VW, height=self._VH,
            bg="#0a0a0a",
            highlightthickness=2,
            highlightbackground=ACCENT,
            cursor="arrow",
        )
        self._canvas.pack(padx=12, pady=(0, 4))
        # scroll bind no canvas (não no CTkScrollableFrame pai)
        self._canvas.bind("<MouseWheel>", self._canvas_scroll)

        ctk.CTkLabel(left,
                     text="← arraste livremente →",
                     font=(FONT_FAMILY, 9), text_color=SUBTEXT).pack(pady=(0, 10))

        # Coluna direita — propriedades com scroll
        right_outer = ctk.CTkFrame(body, fg_color="transparent")
        right_outer.pack(side="left", fill="both", expand=True)

        right = ctk.CTkScrollableFrame(right_outer, fg_color="transparent",
                                       scrollbar_button_color=BG3,
                                       scrollbar_button_hover_color=ACCENT)
        right.pack(fill="both", expand=True)

        self._build_props(right)

        inner = ctk.CTkFrame(rodape, fg_color="transparent")
        inner.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")

        ctk.CTkButton(
            inner, text="💾  Salvar posições",
            command=self._salvar,
            height=38, width=180,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(side="left")

        self._btn_testar = ctk.CTkButton(
            inner, text="🎬  Testar (40s)",
            command=self._testar,
            height=38, width=160,
            fg_color=BG3, hover_color=BG4,
            border_color=SUCCESS, border_width=1,
            text_color=SUCCESS, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        )
        self._btn_testar.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            inner, text="↺  Recarregar",
            command=self._recarregar,
            height=38, width=110,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(10, 0))

        self._msg = ctk.CTkLabel(inner, text="",
                                  font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                                  text_color=SUCCESS)
        self._msg.pack(side="left", padx=(14, 0))

        # Barra de progresso (oculta por padrão)
        self._progress_bar = ctk.CTkProgressBar(
            rodape, height=4, corner_radius=0,
            fg_color=BG4, progress_color=ACCENT,
        )
        self._progress_bar.set(0)
        self._progress_bar_visivel = False

    # ------------------------------------------------------------------ props panel

    def _build_props(self, parent):
        # ---- Logo ----
        c = _card(parent)
        c.pack(fill="x", pady=(0, 10))
        self._v_logo_ativo = self._prop_titulo_switch(c, "🖼️  Logo", COLOR_LOGO)
        g = ctk.CTkFrame(c, fg_color="transparent")
        g.pack(fill="x", padx=14, pady=(0, 12))
        self._v_logo_x   = self._prop_entry(g, "X (px)",        0, 0)
        self._v_logo_y   = self._prop_entry(g, "Y (px)",        0, 1)
        self._v_logo_w   = self._prop_entry(g, "Largura (px)",  0, 2)

        # ---- Legenda ----
        c2 = _card(parent)
        c2.pack(fill="x", pady=(0, 10))
        self._v_leg_ativo = self._prop_titulo_switch(c2, "📝  Legenda", COLOR_LEGENDA)
        g2 = ctk.CTkFrame(c2, fg_color="transparent")
        g2.pack(fill="x", padx=14, pady=(0, 12))
        self._v_leg      = self._prop_entry(g2, "Dist. do fundo (px)", 0, 0)
        self._v_leg_size = self._prop_entry(g2, "Tamanho fonte (px)",  0, 1)

        # ---- Personagem ----
        c3 = _card(parent)
        c3.pack(fill="x", pady=(0, 10))
        self._v_pers_ativo = self._prop_titulo_switch(c3, "🎭  Personagem", COLOR_PERSONAGEM)
        g3 = ctk.CTkFrame(c3, fg_color="transparent")
        g3.pack(fill="x", padx=14, pady=(0, 12))
        self._v_p_lado  = self._prop_opt(g3, "Lado",         0, 0,
                                          ["esquerda", "direita"])
        self._v_p_larg  = self._prop_entry(g3, "Largura (%)",  1, 0)
        self._v_p_mfundo= self._prop_entry(g3, "Margem fundo", 1, 1)
        self._v_p_mesq  = self._prop_entry(g3, "Margem esq.",  1, 2)
        self._v_p_mdir  = self._prop_entry(g3, "Margem dir.",  1, 3)

        # ---- Borda ----
        c4 = _card(parent)
        c4.pack(fill="x", pady=(0, 10))
        self._v_borda_ativo = self._prop_titulo_switch(c4, "🔲  Borda", COLOR_BORDA)
        g4 = ctk.CTkFrame(c4, fg_color="transparent")
        g4.pack(fill="x", padx=14, pady=(0, 6))

        _label(g4, "Arquivo:", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        self._v_borda_arquivo = ctk.StringVar(value="Nenhuma")
        self._borda_menu = ctk.CTkOptionMenu(
            g4, variable=self._v_borda_arquivo,
            values=["Nenhuma"],
            command=lambda _: self._on_entry_change(),
            height=34, fg_color=BG3, button_color=ACCENT,
            button_hover_color=ACCENT3, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        self._borda_menu.pack(fill="x", pady=(2, 6))

        ctk.CTkButton(
            g4, text="↺  Atualizar lista",
            command=self._atualizar_lista_bordas,
            height=28, fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(fill="x", pady=(0, 10))

    def _prop_titulo_switch(self, card, texto: str, cor: str = ACCENT) -> ctk.BooleanVar:
        """Cabeçalho do card com switch liga/desliga. Retorna a BooleanVar."""
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkFrame(r, width=4, height=16, corner_radius=2,
                     fg_color=cor).pack(side="left", padx=(0, 8))
        _label(r, texto, size=FONT_SIZE_SM, bold=True).pack(side="left")
        var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            r, text="", variable=var, width=44, height=22,
            progress_color=cor, button_color=TEXT,
            command=self._redesenhar,
        ).pack(side="right")
        return var

    def _prop_titulo(self, card, texto):
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkFrame(r, width=4, height=16, corner_radius=2,
                     fg_color=ACCENT).pack(side="left", padx=(0, 8))
        _label(r, texto, size=FONT_SIZE_SM, bold=True).pack(side="left")

    def _prop_entry(self, parent, rotulo: str, row: int, col: int) -> ctk.StringVar:
        parent.columnconfigure(col, weight=1)
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=col, padx=(0, 8), pady=(0, 4), sticky="ew")
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=var, height=34,
                     fg_color=BG3, border_color=BORDER, border_width=1,
                     text_color=TEXT, corner_radius=6,
                     font=(FONT_FAMILY, FONT_SIZE_SM)).pack(fill="x")
        var.trace_add("write", lambda *_: self._on_entry_change())
        return var

    def _prop_opt(self, parent, rotulo: str, row: int, col: int,
                  opcoes: list) -> ctk.StringVar:
        parent.columnconfigure(col, weight=1)
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=col, padx=(0, 8), pady=(0, 4), sticky="ew")
        _label(f, rotulo, size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        var = ctk.StringVar(value=opcoes[0])
        ctk.CTkOptionMenu(f, values=opcoes, variable=var, height=34,
                          fg_color=BG3, button_color=ACCENT,
                          button_hover_color=ACCENT3,
                          text_color=TEXT,
                          font=(FONT_FAMILY, FONT_SIZE_SM),
                          command=lambda _: self._on_entry_change()).pack(fill="x")
        return var

    # ------------------------------------------------------------------ helpers

    def _cfg_atual(self) -> dict:
        """Lê config_video.json + personagem/mascote do projeto ativo."""
        d = {
            "logo_x": 20, "logo_y": 248, "logo_largura": 340,
            "logo_ativo": True,
            "posicao_legenda": 300, "tamanho_fonte": 64,
            "legenda_ativa": True,
            "pers_lado": "esquerda",
            "pers_largura_pct": 0.22,
            "pers_margem_fundo": 40,
            "pers_margem_esq": 20,
            "pers_margem_dir": 20,
            "personagem_ativo": True,
            "borda_arquivo": "Nenhuma",
            "borda_ativa": True,
        }
        # config_video.json sobrescreve padrões
        cv = _projeto_dir() / "config_video.json"
        if cv.exists():
            try:
                d.update({k: v for k, v in json.loads(
                    cv.read_text(encoding="utf-8")).items()
                    if not k.startswith("_")})
            except Exception:
                pass
        # personagem/mascote config para lado/largura/margens
        for pc in (_personagem_cfg_path(), _mascote_cfg_path()):
            pc_d = _ler_cfg_json(pc, {})
            for src, dst in (("lado","pers_lado"),
                             ("largura_pct","pers_largura_pct"),
                             ("margem_fundo","pers_margem_fundo"),
                             ("margem_esquerda","pers_margem_esq"),
                             ("margem_direita","pers_margem_dir")):
                if src in pc_d:
                    d[dst] = pc_d[src]
            break  # usa só personagem_config como referência principal
        return d

    def _preencher_vars(self):
        d = self._cfg_atual()
        self._v_logo_x.set(str(d["logo_x"]))
        self._v_logo_y.set(str(d["logo_y"]))
        self._v_logo_w.set(str(d["logo_largura"]))
        self._v_logo_ativo.set(bool(d.get("logo_ativo", True)))
        self._v_leg.set(str(d["posicao_legenda"]))
        self._v_leg_size.set(str(d["tamanho_fonte"]))
        self._v_leg_ativo.set(bool(d.get("legenda_ativa", True)))
        self._v_p_lado.set(str(d["pers_lado"]))
        self._v_p_larg.set(str(d["pers_largura_pct"]))
        self._v_p_mfundo.set(str(d["pers_margem_fundo"]))
        self._v_p_mesq.set(str(d["pers_margem_esq"]))
        self._v_p_mdir.set(str(d["pers_margem_dir"]))
        self._v_pers_ativo.set(bool(d.get("personagem_ativo", True)))
        self._v_borda_arquivo.set(str(d.get("borda_arquivo", "Nenhuma")))
        self._v_borda_ativo.set(bool(d.get("borda_ativa", True)))

    def _iv(self, var, default=0) -> int:
        try:
            return int(float(var.get()))
        except Exception:
            return default

    def _fv(self, var, default=0.0) -> float:
        try:
            return float(var.get())
        except Exception:
            return default

    def _sv(self, var, default="") -> str:
        try:
            return var.get()
        except Exception:
            return default

    # ------------------------------------------------------------------ canvas

    def _redesenhar(self):
        import tkinter as tk

        c = self._canvas
        c.delete("all")
        self._tk_imgs.clear()

        VW, VH = self._VW, self._VH
        SX, SY = self._SX, self._SY

        # ── Fundo — imagem real do banco ──────────────────────────────────────
        c.create_rectangle(0, 0, VW, VH, fill="#0a0a0a", outline="")
        tk_bg = self._carregar_bg()
        if tk_bg:
            c.create_image(0, 0, image=tk_bg, anchor="nw")
        else:
            # Guias de terços quando não há imagem
            for i in (1, 2):
                c.create_line(VW*i//3, 0, VW*i//3, VH, fill="#1c1c1c", dash=(2, 6))
                c.create_line(0, VH*i//3, VW, VH*i//3, fill="#1c1c1c", dash=(2, 6))
            c.create_rectangle(int(VW*.03), int(VH*.04),
                               int(VW*.97), int(VH*.96),
                               fill="#0d0d1a", outline="#1a1a33")
            c.create_text(VW//2, VH//2,
                          text="Coloque imagens em\ncenas/ ou banco de imagens/",
                          fill="#333355", font=("Arial", 8), justify="center")

        # ── Logo ──────────────────────────────────────────────────────────────
        if self._v_logo_ativo.get():
            try:
                lx  = self._iv(self._v_logo_x, 20)
                ly  = self._iv(self._v_logo_y, 248)
                lw  = self._iv(self._v_logo_w, 340)
                cx, cy = int(lx * SX), int(ly * SY)
                tk_logo = self._carregar_logo(lw)
                if tk_logo:
                    c.create_image(cx, cy, image=tk_logo, anchor="nw", tags=("logo",))
                else:
                    cw = max(12, int(lw * SX))
                    ch = max(12, int(42 * SY))
                    c.create_rectangle(cx, cy, cx+cw, cy+ch,
                                       fill="#8b1a2f", outline="#e94560",
                                       width=2, tags=("logo",))
                    c.create_text(cx+cw//2, cy+ch//2, text="LOGO",
                                  fill="#ffffff", font=("Arial", 8, "bold"),
                                  tags=("logo",))
            except Exception:
                pass

        # ── Legenda ────────────────────────────────────────────────────────────
        if self._v_leg_ativo.get():
            try:
                dist  = self._iv(self._v_leg, 300)
                fonte = self._iv(self._v_leg_size, 64)
                l_h   = max(10, int(fonte * 1.6 * SY))
                l_y1  = int((1920 - dist) * SY)
                l_y0  = max(0, l_y1 - l_h)
                c.create_rectangle(0, l_y0, VW, l_y1,
                                   fill="#1a1400", outline="#ffdd00",
                                   width=2, tags=("legenda",))
                c.create_text(VW//2, (l_y0 + l_y1)//2,
                              text="Legenda do vídeo",
                              fill="#ffdd00", font=("Arial", 7, "bold"),
                              tags=("legenda",))
                mid_x = VW//2
                c.create_polygon(mid_x-6, l_y0+4, mid_x+6, l_y0+4,
                                 mid_x, l_y0+10,
                                 fill="#ffdd00", tags=("legenda",))
                c.create_polygon(mid_x-6, l_y1-4, mid_x+6, l_y1-4,
                                 mid_x, l_y1-10,
                                 fill="#ffdd00", tags=("legenda",))
            except Exception:
                pass

        # ── Personagem ────────────────────────────────────────────────────────
        if self._v_pers_ativo.get():
            try:
                lado   = self._sv(self._v_p_lado, "esquerda")
                lpct   = max(0.05, self._fv(self._v_p_larg, 0.22))
                mfundo = self._iv(self._v_p_mfundo, 40)
                mesq   = self._iv(self._v_p_mesq, 20)
                mdir   = self._iv(self._v_p_mdir, 20)

                pw = max(12, int(1080 * lpct * SX))
                ph = max(16, int(pw * 2.2))
                py = max(0, VH - int(mfundo * SY) - ph)
                px = (VW - int(mdir * SX) - pw) if lado == "direita" else int(mesq * SX)

                tk_pers = self._carregar_personagem(pw, ph)
                if tk_pers:
                    c.create_image(px, py, image=tk_pers, anchor="nw", tags=("personagem",))
                else:
                    c.create_rectangle(px, py, px+pw, py+ph,
                                       fill="#0a2a14", outline="#22cc55",
                                       width=2, tags=("personagem",))
                    head_r = pw // 3
                    hx = px + pw//2
                    hy = py + head_r + 4
                    c.create_oval(hx-head_r, hy-head_r, hx+head_r, hy+head_r,
                                  fill="#0d3a1a", outline="#44ff77",
                                  width=1, tags=("personagem",))
                    c.create_text(px+pw//2, py+ph//2+8,
                                  text="PERS.", fill="#44ff77",
                                  font=("Arial", 7, "bold"),
                                  tags=("personagem",))
            except Exception:
                pass

        # ── Borda decorativa (por cima de tudo) ──────────────────────────────
        if self._v_borda_ativo.get():
            try:
                tk_borda = self._carregar_borda()
                if tk_borda:
                    c.create_image(0, 0, image=tk_borda, anchor="nw", tags=("borda",))
            except Exception:
                pass

        # ── Bind drag — SEMPRE executado, independente de erros acima ─────────
        for tag, cur in (("logo", "fleur"),
                         ("legenda", "sb_v_double_arrow"),
                         ("personagem", "fleur")):
            c.tag_bind(tag, "<ButtonPress-1>",
                       lambda e, t=tag: self._drag_start(e, t))
            c.tag_bind(tag, "<B1-Motion>",
                       lambda e, t=tag: self._drag_move(e, t))
            c.tag_bind(tag, "<ButtonRelease-1>",
                       lambda e, t=tag: self._drag_end(e, t))
            c.tag_bind(tag, "<Enter>",
                       lambda e, cur=cur: c.config(cursor=cur))
            c.tag_bind(tag, "<Leave>",
                       lambda e: c.config(cursor="arrow"))

    def _atualizar_lista_bordas(self):
        """Atualiza o OptionMenu com os PNGs disponíveis em projeto/bordas/."""
        bordas_dir = _projeto_dir() / "projeto" / "bordas"
        bordas_dir.mkdir(parents=True, exist_ok=True)
        arquivos = sorted(
            p.name for p in bordas_dir.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        )
        opcoes = ["Nenhuma"] + arquivos
        self._borda_menu.configure(values=opcoes)
        atual = self._v_borda_arquivo.get()
        if atual not in opcoes:
            self._v_borda_arquivo.set("Nenhuma")
        self._redesenhar()

    def _carregar_borda(self):
        """Carrega o PNG de borda selecionado e retorna ImageTk redimensionado."""
        try:
            nome = self._v_borda_arquivo.get()
            if not nome or nome == "Nenhuma":
                return None
            from PIL import Image, ImageTk
            p = _projeto_dir() / "projeto" / "bordas" / nome
            if not p.exists():
                return None
            img = Image.open(p).convert("RGBA")
            img = img.resize((self._VW, self._VH), Image.LANCZOS)
            tk_i = ImageTk.PhotoImage(img)
            self._tk_imgs["borda"] = tk_i
            return tk_i
        except Exception:
            return None

    def _carregar_logo(self, largura_real: int):
        try:
            from PIL import Image, ImageTk
            logos_dir = _projeto_dir() / "projeto" / "logos"
            candidatos: list[Path] = []

            # 1. logo.png exata (copiada pelo TelaCenas ao copiar cenas)
            for d in (logos_dir, _imagens_dir(), _engine_dir()):
                for nome in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp"):
                    candidatos.append(d / nome)

            # 2. Qualquer arquivo em logos/ (logo_1.png, logo_2.png …)
            if logos_dir.exists():
                for ext in ("png", "PNG", "jpg", "JPG", "jpeg", "JPEG", "webp", "WEBP"):
                    candidatos.extend(logos_dir.glob(f"*.{ext}"))

            for p in candidatos:
                if p.exists():
                    w = max(6, int(largura_real * self._SX))
                    img = Image.open(p).convert("RGBA")
                    h = max(1, int(img.height * w / img.width))
                    img = img.resize((w, h), Image.LANCZOS)
                    tk_i = ImageTk.PhotoImage(img)
                    self._tk_imgs["logo"] = tk_i
                    return tk_i
        except Exception:
            pass
        return None

    def _carregar_personagem(self, pw: int, ph: int):
        try:
            from PIL import Image, ImageTk
            imagem: Image.Image | None = None

            # 1. Tenta carregar um frame do cache .npz (já com chromakey aplicado = sem fundo verde)
            if imagem is None:
                for pasta in (_personagem_dir(), _mascote_dir()):
                    if imagem:
                        break
                    trans = pasta / "_transparente"
                    if not trans.exists():
                        continue
                    for npz in sorted(trans.glob("*.npz")):
                        try:
                            import numpy as np
                            data = np.load(str(npz))["frames"]  # (N, h, w, 4) uint8
                            if data.ndim == 4 and data.shape[0] > 0:
                                frame = data[len(data) // 2]   # frame do meio
                                imagem = Image.fromarray(frame, "RGBA")
                                break
                        except Exception:
                            continue

            # 2. Extrai frame do .mp4 com chromakey via FFmpeg (fundo removido)
            if imagem is None:
                cfg_pers = _ler_cfg_json(_personagem_cfg_path(), _PERS_DEFAULTS)
                cor_raw  = cfg_pers.get("chromakey_cor", "0x1AE811")
                cor      = cor_raw.removeprefix("0x").removeprefix("#")
                sim      = cfg_pers.get("chromakey_similaridade", 0.12)
                suav     = cfg_pers.get("chromakey_suavizacao", 0.08)
                for pasta in (_personagem_dir(), _mascote_dir()):
                    if imagem:
                        break
                    if not pasta.exists():
                        continue
                    for mp4 in list(pasta.glob("*.mp4")) + list(pasta.glob("*.MP4")) + \
                               list(pasta.glob("*.mov")) + list(pasta.glob("*.MOV")):
                        try:
                            import tempfile, subprocess as _sp
                            tmp = tempfile.mktemp(suffix=".png")
                            vf  = (f"chromakey=color=0x{cor}:similarity={sim:.3f}:"
                                   f"blend={suav:.3f},format=rgba")
                            _sp.run(
                                ["ffmpeg", "-y", "-ss", "0.5", "-i", str(mp4),
                                 "-vf", vf, "-vframes", "1", tmp],
                                capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                                if sys.platform == "win32" else 0,
                                timeout=15,
                            )
                            if Path(tmp).exists():
                                imagem = Image.open(tmp).convert("RGBA")
                                Path(tmp).unlink(missing_ok=True)
                                break
                        except Exception:
                            continue

            # 3. Fallback: imagem estática nas pastas (PNG/JPG sem chromakey)
            if imagem is None:
                candidatos: list[Path] = []
                for pasta in (_personagem_dir(), _mascote_dir()):
                    if pasta.exists():
                        for ext in ("png", "PNG", "jpg", "JPG", "jpeg", "JPEG", "webp", "WEBP"):
                            candidatos.extend(pasta.glob(f"*.{ext}"))
                vistos: set[Path] = set()
                for p in candidatos:
                    try:
                        rp = p.resolve()
                        if rp in vistos or not p.exists():
                            continue
                        vistos.add(rp)
                        imagem = Image.open(p).convert("RGBA")
                        break
                    except Exception:
                        continue

            if imagem is None:
                return None

            # Redimensiona mantendo proporção, limitando à altura disponível
            orig_w, orig_h = imagem.size
            h = max(1, int(orig_h * pw / orig_w))
            if h > ph:
                pw = max(1, int(orig_w * ph / orig_h))
                h  = ph
            imagem = imagem.resize((pw, h), Image.LANCZOS)
            tk_i = ImageTk.PhotoImage(imagem)
            self._tk_imgs["pers"] = tk_i
            return tk_i
        except Exception:
            return None

    def _carregar_bg(self):
        """Carrega imagem de capa posicionada igual ao engine (layout padrao).
        Cria frame preto 9:16 e cola a imagem na posição exata do vídeo real."""
        try:
            from PIL import Image, ImageTk
            candidatos: list[Path] = []

            # 1. Imagens numeradas em cenas/ (1.jpg, 2.png …)
            cenas = _imagens_dir()
            if cenas.exists():
                for ext in ("jpg", "jpeg", "png", "webp",
                            "JPG", "JPEG", "PNG", "WEBP"):
                    for p in cenas.glob(f"*.{ext}"):
                        if p.stem.isdigit():
                            candidatos.append(p)

            # 2. Qualquer imagem em doramas/
            if not candidatos:
                doramas = _projeto_dir() / "projeto" / "imagens"
                if doramas.exists():
                    for ext in ("jpg", "jpeg", "png", "webp",
                                "JPG", "JPEG", "PNG", "WEBP"):
                        candidatos.extend(doramas.glob(f"*.{ext}"))

            if not candidatos:
                return None

            img_path = sorted(candidatos, key=lambda p: p.stem)[0]
            img = Image.open(img_path).convert("RGB")
            src_w, src_h = img.size

            # ── Replica calcular_capa_geometria (layout padrao) ──────────────
            # padrao: caixa = largura cheia × 78% altura, centrada
            LARG_REAL, ALT_REAL = 1080, 1920
            caixa_w = LARG_REAL
            caixa_h = int(ALT_REAL * 0.78)          # 1497 px
            escala  = min(caixa_w / src_w, caixa_h / src_h)
            iw = (int(src_w * escala) // 2) * 2
            ih = (int(src_h * escala) // 2) * 2
            rx = (LARG_REAL - iw) // 2               # x no vídeo real
            ry = (ALT_REAL  - ih) // 2               # y no vídeo real

            # ── Converte para coordenadas do canvas ───────────────────────────
            cx = int(rx * self._SX)
            cy = int(ry * self._SY)
            cw = max(1, int(iw * self._SX))
            ch = max(1, int(ih * self._SY))

            img_redim = img.resize((cw, ch), Image.LANCZOS)

            # Frame preto do tamanho do canvas + imagem colada na posição correta
            frame = Image.new("RGB", (self._VW, self._VH), (0, 0, 0))
            frame.paste(img_redim, (cx, cy))

            # Escurece levemente
            escuro = Image.new("RGB", (self._VW, self._VH), (0, 0, 0))
            frame = Image.blend(frame, escuro, alpha=0.20)

            tk_i = ImageTk.PhotoImage(frame)
            self._tk_imgs["bg"] = tk_i
            return tk_i
        except Exception:
            return None

    # ------------------------------------------------------------------ drag

    def _drag_start(self, event, tag):
        c = self._canvas
        self._drag_info = {
            "tag": tag,
            "x": c.canvasx(event.x),
            "y": c.canvasy(event.y),
        }
        self._dragging = True

    def _drag_move(self, event, tag):
        if not self._drag_info or self._drag_info["tag"] != tag:
            return
        c = self._canvas
        cx = c.canvasx(event.x)
        cy = c.canvasy(event.y)
        dx = cx - self._drag_info["x"]
        dy = cy - self._drag_info["y"]
        self._drag_info["x"] = cx
        self._drag_info["y"] = cy

        c = self._canvas
        if tag == "logo":
            c.move("logo", dx, dy)
            coords = c.bbox("logo")
            if coords:
                self._v_logo_x.set(str(max(0, int(coords[0] / self._SX))))
                self._v_logo_y.set(str(max(0, int(coords[1] / self._SY))))
        elif tag == "legenda":
            c.move("legenda", 0, dy)       # só vertical
            coords = c.bbox("legenda")
            if coords:
                # coords[3] = borda inferior da faixa em px do canvas
                leg_y1_real = coords[3] / self._SY
                dist = max(0, int(1920 - leg_y1_real))
                self._v_leg.set(str(dist))
        elif tag == "personagem":
            c.move("personagem", dx, dy)
            # StringVars só atualizam em _drag_end para não disparar trace do CTkOptionMenu

    def _drag_end(self, event, tag):
        self._drag_info = None
        self._dragging  = False
        if tag == "personagem":
            coords = self._canvas.bbox("personagem")
            if coords:
                cx_mid = (coords[0] + coords[2]) / 2
                lado   = "esquerda" if cx_mid < self._VW / 2 else "direita"
                self._v_p_lado.set(lado)
                # Recalcula pw/ph exatamente como _redesenhar fará — a imagem pode
                # ter sido redimensionada com proporção diferente de 2.2, então
                # usar coords[3] (fundo real) causaria salto; usamos coords[1] (topo).
                _lpct = max(0.05, self._fv(self._v_p_larg, 0.22))
                _pw   = max(12, int(1080 * _lpct * self._SX))
                _ph   = max(16, int(_pw * 2.2))
                if lado == "esquerda":
                    m = max(0, int(coords[0] / self._SX))
                    self._v_p_mesq.set(str(m))
                else:
                    # Ancora pela borda esquerda do slot esperado (_pw)
                    m = max(0, int((self._VW - coords[0] - _pw) / self._SX))
                    self._v_p_mdir.set(str(m))
                # coords[1] = topo da imagem; _ph = altura que o redesenho usará
                mf = max(0, int((self._VH - coords[1] - _ph) / self._SY))
                self._v_p_mfundo.set(str(mf))
        self._redesenhar()   # redesenha uma vez com as posições finais

    def _canvas_scroll(self, event):
        """Scroll do mouse sobre o canvas → redimensiona o elemento sob o cursor."""
        # Descobre qual tag está sob o cursor
        c = self._canvas
        items = c.find_closest(event.x, event.y)
        if not items:
            return
        tags = set(c.gettags(items[0]))

        step = 1 if event.delta > 0 else -1   # Windows: ±120 → ±1

        if "logo" in tags:
            w = self._iv(self._v_logo_w, 340)
            self._v_logo_w.set(str(max(30, w + step * 10)))
        elif "legenda" in tags:
            sz = self._iv(self._v_leg_size, 64)
            self._v_leg_size.set(str(max(20, sz + step * 2)))
        elif "personagem" in tags:
            pct = self._fv(self._v_p_larg, 0.22)
            pct = round(max(0.05, min(0.60, pct + step * 0.01)), 3)
            self._v_p_larg.set(str(pct))
        else:
            return  # cursor no fundo — não faz nada
        self._redesenhar()

    def _on_entry_change(self):
        """Chamado quando usuário edita manualmente um campo — redesenha."""
        if self._dragging:
            return  # durante drag os StringVars são atualizados mas não redesenha
        try:
            self.after_cancel(self._redraw_after)
        except Exception:
            pass
        self._redraw_after = self.after(150, self._redesenhar)

    # ------------------------------------------------------------------ save

    def _gravar_config_ativa(self):
        """Grava config_video.json + personagem_config.json com os valores atuais da UI.
        Chamado tanto pelo Salvar quanto pelo Testar — garante que o engine sempre
        use as posições visíveis na tela."""
        cv = {
            "logo_x":          self._iv(self._v_logo_x, 20),
            "logo_y":          self._iv(self._v_logo_y, 248),
            "logo_largura":    self._iv(self._v_logo_w, 340),
            "logo_ativo":      self._v_logo_ativo.get(),
            "posicao_legenda": self._iv(self._v_leg, 300),
            "tamanho_fonte":   self._iv(self._v_leg_size, 64),
            "legenda_ativa":   self._v_leg_ativo.get(),
            "personagem_ativo":self._v_pers_ativo.get(),
            "borda_arquivo":   self._sv(self._v_borda_arquivo, "Nenhuma"),
            "borda_ativa":     self._v_borda_ativo.get(),
        }
        out = _projeto_dir() / "config_video.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cv, ensure_ascii=False, indent=2), encoding="utf-8")

        pers_upd = {
            "lado":           self._sv(self._v_p_lado, "esquerda"),
            "largura_pct":    self._fv(self._v_p_larg, 0.22),
            "margem_fundo":   self._iv(self._v_p_mfundo, 40),
            "margem_esquerda":self._iv(self._v_p_mesq, 20),
            "margem_direita": self._iv(self._v_p_mdir, 20),
        }
        for cfg_path, defaults in ((_personagem_cfg_path(), _PERS_DEFAULTS),
                                   (_mascote_cfg_path(), _MASC_DEFAULTS)):
            existing = _ler_cfg_json(cfg_path, defaults)
            existing.update(pers_upd)
            _salvar_cfg_json(cfg_path, existing)

    def _salvar(self):
        # "Padrão" é somente leitura — pede para criar um modelo com nome
        if self._preset_ativo == "Padrão":
            self._dialog_salvar_como()
            return

        # Grava os arquivos que o engine lê
        self._gravar_config_ativa()

        # Grava também no arquivo do preset para recarregar depois
        p = self._preset_path(self._preset_ativo)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._cfg_para_dict(), ensure_ascii=False, indent=2),
                     encoding="utf-8")

        self._set_msg_preview(f"✓ Salvo! (modelo: {self._preset_ativo})", SUCCESS)

    # ------------------------------------------------------------------ presets

    def _preset_path(self, nome: str) -> Path:
        return _layouts_dir() / f"{nome}.json"

    def _listar_presets(self) -> list[str]:
        d = _layouts_dir()
        d.mkdir(parents=True, exist_ok=True)
        nomes = ["Padrão"] + sorted(
            p.stem for p in d.glob("*.json") if p.stem != "Padrão"
        )
        return nomes

    def _atualizar_dropdown(self):
        nomes = self._listar_presets()
        self._preset_menu.configure(values=nomes)
        if self._preset_ativo not in nomes:
            self._preset_ativo = "Padrão"
        self._preset_var.set(self._preset_ativo)

    def _cfg_para_dict(self) -> dict:
        return {
            "logo_x":           self._iv(self._v_logo_x, 20),
            "logo_y":           self._iv(self._v_logo_y, 248),
            "logo_largura":     self._iv(self._v_logo_w, 340),
            "logo_ativo":       self._v_logo_ativo.get(),
            "posicao_legenda":  self._iv(self._v_leg, 300),
            "tamanho_fonte":    self._iv(self._v_leg_size, 64),
            "legenda_ativa":    self._v_leg_ativo.get(),
            "pers_lado":        self._sv(self._v_p_lado, "esquerda"),
            "pers_largura_pct": self._fv(self._v_p_larg, 0.22),
            "pers_margem_fundo":self._iv(self._v_p_mfundo, 40),
            "pers_margem_esq":  self._iv(self._v_p_mesq, 20),
            "pers_margem_dir":  self._iv(self._v_p_mdir, 20),
            "personagem_ativo": self._v_pers_ativo.get(),
            "borda_arquivo":    self._sv(self._v_borda_arquivo, "Nenhuma"),
            "borda_ativa":      self._v_borda_ativo.get(),
        }

    def _aplicar_dict(self, d: dict):
        self._v_logo_x.set(str(d.get("logo_x", 20)))
        self._v_logo_y.set(str(d.get("logo_y", 248)))
        self._v_logo_w.set(str(d.get("logo_largura", 340)))
        self._v_logo_ativo.set(bool(d.get("logo_ativo", True)))
        self._v_leg.set(str(d.get("posicao_legenda", 300)))
        self._v_leg_size.set(str(d.get("tamanho_fonte", 64)))
        self._v_leg_ativo.set(bool(d.get("legenda_ativa", True)))
        self._v_p_lado.set(str(d.get("pers_lado", "esquerda")))
        self._v_p_larg.set(str(d.get("pers_largura_pct", 0.22)))
        self._v_p_mfundo.set(str(d.get("pers_margem_fundo", 40)))
        self._v_p_mesq.set(str(d.get("pers_margem_esq", 20)))
        self._v_p_mdir.set(str(d.get("pers_margem_dir", 20)))
        self._v_pers_ativo.set(bool(d.get("personagem_ativo", True)))
        borda = d.get("borda_arquivo", "Nenhuma")
        self._v_borda_arquivo.set(borda if borda else "Nenhuma")
        self._v_borda_ativo.set(bool(d.get("borda_ativa", True)))

    # Valores fixos do modelo "Padrão" — nunca se alteram
    _PADRAO_FIXO = {
        "logo_x": 20, "logo_y": 248, "logo_largura": 340, "logo_ativo": True,
        "posicao_legenda": 300, "tamanho_fonte": 64, "legenda_ativa": True,
        "pers_lado": "esquerda", "pers_largura_pct": 0.22,
        "pers_margem_fundo": 40, "pers_margem_esq": 20, "pers_margem_dir": 20,
        "personagem_ativo": True,
        "borda_arquivo": "Nenhuma", "borda_ativa": True,
    }

    def _ao_selecionar_preset(self, nome: str):
        self._preset_ativo = nome
        if nome == "Padrão":
            self._aplicar_dict(self._PADRAO_FIXO)
        else:
            p = self._preset_path(nome)
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    self._aplicar_dict(d)
                except Exception:
                    pass
        self._redesenhar()
        self._set_msg_preview(f"Modelo '{nome}' carregado", SUCCESS)

    def _dialog_salvar_como(self):
        import tkinter.simpledialog as sd
        nome = sd.askstring(
            "Salvar modelo",
            "Nome do modelo de layout:",
            initialvalue=self._preset_ativo if self._preset_ativo != "Padrão" else "",
            parent=self,
        )
        if not nome:
            return
        nome = nome.strip()
        if not nome:
            return
        if nome == "Padrão":
            self._set_msg_preview("'Padrão' é reservado. Escolha outro nome.", WARNING)
            return
        d = _layouts_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{nome}.json"
        p.write_text(json.dumps(self._cfg_para_dict(), ensure_ascii=False, indent=2),
                     encoding="utf-8")
        self._preset_ativo = nome
        self._atualizar_dropdown()
        # Grava os arquivos que o engine lê com as posições atuais
        self._gravar_config_ativa()
        self._set_msg_preview(f"Modelo '{nome}' salvo!", SUCCESS)

    def _dialog_renomear(self):
        import tkinter.simpledialog as sd
        if self._preset_ativo == "Padrão":
            self._set_msg_preview("O modelo 'Padrão' não pode ser renomeado.", WARNING)
            return
        novo = sd.askstring(
            "Renomear modelo",
            f"Novo nome para '{self._preset_ativo}':",
            initialvalue=self._preset_ativo,
            parent=self,
        )
        if not novo:
            return
        novo = novo.strip()
        if not novo or novo == self._preset_ativo or novo == "Padrão":
            return
        antigo_path = self._preset_path(self._preset_ativo)
        novo_path   = self._preset_path(novo)
        if antigo_path.exists():
            antigo_path.rename(novo_path)
        self._preset_ativo = novo
        self._atualizar_dropdown()
        self._set_msg_preview(f"Renomeado para '{novo}'", SUCCESS)

    def _dialog_deletar(self):
        import tkinter.messagebox as mb
        if self._preset_ativo == "Padrão":
            self._set_msg_preview("O modelo 'Padrão' não pode ser deletado.", WARNING)
            return
        ok = mb.askyesno(
            "Deletar modelo",
            f"Deletar o modelo '{self._preset_ativo}'?\nEsta ação não pode ser desfeita.",
            parent=self,
        )
        if not ok:
            return
        p = self._preset_path(self._preset_ativo)
        if p.exists():
            p.unlink()
        self._preset_ativo = "Padrão"
        self._atualizar_dropdown()
        self._preencher_vars()
        self._redesenhar()
        self._set_msg_preview("Modelo deletado.", SUBTEXT)

    # ------------------------------------------------------------------ testar

    def _testar(self):
        """Salva o layout e gera um vídeo de 40s para testar como ficou."""
        # 1. Valida se tem os arquivos necessários
        proj_dir = _projeto_dir()
        cenas_dir  = proj_dir / "projeto" / "cenas"
        audio_dir  = proj_dir / "projeto" / "audio"
        roteiro_dir = proj_dir / "projeto" / "roteiro"

        cenas   = list(cenas_dir.glob("*")) if cenas_dir.exists() else []
        audios  = list(audio_dir.glob("*")) if audio_dir.exists() else []
        roteiros = list(roteiro_dir.glob("*.txt")) if roteiro_dir.exists() else []

        faltando = []
        if not cenas:
            faltando.append("• Imagens em cenas/")
        if not audios:
            faltando.append("• Áudio em audio/")
        if not roteiros:
            faltando.append("• Roteiro em roteiro/")

        if faltando:
            self._set_msg_preview(
                "Faltam arquivos para testar:\n" + "\n".join(faltando),
                DANGER,
            )
            return

        # 2. Grava config_video.json + personagem_config.json com posições atuais da tela
        self._gravar_config_ativa()

        # Desabilita botão e mostra barra de progresso
        self._btn_testar.configure(state="disabled", text="⏳  Gerando...")
        self._set_msg_preview("Gerando preview de 40s...", WARNING)
        self._progress_bar.pack(fill="x", side="bottom")
        self._progress_bar.set(0)
        self._progress_bar.configure(mode="indeterminate")
        self._progress_bar.start()
        self._progress_bar_visivel = True

        proj_dir = _projeto_dir()
        cmd = _engine_cmd([
            "--projeto-dir", str(proj_dir),
            "--preview",
            "--linguas", "pt",
        ])

        log_file = BASE_DIR / "preview_log.txt"

        def _run():
            try:
                import os as _os
                env = _os.environ.copy()
                env["PYTHONUNBUFFERED"]  = "1"
                env["PYTHONIOENCODING"]  = "utf-8"
                env["PYTHONUTF8"]        = "1"
                env["GERADORBB_DATA_DIR"] = str(DATA_DIR)
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    cwd=str(_engine_dir()),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                saida = proc.communicate()[0]
                ok = proc.returncode == 0

                # Salva log completo para diagnóstico
                try:
                    log_file.write_text(
                        f"CMD: {' '.join(str(c) for c in cmd)}\n"
                        f"CWD: {_engine_dir()}\n"
                        f"RETURNCODE: {proc.returncode}\n\n"
                        f"{saida}",
                        encoding="utf-8",
                    )
                except Exception:
                    pass

                # Tenta achar o vídeo gerado
                video = None
                videos_dir = proj_dir / "videos"
                if videos_dir.exists():
                    candidatos = sorted(
                        videos_dir.rglob("*.mp4"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if candidatos:
                        video = candidatos[0]

                # Extrai última linha de erro útil do output
                erro_msg = ""
                if not ok:
                    linhas = [l.strip() for l in saida.splitlines() if l.strip()]
                    erro_msg = linhas[-1] if linhas else "erro desconhecido"

                self.after(0, lambda: self._pos_testar(ok, video, erro_msg))
            except Exception as e:
                self.after(0, lambda: self._pos_testar(False, None, str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _pos_testar(self, ok: bool, video, erro: str = ""):
        self._btn_testar.configure(state="normal", text="🎬  Testar (40s)")
        # Para e esconde a barra de progresso
        try:
            self._progress_bar.stop()
            self._progress_bar.pack_forget()
            self._progress_bar_visivel = False
        except Exception:
            pass
        engine = _engine_dir()
        log_file = engine / "preview_log.txt"
        if ok and video:
            self._set_msg_preview("Preview pronto! Abrindo...", SUCCESS)
            os.startfile(str(video))
        elif ok:
            self._set_msg_preview("Preview gerado! (vídeo não encontrado)", WARNING)
        else:
            if "Falta imagem" in erro:
                self._set_msg_preview(
                    "Cenas não configuradas — vá em 'Organizar Cenas' e salve primeiro.", DANGER)
            else:
                resumo = erro[:120] if erro else "erro desconhecido"
                self._set_msg_preview(f"Erro: {resumo}", DANGER)
            # Abre o log completo automaticamente para diagnóstico
            if log_file.exists():
                try:
                    os.startfile(str(log_file))
                except Exception:
                    pass

    def _set_msg_preview(self, texto: str, cor: str = SUCCESS):
        self._msg.configure(text=texto, text_color=cor)
        self.after(6000, lambda: self._msg.configure(text=""))

    # ------------------------------------------------------------------ resize dinâmico

    def _on_left_resize(self, event):
        """Ajusta o canvas para preencher o frame esquerdo mantendo 9:16."""
        # reserva ~80px para os dois cabeçalhos (cor-legenda + título) + label inferior
        h = max(240, event.height - 80)
        w = int(h * 9 / 16)
        if abs(w - self._VW) < 4 and abs(h - self._VH) < 4:
            return  # variação mínima — ignora para evitar loop
        self._VW = w
        self._VH = h
        self._SX = w / 1080
        self._SY = h / 1920
        self._canvas.config(width=w, height=h)
        try:
            self.after_cancel(self._resize_after_id)
        except Exception:
            pass
        self._resize_after_id = self.after(80, self._redesenhar)

    # ------------------------------------------------------------------ reload

    def _recarregar(self):
        self._tk_imgs.clear()
        self._aplicar_dict(self._PADRAO_FIXO)
        self._redesenhar()
        self._set_msg_preview("Valores padrão restaurados.", INFO)

    def ao_exibir(self):
        self._preset_ativo = "Padrão"
        self._atualizar_dropdown()
        self._preencher_vars()
        self._atualizar_lista_bordas()
        self._redesenhar()


# ===========================================================================
# Tela: Organizar Cenas — cruza roteiro com banco de imagens
# ===========================================================================

class TelaCenas(ctk.CTkFrame):
    """
    Lê o roteiro, extrai nomes de dramas por posição (1-10),
    cruza com imagens disponíveis no banco de imagens (ajuste/saida/)
    e permite montar as cenas em projeto/cenas/ com nomes corretos.
    """

    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela = janela
        self._linhas_ui: dict[str, dict] = {}
        self._tema_ativo: int = 1
        self._logo_ativa: Path | None = None
        self._pasta_extra: Path | None = None   # pasta personalizada do usuário
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        header = SectionHeader(self, "🎞️", "Organizar Cenas",
                               "Leia o roteiro, detecte imagens do banco de imagens e prepare as cenas.")
        header.pack(fill="x")
        _sep(self).pack(fill="x")

        # ---- Barra de ações ----
        barra = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=60)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        bi = ctk.CTkFrame(barra, fg_color="transparent")
        bi.place(relx=0, rely=0.5, x=PAD*2, anchor="w")

        ctk.CTkButton(
            bi, text="📄  Ler Roteiro",
            command=self._ler_roteiro,
            height=36, width=140,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bi, text="🔍  Auto-detectar do banco",
            command=self._auto_detectar,
            height=36, width=210,
            fg_color=BG3, hover_color=BG4,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            bi, text="📁",
            command=self._escolher_pasta_banco,
            height=36, width=36,
            fg_color=BG3, hover_color=BG4,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bi, text="✅  Copiar para Cenas",
            command=self._copiar_para_cenas,
            height=36, width=190,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            bi, text="📂  Banco de imagens",
            command=self._abrir_banco,
            height=36, width=120,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=SUBTEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bi, text="📐  Estrutura",
            command=self._ver_estrutura,
            height=36, width=110,
            fg_color=BG3, hover_color=BG4,
            border_color=INFO, border_width=1,
            text_color=INFO, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 8))

        self._msg = ctk.CTkLabel(bi, text="",
                                  font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                                  text_color=SUCCESS)
        self._msg.pack(side="left")

        _sep(self).pack(fill="x")

        # ---- Cards: Tema + Logo ----
        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", padx=PAD*2, pady=(PAD, 0))

        self._card_tema_frame = _card(cards_row)
        self._card_tema_frame.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._build_card_tema(self._card_tema_frame)

        self._card_logo_frame = _card(cards_row)
        self._card_logo_frame.pack(side="left", fill="x", expand=True)
        self._build_card_logo(self._card_logo_frame)

        _sep(self).pack(fill="x", pady=(PAD, 0))

        # ---- Badge do template ativo ----
        badge_row = ctk.CTkFrame(self, fg_color="transparent")
        badge_row.pack(fill="x", padx=PAD*2, pady=(6, 2))
        self._template_badge = ctk.CTkLabel(
            badge_row, text="",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT, anchor="w",
        )
        self._template_badge.pack(side="left")

        # ---- Cabeçalho da lista ----
        cab = ctk.CTkFrame(self, fg_color=BG3, corner_radius=0, height=36)
        cab.pack(fill="x", padx=PAD*2)
        cab.pack_propagate(False)
        cab_inner = ctk.CTkFrame(cab, fg_color="transparent")
        cab_inner.place(relx=0, rely=0.5, x=18, anchor="w")
        for txt, w in (("Slot", 120), ("Nome (do roteiro)", 256),
                       ("Imagem atribuída", 0)):
            ctk.CTkLabel(cab_inner, text=txt, width=w,
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=SUBTEXT, anchor="w").pack(side="left")

        # ---- Lista scrollável ----
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0,
                                              scrollbar_button_color=BG3,
                                              scrollbar_button_hover_color=ACCENT)
        self._scroll.pack(fill="both", expand=True, padx=PAD*2, pady=(4, PAD))
        self._montar_linhas()

    # ------------------------------------------------------------------ linhas

    def _montar_linhas(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._linhas_ui = {}

        t    = self._template_ativo()
        tipo = t.get("tipo", "livre") if t else "numerado"
        img_dir = _projeto_dir() / "projeto" / "imagens"

        for slot_id, rotulo in self._construir_slots():
            self._criar_linha(slot_id, rotulo)

            # Template "livre": slot_id É o stem do arquivo → atribui diretamente
            if tipo == "livre" and not any(
                    slot_id.startswith(k)
                    for k in ("abertura", "fechamento", "__livre__")):
                for ext in ("png", "jpg", "jpeg", "webp",
                            "PNG", "JPG", "JPEG", "WEBP",
                            "mp4", "mov", "webm", "mkv"):
                    p = img_dir / f"{slot_id}.{ext}"
                    if p.exists():
                        self._atribuir(slot_id, p)
                        # Preenche nome_var com o stem limpo (sem extensão)
                        if slot_id in self._linhas_ui:
                            self._linhas_ui[slot_id]["nome_var"].set(slot_id)
                        break

    def _criar_linha(self, slot_id: str, rotulo: str):
        eh_numerado = slot_id.isdigit()
        cor_slot = ACCENT if eh_numerado else INFO

        row = ctk.CTkFrame(self._scroll, fg_color=BG2, corner_radius=8,
                           border_width=1, border_color=BORDER)
        row.pack(fill="x", pady=2)

        # Barra colorida à esquerda indicando tipo do slot
        barra = ctk.CTkFrame(row, width=4, fg_color=cor_slot, corner_radius=2)
        barra.pack(side="left", fill="y", padx=(0, 0), pady=4)
        barra.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=(10, 10), pady=7)

        # Rótulo do slot (fixo 110px)
        slot_col = ctk.CTkFrame(inner, fg_color="transparent", width=110)
        slot_col.pack(side="left")
        slot_col.pack_propagate(False)
        ctk.CTkLabel(slot_col, text=rotulo,
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=cor_slot, anchor="w").pack(fill="x")

        # Campo nome drama (editável, 240px)
        nome_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            inner, textvariable=nome_var,
            placeholder_text="nome do drama / título...",
            height=32, width=240,
            fg_color=BG3, border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 14))

        # Status da imagem (expandível)
        status_lbl = ctk.CTkLabel(inner, text="  ○  sem imagem",
                                   font=(FONT_FAMILY, FONT_SIZE_SM),
                                   text_color=SUBTEXT, anchor="w")
        status_lbl.pack(side="left", fill="x", expand=True)

        # Botões à direita
        ctk.CTkButton(
            inner, text="📁",
            command=lambda s=slot_id: self._selecionar_manual(s),
            width=34, height=30,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=6,
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            inner, text="✕",
            command=lambda s=slot_id: self._limpar_slot(s),
            width=30, height=30,
            fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
            border_color=BORDER, border_width=1,
            text_color=SUBTEXT, corner_radius=6,
        ).pack(side="right")

        self._linhas_ui[slot_id] = {
            "row":        row,
            "barra":      barra,
            "nome_var":   nome_var,
            "status_lbl": status_lbl,
            "atribuicao": None,
        }

    # ------------------------------------------------------------------ template slots

    def _template_ativo(self) -> dict | None:
        """Retorna o template ativo do config, ou None se não houver."""
        try:
            import gui_templates as _gt
            cfg = _carregar_config()
            tid = cfg.get("template_id", "")
            t = None
            if tid:
                t = _gt.carregar_template_por_id(tid)
            if not t:
                templates = _gt.carregar_templates()
                t = next((x for x in templates if x.get("padrao")), None)
                if not t and templates:
                    t = templates[0]
            return t
        except Exception:
            return None

    def _construir_slots(self) -> list[tuple[str, str]]:
        """Constrói a lista de slots com base no template ativo."""
        import re as _re
        t = self._template_ativo()

        if not t:
            # fallback: Top 10 decrescente
            return [
                ("abertura_pt", "Abertura PT"),
                ("abertura_en", "Abertura EN"),
                *[(str(i), f"  #{i:>2}") for i in range(10, 0, -1)],
                ("fechamento_pt", "Fechamento PT"),
                ("fechamento_en", "Fechamento EN"),
            ]

        slots: list[tuple[str, str]] = []
        tipo  = t.get("tipo", "livre")

        if t.get("abertura"):
            slots.append(("abertura_pt", "Abertura PT"))
            slots.append(("abertura_en", "Abertura EN"))

        if tipo == "numerado":
            n     = t.get("num_itens", 10)
            ordem = t.get("ordem", "decrescente")
            seq   = list(range(n, 0, -1)) if ordem == "decrescente" \
                    else list(range(1, n + 1))
            for i in seq:
                slots.append((str(i), f"  #{i:>2}"))

        elif tipo == "secoes":
            for s in t.get("secoes", []):
                label   = s.get("label", "")
                slot_id = _re.sub(r"[^a-z0-9_]", "",
                                  label.lower().replace(" ", "_"))
                if not slot_id:
                    slot_id = f"secao_{len(slots)}"
                obr = " *" if s.get("obrigatorio") else ""
                slots.append((slot_id, f"  {label}{obr}"))

        else:  # livre — mostra arquivos já em projeto/imagens/ (exceto abertura/fechamento)
            img_dir = _projeto_dir() / "projeto" / "imagens"
            if img_dir.exists():
                exts = {"png", "jpg", "jpeg", "webp",
                        "mp4", "mov", "webm", "mkv"}
                skip = ("abertura", "fechamento")
                found = sorted(
                    p for p in img_dir.iterdir()
                    if p.suffix.lower().lstrip(".") in exts
                    and not any(p.stem.lower().startswith(k) for k in skip)
                )
                for p in found:
                    nm = p.name
                    if len(nm) > 30:
                        nm = nm[:28] + "…"
                    slots.append((p.stem, f"  {nm}"))

            if not any(slot_id not in ("abertura_pt", "abertura_en",
                                       "fechamento_pt", "fechamento_en")
                       for slot_id, _ in slots):
                slots.append(("__livre__",
                               "  (nenhum arquivo — adicione em projeto/imagens/)"))

        if t.get("fechamento"):
            slots.append(("fechamento_pt", "Fechamento PT"))
            slots.append(("fechamento_en", "Fechamento EN"))

        return slots

    def _atualizar_template_badge(self):
        """Atualiza o badge que mostra o template ativo acima da lista."""
        t = self._template_ativo()
        if not t:
            self._template_badge.configure(text="")
            return
        tipo_map = {"livre": "Livre", "numerado": "Numerado", "secoes": "Seções"}
        tipo_label = tipo_map.get(t.get("tipo", "livre"), "")
        icone = t.get("icone", "📋")
        nome  = t.get("nome", "")
        extras = []
        if t.get("tipo") == "numerado":
            n     = t.get("num_itens", 10)
            ordem = t.get("ordem", "decrescente")
            extras.append(f"{n} itens, {ordem}")
        elif t.get("tipo") == "secoes":
            n = len(t.get("secoes", []))
            extras.append(f"{n} seção(ões)")
        if t.get("abertura"):
            extras.append("abertura")
        if t.get("fechamento"):
            extras.append("fechamento")
        extra_str = f"  ·  {', '.join(extras)}" if extras else ""
        self._template_badge.configure(
            text=f"{icone} Template ativo: {nome}  [{tipo_label}]{extra_str}",
            text_color=INFO,
        )

    # ------------------------------------------------------------------ ler roteiro

    def _ler_roteiro(self):
        import re
        rot_dir = _roteiro_dir()
        texto = None
        usou = ""
        for nome in ("roteiro_pt.txt", "roteiro_en.txt"):
            p = rot_dir / nome
            if p.exists():
                try:
                    texto = p.read_text(encoding="utf-8")
                    usou = nome
                    break
                except Exception:
                    pass

        if not texto:
            self._set_msg(f"⚠  Roteiro não encontrado em:\n{rot_dir}", WARNING)
            return

        t    = self._template_ativo()
        tipo = t.get("tipo", "livre") if t else "numerado"

        if tipo == "secoes":
            # Para templates de seções, preenche "nome" com o conteúdo logo
            # após o marcador [NOME_SECAO] (primeira linha não vazia)
            cenas_secao = self._extrair_cenas_secoes(texto)
            preenchidos = 0
            for slot_id, info in self._linhas_ui.items():
                conteudo = cenas_secao.get(slot_id, "")
                if conteudo:
                    info["nome_var"].set(conteudo)
                    preenchidos += 1
            self._set_msg(
                f"✓  {preenchidos} seção(ões) lidas de '{usou}'" if preenchidos else
                f"⚠  Nenhuma seção encontrada em '{usou}'",
                SUCCESS if preenchidos else WARNING)
        else:
            cenas = self._extrair_cenas(texto)
            for slot_id, info in self._linhas_ui.items():
                if slot_id.isdigit():
                    num = int(slot_id)
                    nome = cenas.get(num, "")
                    info["nome_var"].set(nome)
            n = len(cenas)
            self._set_msg(
                f"✓  {n} cenas lidas de '{usou}'" if n else
                f"⚠  Nenhuma cena numerada encontrada em '{usou}'",
                SUCCESS if n else WARNING)

    @staticmethod
    def _norm_nome(s: str) -> str:
        """
        Normaliza nome para comparação: remove acentos (NFD),
        converte para minúsculas, remove tudo que não seja letra/dígito.
        Assim 'Caçadores' == 'cacadores', 'Retaliação' == 'retaliacao'.
        """
        import unicodedata, re
        # NFD decompõe acentos em letra-base + combining mark
        sem_acento = unicodedata.normalize("NFD", s)
        # Remove combining marks (categoria Mn = Mark, Nonspacing)
        sem_acento = "".join(c for c in sem_acento
                             if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]", "", sem_acento.lower())

    def _extrair_cenas(self, texto: str) -> dict[int, str]:
        import re
        cenas: dict[int, str] = {}
        for linha in texto.splitlines():
            limpa = re.sub(r'\*+|_+|#+|\|', '', linha).strip()
            # Aceita separadores: . : ) - – — (hífen, en-dash U+2013, em-dash U+2014)
            # Formato: "10. Nome", "10: Nome", "10) Nome",
            #          "10 – Nome", "10 — Nome", "10 - Nome"
            m = re.match(
                r'^(?:n[uú]mero\s+)?(\d{1,2})\s*'
                r'(?:[.:)]\s*|\s*[\-\u2013\u2014]\s*)'
                r'(.+)',
                limpa, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                if 1 <= num <= 10:
                    nome = m.group(2).strip()
                    # Pega só o nome antes de ": descrição" ou "- descrição"
                    nome = re.split(
                        r':\s+|\s+[\-\u2013\u2014]\s+|\s*[,|]\s*',
                        nome)[0].strip()
                    # Remove parênteses "(pausa)", "(pause)" etc.
                    nome = re.sub(r'\s*\(.*?\)', '', nome).strip()
                    if nome:
                        cenas[num] = nome
        return cenas

    def _extrair_cenas_secoes(self, texto: str) -> dict[str, str]:
        """
        Para templates do tipo 'secoes'. Extrai o primeiro texto não-vazio
        que segue cada marcador [NOME_SECAO] e associa ao slot_id correspondente.
        Retorna {slot_id: primeira_linha_conteudo}.
        """
        import re as _re2
        t = self._template_ativo()
        if not t:
            return {}

        # Mapa: slot_id → label original (para comparar com marcadores)
        slot_labels: dict[str, str] = {}
        for s in t.get("secoes", []):
            label   = s.get("label", "")
            slot_id = _re2.sub(r"[^a-z0-9_]", "",
                               label.lower().replace(" ", "_"))
            if slot_id:
                slot_labels[slot_id] = label

        resultado: dict[str, str] = {}
        secao_atual: str | None = None

        for linha in texto.splitlines():
            # Detecta marcador [NOME_SECAO]
            m = _re2.match(r"^\[(.+)\]\s*$", linha.strip())
            if m:
                nome_marcador = m.group(1).strip()
                secao_atual = None
                for sid, lbl in slot_labels.items():
                    if lbl.lower() == nome_marcador.lower():
                        secao_atual = sid
                        break
                continue

            # Pega a primeira linha de conteúdo após o marcador
            if secao_atual and secao_atual not in resultado:
                limpa = _re2.sub(r'\*+|_+|#+|\|', '', linha).strip()
                if limpa:
                    resultado[secao_atual] = limpa

        return resultado

    # ------------------------------------------------------------------ auto-detectar

    def _auto_detectar(self):
        import os as _os

        # Pastas onde buscar imagens (em ordem de prioridade)
        banco_paths = [
            _projeto_dir() / "projeto" / "imagens",
        ]
        if self._pasta_extra and self._pasta_extra.exists():
            banco_paths.insert(0, self._pasta_extra)

        todas: list[Path] = []
        contagem_por_pasta: dict[str, int] = {}
        for d in banco_paths:
            antes = len(todas)
            if d.exists():
                for ext in ("png", "jpg", "jpeg", "webp",
                            "PNG", "JPG", "JPEG", "WEBP"):
                    # rglob = busca recursiva dentro de subpastas também
                    todas.extend(d.rglob(f"*.{ext}"))
            contagem_por_pasta[str(d)] = len(todas) - antes

        if not todas:
            self._mostrar_diagnostico(banco_paths, [], {})
            return

        _norm = self._norm_nome
        encontrados = 0
        temas_dir = _projeto_dir() / "projeto" / "temas"

        for slot_id, info in self._linhas_ui.items():
            if info["atribuicao"]:
                continue  # já tem imagem

            # Abertura / fechamento — busca pelo tema ativo em temas/
            if not slot_id.isdigit():
                if temas_dir.exists():
                    for ext in ("jpg", "jpeg", "png", "webp",
                                "JPG", "JPEG", "PNG", "WEBP"):
                        p = temas_dir / f"{slot_id}_{self._tema_ativo}.{ext}"
                        if p.exists():
                            self._atribuir(slot_id, p)
                            encontrados += 1
                            break
                continue

            nome_drama = info["nome_var"].get().strip()
            if not nome_drama:
                continue

            # Remove extensão se o roteiro trouxe nome como "Drama.jpg"
            stem, _ext = _os.path.splitext(nome_drama)
            if stem:
                nome_drama = stem.strip()

            nome_n = _norm(nome_drama)
            palavras = set(_norm(w) for w in nome_drama.split() if len(w) > 2)
            melhor: Path | None = None
            melhor_score = 0

            for img in todas:
                img_n = _norm(img.stem)
                if nome_n == img_n:
                    melhor, melhor_score = img, 1000
                    break
                if nome_n in img_n or img_n in nome_n:
                    sc = len(min(nome_n, img_n, key=len)) * 10
                    if sc > melhor_score:
                        melhor, melhor_score = img, sc
                else:
                    palavras_img = set(
                        _norm(w) for w in
                        img.stem.replace('-', ' ').replace('_', ' ').split()
                        if len(w) > 2)
                    comuns = len(palavras & palavras_img)
                    sc = comuns * 8
                    if sc > melhor_score and sc > 0:
                        melhor, melhor_score = img, sc

            if melhor:
                self._atribuir(slot_id, melhor)
                encontrados += 1

        total_slots = sum(1 for sid in self._linhas_ui if sid.isdigit())
        total_ok    = sum(1 for sid, inf in self._linhas_ui.items()
                         if sid.isdigit() and inf["atribuicao"])

        if encontrados:
            self._set_msg(
                f"✓  {encontrados} detectada{'s' if encontrados > 1 else ''}  "
                f"({total_ok}/{total_slots} slots preenchidos)",
                SUCCESS)
        else:
            # Coleta nomes dos slots para o diagnóstico
            nomes_slots = []
            for sid, inf in self._linhas_ui.items():
                if sid.isdigit():
                    n = inf["nome_var"].get().strip()
                    if n:
                        stem, _ = _os.path.splitext(n)
                        nomes_slots.append(stem.strip() or n)
            self._mostrar_diagnostico(banco_paths, todas, nomes_slots)

    # ------------------------------------------------------------------ diagnóstico

    def _mostrar_diagnostico(self, pastas: list, todas: list, nomes_slots: list):
        """Popup de diagnóstico quando auto-detectar não encontra correspondência."""
        self._set_msg("⚠  Sem correspondência — veja diagnóstico", WARNING)

        pop = ctk.CTkToplevel(self)
        pop.title("Diagnóstico — Auto-detectar")
        pop.geometry("580x500")
        pop.resizable(True, True)
        pop.grab_set()
        pop.configure(fg_color=BG2)

        # Header
        h = ctk.CTkFrame(pop, fg_color=BG3, corner_radius=0, height=52)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(h, text="🔍  Diagnóstico do Auto-detectar",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).place(relx=0, rely=0.5, x=PAD, anchor="w")

        scroll = ctk.CTkScrollableFrame(pop, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        def _bloco(titulo, cor=ACCENT):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=(10, 2))
            ctk.CTkFrame(row, width=4, height=16, corner_radius=2,
                         fg_color=cor).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row, text=titulo,
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=cor).pack(side="left")

        def _linha(txt, cor=TEXT):
            ctk.CTkLabel(scroll, text=txt,
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=cor, anchor="w",
                         justify="left").pack(anchor="w", padx=(14, 0))

        # Pastas verificadas
        _bloco("Pastas verificadas")
        for p in pastas:
            existe = Path(p).exists()
            n = sum(1 for f in todas if str(f).startswith(str(p)))
            cor = SUCCESS if n > 0 else (SUBTEXT if existe else DANGER)
            icone = "✓" if n > 0 else ("◦" if existe else "✗")
            _linha(f"  {icone}  {p}  ({n} imagens)", cor)

        if not todas:
            _bloco("Resultado", DANGER)
            _linha("Nenhuma imagem encontrada nas pastas acima.", DANGER)
            _linha("")
            _bloco("O que fazer", WARNING)
            _linha("1. Clique em '📂 Banco de imagens' para abrir a pasta correta.")
            _linha("2. Copie suas imagens para essa pasta.")
            _linha("3. OU clique em '📁' ao lado de 'Auto-detectar' para escolher")
            _linha("   qualquer pasta com suas imagens.")
        else:
            # Mostra exemplos de imagens encontradas
            _bloco(f"Imagens encontradas ({len(todas)} total)", INFO)
            for img in sorted(todas)[:8]:
                _linha(f"  • {img.name}", SUBTEXT)
            if len(todas) > 8:
                _linha(f"  … e mais {len(todas) - 8}", SUBTEXT)

            # Mostra nomes dos slots
            if nomes_slots:
                _bloco("Nomes dos slots (do roteiro)")
                for n in nomes_slots[:8]:
                    _linha(f"  • {n}", TEXT)
                if len(nomes_slots) > 8:
                    _linha(f"  … e mais {len(nomes_slots) - 8}", SUBTEXT)

            _bloco("Por que não casou?", WARNING)
            _linha("Os nomes das imagens precisam ser parecidos com os nomes do roteiro.")
            _linha("Exemplo:  roteiro = 'Caçadores de Demônios'")
            _linha("          arquivo  = 'Cacadores de Demonios.jpg'  ✓")
            _linha("          arquivo  = 'cacadores_de_demonios.jpg'  ✓")
            _linha("          arquivo  = 'kdrama_001.jpg'             ✗ (sem palavras em comum)")
            _linha("")
            _bloco("Solução rápida", SUCCESS)
            _linha("Renomeie os arquivos com o nome do drama ou use '📁'")
            _linha("para apontar a pasta correta e tente novamente.")

        # Botão fechar
        ctk.CTkButton(
            pop, text="Fechar",
            command=pop.destroy,
            height=38, width=120,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(pady=(0, PAD))

    # ------------------------------------------------------------------ helpers UI

    def _atribuir(self, slot_id: str, caminho: Path):
        info = self._linhas_ui.get(slot_id)
        if not info:
            return
        info["atribuicao"] = caminho
        nome = caminho.name
        if len(nome) > 48:
            nome = "…" + nome[-46:]
        info["status_lbl"].configure(text=f"  ✅  {nome}", text_color=SUCCESS)
        info["row"].configure(fg_color=BG_ROW_SUCCESS, border_color=SUCCESS)
        if "barra" in info:
            info["barra"].configure(fg_color=SUCCESS)

    def _limpar_slot(self, slot_id: str):
        info = self._linhas_ui.get(slot_id)
        if not info:
            return
        info["atribuicao"] = None
        info["status_lbl"].configure(text="  ○  sem imagem", text_color=SUBTEXT)
        info["row"].configure(fg_color=BG2, border_color=BORDER)
        # restaura cor da barra baseada no tipo do slot
        if "barra" in info:
            cor = ACCENT if slot_id.isdigit() else INFO
            info["barra"].configure(fg_color=cor)

    def _selecionar_manual(self, slot_id: str):
        import tkinter.filedialog as fd
        pasta_init = _projeto_dir() / "projeto" / "imagens"
        pasta_init.mkdir(parents=True, exist_ok=True)
        caminho = fd.askopenfilename(
            title=f"Selecionar imagem — slot {slot_id}",
            initialdir=str(pasta_init),
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.PNG *.JPG *.JPEG *.WEBP"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if caminho:
            self._atribuir(slot_id, Path(caminho))

    def _escolher_pasta_banco(self):
        """Permite o usuário apontar qualquer pasta como banco de imagens."""
        import tkinter.filedialog as fd
        pasta = fd.askdirectory(
            title="Selecionar pasta com as imagens do banco",
            initialdir=str(_projeto_dir()),
        )
        if pasta:
            self._pasta_extra = Path(pasta)
            self._set_msg(f"📁  Pasta: …/{self._pasta_extra.name}", INFO)

    def _abrir_banco(self):
        pasta = _projeto_dir() / "projeto" / "imagens"
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(pasta))

    def _ver_estrutura(self):
        """Abre popup mostrando a estrutura de arquivos esperada pelo template ativo."""
        import gui_templates as _gt_cenas
        t = self._template_ativo()
        if not t:
            self._set_msg("⚠  Nenhum template ativo encontrado.", WARNING)
            return

        texto = _gt_cenas.preview_estrutura(t)

        pop = ctk.CTkToplevel(self)
        pop.title(f"Estrutura — {t.get('nome', 'Template')}")
        pop.geometry("480x420")
        pop.resizable(False, True)
        pop.grab_set()
        pop.configure(fg_color=BG2)

        header = ctk.CTkFrame(pop, fg_color=BG3, corner_radius=0, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header,
                     text=f"{t.get('icone','📋')}  {t.get('nome','')}  —  Estrutura de arquivos esperada",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT).pack(side="left", padx=PAD, pady=12)

        txt = ctk.CTkTextbox(pop, fg_color=BG, text_color=INFO,
                             font=FONT_MONO, corner_radius=0,
                             border_width=0, state="normal")
        txt.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        txt.insert("1.0", texto)
        txt.configure(state="disabled")

        ctk.CTkButton(pop, text="Fechar",
                      command=pop.destroy,
                      height=36, width=120,
                      fg_color=ACCENT, hover_color=ACCENT3,
                      text_color=TEXT, corner_radius=CORNER_R,
                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold")).pack(pady=(0, PAD))

    # ------------------------------------------------------------------ card tema

    def _listar_temas(self) -> list[int]:
        """Retorna lista de números de tema disponíveis em temas/."""
        temas_dir = _projeto_dir() / "projeto" / "temas"
        if not temas_dir.exists():
            return []
        numeros: set[int] = set()
        import re
        for f in temas_dir.iterdir():
            m = re.search(r'_(\d+)\.[^.]+$', f.name)
            if m:
                numeros.add(int(m.group(1)))
        return sorted(numeros)

    def _build_card_tema(self, parent):
        """Constrói o card de seleção de tema dentro de `parent`."""
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        # Título
        row_tit = ctk.CTkFrame(inner, fg_color="transparent")
        row_tit.pack(fill="x")
        ctk.CTkFrame(row_tit, width=3, height=16, corner_radius=2,
                     fg_color=ACCENT2).pack(side="left", padx=(0, 8))
        _label(row_tit, "Tema (abertura + fechamento)",
               size=FONT_SIZE_SM, bold=True).pack(side="left")

        # Descrição
        _label(inner, "Clique num número para selecionar o tema.",
               size=FONT_SIZE_SM-1, color=SUBTEXT).pack(anchor="w", pady=(2, 6))

        # Linha de botões de tema
        self._tema_btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        self._tema_btn_row.pack(anchor="w")
        self._tema_btn_refs: dict[int, ctk.CTkButton] = {}
        self._atualizar_card_tema()

    def _atualizar_card_tema(self):
        """Atualiza os botões de tema disponíveis."""
        for w in self._tema_btn_row.winfo_children():
            w.destroy()
        self._tema_btn_refs = {}

        temas = self._listar_temas()
        if not temas:
            _label(self._tema_btn_row,
                   "Nenhum tema encontrado em projeto/temas/",
                   size=FONT_SIZE_SM-1, color=SUBTEXT).pack(side="left")
            return

        for n in temas:
            ativo = (n == self._tema_ativo)
            btn = ctk.CTkButton(
                self._tema_btn_row,
                text=f"Tema {n}",
                command=lambda num=n: self._selecionar_tema(num),
                width=72, height=30,
                fg_color=ACCENT if ativo else BG3,
                hover_color=ACCENT3 if ativo else BG4,
                border_color=ACCENT if ativo else BORDER,
                border_width=2 if ativo else 1,
                text_color=TEXT, corner_radius=6,
                font=(FONT_FAMILY, FONT_SIZE_SM, "bold" if ativo else "normal"),
            )
            btn.pack(side="left", padx=(0, 6))
            self._tema_btn_refs[n] = btn

        # Link para abrir a pasta
        ctk.CTkButton(
            self._tema_btn_row, text="📂",
            command=lambda: os.startfile(
                str(_projeto_dir() / "projeto" / "temas")),
            width=30, height=30,
            fg_color="transparent", hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=SUBTEXT, corner_radius=6,
        ).pack(side="left", padx=(4, 0))

    def _selecionar_tema(self, n: int):
        """Seleciona o tema n e preenche os slots de abertura/fechamento."""
        self._tema_ativo = n
        temas_dir = _projeto_dir() / "projeto" / "temas"
        slots_tema = ("abertura_pt", "abertura_en",
                      "fechamento_pt", "fechamento_en")
        preenchidos = 0
        for slot_id in slots_tema:
            if temas_dir.exists():
                for ext in ("jpg", "jpeg", "png", "webp",
                            "JPG", "JPEG", "PNG", "WEBP"):
                    p = temas_dir / f"{slot_id}_{n}.{ext}"
                    if p.exists():
                        self._atribuir(slot_id, p)
                        preenchidos += 1
                        break
        self._atualizar_card_tema()
        self._set_msg(
            f"✓  Tema {n} selecionado ({preenchidos} imagens preenchidas)",
            SUCCESS if preenchidos else WARNING)

    # ------------------------------------------------------------------ card logo

    def _listar_logos(self) -> list[Path]:
        """Retorna logos disponíveis em projeto/logos/."""
        logos_dir = _projeto_dir() / "projeto" / "logos"
        if not logos_dir.exists():
            return []
        imgs = []
        for ext in ("png", "PNG", "jpg", "JPG", "jpeg", "JPEG", "webp", "WEBP"):
            imgs.extend(logos_dir.glob(f"*.{ext}"))
        return sorted(set(imgs), key=lambda p: p.name)

    def _build_card_logo(self, parent):
        """Constrói o card de seleção de logo dentro de `parent`."""
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        row_tit = ctk.CTkFrame(inner, fg_color="transparent")
        row_tit.pack(fill="x")
        ctk.CTkFrame(row_tit, width=3, height=16, corner_radius=2,
                     fg_color=ACCENT2).pack(side="left", padx=(0, 8))
        _label(row_tit, "Logo do canal",
               size=FONT_SIZE_SM, bold=True).pack(side="left")

        _label(inner, "Selecione a logo que será usada no vídeo.",
               size=FONT_SIZE_SM-1, color=SUBTEXT).pack(anchor="w", pady=(2, 6))

        self._logo_btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        self._logo_btn_row.pack(anchor="w")
        self._atualizar_card_logo()

    def _atualizar_card_logo(self):
        """Atualiza a lista de logos disponíveis."""
        for w in self._logo_btn_row.winfo_children():
            w.destroy()

        logos = self._listar_logos()
        if not logos:
            _label(self._logo_btn_row,
                   "Nenhuma logo encontrada em projeto/logos/",
                   size=FONT_SIZE_SM-1, color=SUBTEXT).pack(side="left")
            # Botão para abrir pasta
            ctk.CTkButton(
                self._logo_btn_row, text="📂",
                command=lambda: os.startfile(
                    str(_projeto_dir() / "projeto" / "logos")),
                width=30, height=30,
                fg_color="transparent", hover_color=BG4,
                border_color=BORDER, border_width=1,
                text_color=SUBTEXT, corner_radius=6,
            ).pack(side="left", padx=(8, 0))
            return

        # Se nenhuma logo selecionada, seleciona a primeira automaticamente
        if self._logo_ativa is None:
            self._logo_ativa = logos[0]

        for logo_path in logos:
            ativo = (self._logo_ativa
                     and logo_path.resolve() == self._logo_ativa.resolve())
            # Nome curto para o botão
            nome_curto = logo_path.stem
            if len(nome_curto) > 12:
                nome_curto = nome_curto[:11] + "…"
            btn = ctk.CTkButton(
                self._logo_btn_row,
                text=nome_curto,
                command=lambda lp=logo_path: self._selecionar_logo(lp),
                width=90, height=30,
                fg_color=ACCENT if ativo else BG3,
                hover_color=ACCENT3 if ativo else BG4,
                border_color=ACCENT if ativo else BORDER,
                border_width=2 if ativo else 1,
                text_color=TEXT, corner_radius=6,
                font=(FONT_FAMILY, FONT_SIZE_SM,
                      "bold" if ativo else "normal"),
            )
            btn.pack(side="left", padx=(0, 6))

        # Botão para abrir pasta
        ctk.CTkButton(
            self._logo_btn_row, text="📂",
            command=lambda: os.startfile(
                str(_projeto_dir() / "projeto" / "logos")),
            width=30, height=30,
            fg_color="transparent", hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=SUBTEXT, corner_radius=6,
        ).pack(side="left", padx=(4, 0))

        # Lbl logo ativa
        if self._logo_ativa:
            nome = self._logo_ativa.name
            if len(nome) > 30:
                nome = "…" + nome[-28:]
            _label(self._logo_btn_row, f"  ✓ {nome}",
                   size=FONT_SIZE_SM-1, color=SUCCESS).pack(side="left", padx=6)

    def _selecionar_logo(self, logo_path: Path):
        self._logo_ativa = logo_path
        self._atualizar_card_logo()
        self._set_msg(f"✓  Logo selecionada: {logo_path.name}", SUCCESS)

    def _set_msg(self, texto: str, cor: str = SUCCESS):
        self._msg.configure(text=texto, text_color=cor)
        self.after(5000, lambda: self._msg.configure(text=""))

    # ------------------------------------------------------------------ copiar

    def _copiar_para_cenas(self):
        import shutil
        cenas_dir = _imagens_dir()
        cenas_dir.mkdir(parents=True, exist_ok=True)

        copiados = erros = sem_imagem = 0
        for slot_id, info in self._linhas_ui.items():
            origem = info.get("atribuicao")
            if not origem:
                sem_imagem += 1
                continue
            origem = Path(origem)
            if not origem.exists():
                erros += 1
                continue
            destino = cenas_dir / f"{slot_id}{origem.suffix.lower()}"
            try:
                shutil.copy2(str(origem), str(destino))
                copiados += 1
            except Exception:
                erros += 1

        # Copia a logo ativa para cenas/ (engine.py espera logo.png lá)
        logo_copiada = False
        if self._logo_ativa and self._logo_ativa.exists():
            try:
                destino_logo = cenas_dir / f"logo{self._logo_ativa.suffix.lower()}"
                shutil.copy2(str(self._logo_ativa), str(destino_logo))
                logo_copiada = True
            except Exception:
                erros += 1

        if copiados:
            msg = f"✓  {copiados} imagens copiadas para cenas/"
            if logo_copiada:
                msg += "  |  logo copiada"
            if erros:
                msg += f"  |  {erros} erros"
            if sem_imagem:
                msg += f"  |  {sem_imagem} slots sem imagem"
            self._set_msg(msg, SUCCESS)
            if hasattr(self._janela, "set_status"):
                self._janela.set_status(f"{copiados} imagens copiadas", SUCCESS)
        else:
            self._set_msg(
                "⚠  Nenhuma imagem para copiar. "
                "Use 'Ler Roteiro' + 'Auto-detectar' ou selecione manualmente (📁).",
                WARNING)

    def ao_exibir(self):
        # Reseta seleções ao trocar de projeto
        self._tema_ativo = 1
        self._logo_ativa = None
        self._atualizar_template_badge()
        self._montar_linhas()
        self._ler_roteiro()
        # Atualiza cards com temas/logos disponíveis no projeto ativo
        self._atualizar_card_tema()
        self._atualizar_card_logo()


# ===========================================================================
# Tela: Gerenciar Projetos
# ===========================================================================

class TelaGerenciarProjetos(ctk.CTkFrame):
    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela = janela
        self._build_ui()

    def _build_ui(self):
        header = SectionHeader(self, "📺", "Canais",
                               "Gerencie seus canais de vídeo.")
        header.pack(fill="x")
        _sep(self).pack(fill="x")

        # Header com botão criar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=PAD*2, pady=(PAD, 0))

        _label(top_bar, "Pasta dos canais:", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")
        pasta_banco = _banco_dir()
        ctk.CTkLabel(top_bar, text=str(pasta_banco),
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            top_bar, text="+ Novo canal",
            command=self._dialog_novo_projeto,
            height=36, width=150,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="right")

        ctk.CTkButton(
            top_bar, text="↺ Atualizar",
            command=self.ao_exibir,
            height=36, width=110,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="right", padx=(0, 8))

        _sep(self).pack(fill="x", padx=PAD*2, pady=(PAD, 0))

        # Lista de projetos
        self._lista = ctk.CTkFrame(self, fg_color="transparent")
        self._lista.pack(fill="both", expand=True, padx=PAD*2, pady=PAD)

    def ao_exibir(self):
        for w in self._lista.winfo_children():
            w.destroy()

        projetos = _listar_projetos()
        ativo    = _projeto_ativo()

        if not projetos:
            inner = ctk.CTkFrame(self._lista, fg_color="transparent")
            inner.pack(expand=True, fill="both", pady=60)
            ctk.CTkLabel(inner, text="📺", font=(FONT_FAMILY, 56)).pack()
            _label(inner, "Nenhum canal encontrado", size=FONT_SIZE_LG, bold=True, color=SUBTEXT).pack(pady=(12, 0))
            _label(inner, "Clique em \"+ Novo canal\" para criar seu primeiro canal.",
                   size=FONT_SIZE_SM, color=SUBTEXT).pack(pady=(6, 0))
            return

        for nome in projetos:
            self._linha_projeto(nome, nome == ativo)

    def _linha_projeto(self, nome: str, ativo: bool):
        cor_borda = ACCENT if ativo else BORDER

        row = ctk.CTkFrame(self._lista, fg_color=BG2, corner_radius=CORNER_R,
                           border_width=2 if ativo else 1, border_color=cor_borda)
        row.pack(fill="x", pady=5)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        # Ícone + nome
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        nome_row = ctk.CTkFrame(left, fg_color="transparent")
        nome_row.pack(anchor="w")
        ctk.CTkLabel(nome_row, text="📺", font=(FONT_FAMILY, 20)).pack(side="left", padx=(0, 8))
        _label(nome_row, nome, size=FONT_SIZE_LG, bold=True).pack(side="left")
        if ativo:
            badge = ctk.CTkFrame(nome_row, fg_color=ACCENT, corner_radius=8)
            badge.pack(side="left", padx=(10, 0))
            ctk.CTkLabel(badge, text="✓ ATIVO",
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=TEXT).pack(padx=8, pady=2)

        # Stats do projeto
        proj_path = _banco_dir() / nome
        stats = self._stats_projeto(proj_path)
        ctk.CTkLabel(left, text=stats,
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w", pady=(4, 0))

        # Botões
        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(side="right")

        if not ativo:
            ctk.CTkButton(
                btns, text="✓ Ativar",
                command=lambda n=nome: self._ativar(n),
                height=34, width=90,
                fg_color=ACCENT, hover_color=ACCENT3,
                text_color=TEXT, corner_radius=8,
                font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btns, text="📋 Duplicar",
            command=lambda n=nome: self._dialog_duplicar_projeto(n),
            height=34, width=96,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btns, text="📂 Pasta",
            command=lambda p=proj_path: os.startfile(str(p)) if p.exists() else None,
            height=34, width=84,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 6))

        if not ativo:
            ctk.CTkButton(
                btns, text="🗑 Remover",
                command=lambda n=nome: self._remover(n),
                height=34, width=100,
                fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
                border_color=DANGER, border_width=1,
                text_color=DANGER, corner_radius=8,
                font=(FONT_FAMILY, FONT_SIZE_SM),
            ).pack(side="left")

    def _stats_projeto(self, proj_path: Path) -> str:
        partes = []
        cenas = proj_path / "projeto" / "cenas"
        n_img = 0
        if cenas.exists():
            for ext in ("png","jpg","jpeg","webp"):
                n_img += len(list(cenas.glob(f"*.{ext}")))
        partes.append(f"🖼️ {n_img} imagens")

        audio = proj_path / "projeto" / "audio"
        n_audio = 0
        if audio.exists():
            for lang in ("pt","en"):
                for ext in ("mp3","wav","ogg","m4a"):
                    if list(audio.glob(f"*{lang}*.{ext}")):
                        n_audio += 1
                        break
        partes.append(f"🔊 {n_audio}/2 áudios")

        rot = proj_path / "projeto" / "roteiro"
        n_rot = 0
        if rot.exists():
            for lang in ("pt","en"):
                if (rot/f"roteiro_{lang}.txt").exists():
                    n_rot += 1
        partes.append(f"📄 {n_rot}/2 roteiros")

        vid = proj_path / "videos"
        n_vid = sum(1 for _ in vid.rglob("*.mp4")) if vid.exists() else 0
        partes.append(f"🎬 {n_vid} vídeos")

        return "   ".join(partes)

    def _ativar(self, nome: str):
        cfg = _carregar_config()
        cfg["projeto_ativo"] = nome
        _salvar_config(cfg)
        # Atualiza selector na sidebar
        if hasattr(self._janela, "_atualizar_seletor_projeto"):
            self._janela._atualizar_seletor_projeto()
        self.ao_exibir()

    def _dialog_novo_projeto(self):
        """Abre um dialog inline para criar novo projeto."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Novo Canal")
        dialog.geometry("380x200")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()

        # Centraliza
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        dialog.geometry(f"380x200+{(sw-380)//2}+{(sh-200)//2}")

        dialog.configure(fg_color=BG2)

        ctk.CTkLabel(dialog, text="Nome do novo canal",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(pady=(20, 6))
        ctk.CTkLabel(dialog, text="Use letras, números e hífens. Ex: rotadosherois",
                     font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT).pack()

        entry = ctk.CTkEntry(dialog, placeholder_text="nome-do-canal",
                             height=44, width=320,
                             fg_color=BG3, border_color=BORDER, border_width=1,
                             text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD))
        entry.pack(pady=(16, 0))
        entry.focus()

        msg = ctk.CTkLabel(dialog, text="", text_color=DANGER,
                           font=(FONT_FAMILY, FONT_SIZE_SM))
        msg.pack(pady=(6, 0))

        def _criar():
            nome = entry.get().strip().lower()
            nome = "".join(c if c.isalnum() or c in "-_" else "-" for c in nome)
            if not nome:
                msg.configure(text="Digite um nome válido.")
                return
            proj = _banco_dir() / nome
            if proj.exists():
                msg.configure(text="Já existe um canal com esse nome.")
                return
            _criar_projeto(nome)
            # Ativa o novo projeto
            cfg = _carregar_config()
            cfg["projeto_ativo"] = nome
            _salvar_config(cfg)
            if hasattr(self._janela, "_atualizar_seletor_projeto"):
                self._janela._atualizar_seletor_projeto()
            dialog.destroy()
            self.ao_exibir()

        entry.bind("<Return>", lambda _: _criar())

        ctk.CTkButton(dialog, text="Criar canal", command=_criar,
                      height=40, width=200,
                      fg_color=ACCENT, hover_color=ACCENT3,
                      text_color=TEXT, corner_radius=CORNER_R,
                      font=(FONT_FAMILY, FONT_SIZE_MD, "bold")).pack(pady=(8, 0))

    def _dialog_duplicar_projeto(self, origem: str):
        """Abre dialog para duplicar um projeto existente."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Duplicar Canal")
        dialog.geometry("400x230")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()
        dialog.configure(fg_color=BG2)

        dialog.update_idletasks()
        sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
        dialog.geometry(f"400x230+{(sw-400)//2}+{(sh-230)//2}")

        ctk.CTkLabel(dialog, text=f'Duplicar  "{origem}"',
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(pady=(20, 4))
        ctk.CTkLabel(dialog, text="Nome para a cópia (cenas e roteiro serão copiados):",
                     font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT).pack()

        entry = ctk.CTkEntry(dialog, placeholder_text=f"{origem}-copia",
                             height=44, width=340,
                             fg_color=BG3, border_color=BORDER, border_width=1,
                             text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_MD))
        entry.pack(pady=(12, 0))
        entry.insert(0, f"{origem}-copia")
        entry.focus()

        msg = ctk.CTkLabel(dialog, text="", text_color=DANGER,
                           font=(FONT_FAMILY, FONT_SIZE_SM))
        msg.pack(pady=(4, 0))

        btn = ctk.CTkButton(dialog, text="📋  Duplicar",
                            height=40, width=200,
                            fg_color=ACCENT, hover_color=ACCENT3,
                            text_color=TEXT, corner_radius=CORNER_R,
                            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"))
        btn.pack(pady=(6, 0))

        def _duplicar():
            destino = entry.get().strip().lower()
            destino = "".join(c if c.isalnum() or c in "-_" else "-" for c in destino)
            if not destino:
                msg.configure(text="Digite um nome válido.")
                return
            if (_banco_dir() / destino).exists():
                msg.configure(text="Já existe um projeto com esse nome.")
                return
            btn.configure(state="disabled", text="Copiando...")
            dialog.update()

            def _run():
                try:
                    _duplicar_projeto(origem, destino)
                    def _ok():
                        dialog.destroy()
                        if hasattr(self._janela, "_atualizar_seletor_projeto"):
                            self._janela._atualizar_seletor_projeto()
                        self.ao_exibir()
                    self.after(0, _ok)
                except Exception as e:
                    self.after(0, lambda: msg.configure(
                        text=f"Erro ao duplicar: {e}"))
                    self.after(0, lambda: btn.configure(
                        state="normal", text="📋  Duplicar"))

            threading.Thread(target=_run, daemon=True).start()

        entry.bind("<Return>", lambda _: _duplicar())
        btn.configure(command=_duplicar)

    def _remover(self, nome: str):
        """Abre confirmação antes de deletar."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Remover Projeto")
        dialog.geometry("360x180")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        dialog.geometry(f"360x180+{(sw-360)//2}+{(sh-180)//2}")
        dialog.configure(fg_color=BG2)

        ctk.CTkLabel(dialog, text="⚠️  Remover projeto?",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=DANGER).pack(pady=(20, 6))
        ctk.CTkLabel(dialog, text=f"Isso apagará a pasta \"{nome}\" e todos seus arquivos.\nEssa ação não pode ser desfeita.",
                     font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
                     wraplength=320, justify="center").pack()

        btns = ctk.CTkFrame(dialog, fg_color="transparent")
        btns.pack(pady=(16, 0))

        def _confirmar():
            import shutil
            proj = _banco_dir() / nome
            try:
                shutil.rmtree(proj)
            except Exception:
                pass
            dialog.destroy()
            self.ao_exibir()

        ctk.CTkButton(btns, text="Sim, remover",
                      command=_confirmar,
                      height=38, width=140,
                      fg_color=DANGER, hover_color=DANGER_HOVER,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold")).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btns, text="Cancelar",
                      command=dialog.destroy,
                      height=38, width=100,
                      fg_color=BG3, hover_color=BG4,
                      border_color=BORDER, border_width=1,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")


# ===========================================================================
# Tela Admin — Painel de gerenciamento de usuários e licenças
# ===========================================================================

class TelaAdmin(ctk.CTkFrame):
    """
    Painel exclusivo para o administrador.
    Visível apenas quando user["is_admin"] == True.
    Lista todos os usuários, permite gerar e revogar licenças.
    """

    _TIPOS_LICENCA = ["7dias", "30dias", "60dias", "90dias", "vitalicio"]
    _LABELS_TIPO   = {
        "7dias":     "7 dias",
        "30dias":    "30 dias",
        "60dias":    "60 dias",
        "90dias":    "90 dias",
        "vitalicio": "Vitalício",
    }

    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela = janela
        self._usuarios: list = []
        self._build()

    # ------------------------------------------------------------------ build

    def _build(self):
        # Header
        header = SectionHeader(self, "🛡️", "Painel Admin", "Gerencie usuários e licenças")
        header.pack(fill="x")

        # Barra de controles
        barra = ctk.CTkFrame(self, fg_color=BG3, corner_radius=0, height=56)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        inner = ctk.CTkFrame(barra, fg_color="transparent")
        inner.place(relx=0, rely=0.5, x=PAD * 2, anchor="w")

        self._entry_busca = ctk.CTkEntry(
            inner, placeholder_text="Buscar por nome ou e-mail...",
            width=280, height=34,
            fg_color=BG4, border_color=BORDER, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", lambda e: self._aplicar_filtro())

        ctk.CTkButton(
            inner, text="Atualizar",
            command=self.ao_exibir,
            width=100, height=34,
            fg_color=BG4, hover_color=BG5,
            border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(8, 0))

        # Cabeçalho da tabela
        cabec = ctk.CTkFrame(self, fg_color=BG4, corner_radius=0, height=36)
        cabec.pack(fill="x")
        cabec.pack_propagate(False)
        for txt, w in [("Usuário", 220), ("E-mail", 240), ("Licença", 140), ("Criado em", 110), ("Ações", 200)]:
            ctk.CTkLabel(cabec, text=txt,
                         font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                         text_color=SUBTEXT, width=w, anchor="w",
                         ).pack(side="left", padx=(PAD, 0))

        # Área scrollável
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self._scroll.pack(fill="both", expand=True)

        self.after(100, self.ao_exibir)

    # ------------------------------------------------------------------ dados

    def ao_exibir(self):
        self._janela.set_status("Carregando usuários...", WARNING)
        threading.Thread(target=self._carregar, daemon=True).start()

    def _carregar(self):
        usuarios = auth.admin_listar_usuarios()
        self.after(0, lambda: self._renderizar(usuarios))

    def _renderizar(self, usuarios: list):
        self._usuarios = usuarios
        self._aplicar_filtro()
        self._janela.set_status(f"{len(usuarios)} usuários", SUCCESS)

    def _aplicar_filtro(self):
        try:
            termo = self._entry_busca.get().lower()
        except Exception:
            termo = ""
        filtrados = [
            u for u in self._usuarios
            if termo in u["nome"].lower() or termo in u["email"].lower()
        ] if termo else list(self._usuarios)
        self._desenhar_lista(filtrados)

    # ------------------------------------------------------------------ lista

    def _desenhar_lista(self, usuarios: list):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not usuarios:
            ctk.CTkLabel(self._scroll, text="Nenhum usuário encontrado.",
                         font=(FONT_FAMILY, FONT_SIZE_MD),
                         text_color=SUBTEXT).pack(pady=40)
            return

        for i, u in enumerate(usuarios):
            bg = BG3 if i % 2 == 0 else BG
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0, height=52)
            row.pack(fill="x")
            row.pack_propagate(False)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="both", padx=PAD)
            inner.pack_propagate(False)

            # Avatar + nome
            nome_frame = ctk.CTkFrame(inner, fg_color="transparent", width=220)
            nome_frame.pack(side="left", fill="y")
            nome_frame.pack_propagate(False)

            av = ctk.CTkFrame(nome_frame, width=30, height=30,
                              corner_radius=15,
                              fg_color=ACCENT if u.get("is_admin") else BG5)
            av.place(relx=0, rely=0.5, anchor="w")
            av.pack_propagate(False)
            inicial = (u["nome"] or u["email"] or "?")[0].upper()
            ctk.CTkLabel(av, text=inicial, font=(FONT_FAMILY, 11, "bold"),
                         text_color=TEXT).place(relx=0.5, rely=0.5, anchor="center")

            sufixo = " ★" if u.get("is_admin") else ""
            nome_lbl = ctk.CTkLabel(nome_frame,
                                    text=(u["nome"] or "(sem nome)") + sufixo,
                                    font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                                    text_color=ACCENT if u.get("is_admin") else TEXT,
                                    anchor="w")
            nome_lbl.place(relx=0, rely=0.5, x=38, anchor="w")

            # E-mail
            email_frame = ctk.CTkFrame(inner, fg_color="transparent", width=240)
            email_frame.pack(side="left", fill="y")
            email_frame.pack_propagate(False)
            ctk.CTkLabel(email_frame, text=u["email"],
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=SUBTEXT, anchor="w").place(relx=0, rely=0.5, anchor="w")

            # Badge licença
            lic_frame = ctk.CTkFrame(inner, fg_color="transparent", width=140)
            lic_frame.pack(side="left", fill="y")
            lic_frame.pack_propagate(False)
            badge_txt, badge_cor = self._badge(u)
            ctk.CTkLabel(lic_frame, text=badge_txt,
                         font=(FONT_FAMILY, 10, "bold"),
                         text_color=badge_cor, anchor="w").place(relx=0, rely=0.5, anchor="w")

            # Criado em
            data_frame = ctk.CTkFrame(inner, fg_color="transparent", width=110)
            data_frame.pack(side="left", fill="y")
            data_frame.pack_propagate(False)
            ctk.CTkLabel(data_frame, text=u["criado_em"],
                         font=(FONT_FAMILY, FONT_SIZE_SM),
                         text_color=SUBTEXT, anchor="w").place(relx=0, rely=0.5, anchor="w")

            # Ações (não aparecem para admin)
            if not u.get("is_admin"):
                acoes = ctk.CTkFrame(inner, fg_color="transparent")
                acoes.pack(side="left", fill="y")

                ctk.CTkButton(
                    acoes, text="+ Licença",
                    command=lambda uid=u["user_id"], nm=u["nome"]: self._dialog_licenca(uid, nm),
                    width=85, height=28,
                    fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                    text_color=TEXT, corner_radius=6,
                    font=(FONT_FAMILY, 11, "bold"),
                ).place(relx=0, rely=0.5, anchor="w")

                if u["lic_tipo"]:
                    ctk.CTkButton(
                        acoes, text="Revogar",
                        command=lambda uid=u["user_id"]: self._revogar(uid),
                        width=70, height=28,
                        fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
                        border_color=DANGER, border_width=1,
                        text_color=DANGER, corner_radius=6,
                        font=(FONT_FAMILY, 11),
                    ).place(relx=0, rely=0.5, x=92, anchor="w")

    # ------------------------------------------------------------------ badge

    def _badge(self, u: dict) -> tuple:
        tipo = u.get("lic_tipo")
        dias = u.get("lic_dias")
        if not tipo:
            return ("x Sem licenca", DANGER)
        if tipo == "vitalicio":
            return ("v Vitalicio", SUCCESS)
        label = self._LABELS_TIPO.get(tipo, tipo)
        if dias is None:
            return (f"v {label}", SUCCESS)
        if dias < 0:
            return ("x Expirada", DANGER)
        if dias <= 7:
            return (f"! {dias}d restantes", DANGER)
        if dias <= 15:
            return (f"~ {dias}d restantes", WARNING)
        return (f"v {dias}d restantes", SUCCESS)

    # ------------------------------------------------------------------ acoes

    def _dialog_licenca(self, user_id: str, nome: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Gerar Licença")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        dialog.geometry(f"360x230+{(sw-360)//2}+{(sh-230)//2}")
        dialog.configure(fg_color=BG2)

        ctk.CTkLabel(dialog, text="Gerar Licença",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(pady=(20, 4))
        ctk.CTkLabel(dialog, text=f"Usuário: {nome}",
                     font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack()

        ctk.CTkLabel(dialog, text="Duração:",
                     font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                     text_color=TEXT).pack(pady=(16, 4))

        opcoes  = [self._LABELS_TIPO[t] for t in self._TIPOS_LICENCA]
        var_sel = ctk.StringVar(value="30 dias")
        dropdown = ctk.CTkOptionMenu(
            dialog, values=opcoes, variable=var_sel,
            width=200, height=34,
            fg_color=BG3, button_color=ACCENT,
            button_hover_color=ACCENT3, text_color=TEXT,
            corner_radius=8,
        )
        dropdown.pack()

        def _confirmar():
            label = var_sel.get()
            tipo  = next(
                (k for k, v in self._LABELS_TIPO.items() if v == label),
                "30dias"
            )
            dialog.destroy()
            self._gerar_licenca(user_id, tipo)

        btns = ctk.CTkFrame(dialog, fg_color="transparent")
        btns.pack(pady=(16, 0))
        ctk.CTkButton(btns, text="Gerar",
                      command=_confirmar,
                      width=100, height=36,
                      fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Cancelar",
                      command=dialog.destroy,
                      width=90, height=36,
                      fg_color=BG3, hover_color=BG4,
                      border_color=BORDER, border_width=1,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")

    def _gerar_licenca(self, user_id: str, tipo: str):
        self._janela.set_status("Gerando licença...", WARNING)
        def _run():
            res = auth.admin_criar_licenca(user_id, tipo)
            def _done():
                if res.get("ok"):
                    self._janela.set_status(
                        "Licenca '{}' gerada!".format(self._LABELS_TIPO.get(tipo, tipo)),
                        SUCCESS)
                    self.ao_exibir()
                else:
                    self._janela.set_status(
                        "Erro: {}".format(res.get("erro", "?")), DANGER)
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _revogar(self, user_id: str):
        self._janela.set_status("Revogando licença...", WARNING)
        def _run():
            res = auth.admin_revogar_licenca(user_id)
            def _done():
                if res.get("ok"):
                    self._janela.set_status("Licença revogada.", SUCCESS)
                    self.ao_exibir()
                else:
                    self._janela.set_status(
                        "Erro: {}".format(res.get("erro", "?")), DANGER)
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()
