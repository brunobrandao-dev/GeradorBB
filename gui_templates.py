# gui_templates.py — Gerenciador e editor de templates de vídeo
#
# Layout: lista à esquerda + editor à direita (split-pane).
# Templates ficam em DATA_DIR/templates/*.json
# O template "Vídeo Único" (id="video_unico") é o padrão protegido.

from __future__ import annotations
import json
import uuid
import datetime
from pathlib import Path

import customtkinter as ctk
from gui_theme import (
    BG, BG2, BG3, BG4, BG5, ACCENT, ACCENT2, ACCENT3,
    SUCCESS, WARNING, DANGER, DANGER_HOVER, INFO,
    ACCENT_GHOST_HOVER,
    TEXT, SUBTEXT, BORDER, BORDER2,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL,
    FONT_TITLE, FONT_H2, FONT_BODY, FONT_SMALL, FONT_MONO, CORNER_R, PAD,
)

# ── Ícones disponíveis ────────────────────────────────────────────────────────
ICONES = [
    "🎬","🏆","🤔","⚔️","😈","🦸","📖","🔍","📰","🎭",
    "🌟","🔥","💥","🎯","🎪","🎨","📺","🎵","🎤","💡",
    "🕹️","🃏","🧩","🎲","📽️","🎞️","🎗️","🏅","👑","🧠",
    "📣","💬","🗣️","📢","🎙️","🖼️","🖊️","📝","📋","🗂️",
]

# ── Schema padrão ──────────────────────────────────────────────────────────────
_SCHEMA = {
    "id":         "",
    "nome":       "Novo Template",
    "icone":      "🎬",
    "descricao":  "",
    "padrao":     False,
    "abertura":   False,
    "fechamento": False,
    "tipo":       "livre",       # "livre" | "numerado" | "secoes"
    "n_itens":    10,
    "ordem":      "decrescente", # "decrescente" | "crescente"
    "secoes":     [],            # [{"label": "Origem", "obrigatorio": True}]
    "criado_em":  "",
}

TEMPLATE_VIDEO_UNICO = {
    **_SCHEMA,
    "id":        "video_unico",
    "nome":      "Vídeo Único",
    "icone":     "🎬",
    "descricao": "Um vídeo contínuo. Coloque suas cenas na pasta e pronto.",
    "padrao":    True,
    "criado_em": "2026-01-01T00:00:00",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Storage helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _templates_dir() -> Path:
    from gui_main import DATA_DIR
    d = DATA_DIR / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def inicializar_templates():
    """Cria o Vídeo Único se a pasta estiver vazia."""
    d = _templates_dir()
    if not list(d.glob("*.json")):
        salvar_template(TEMPLATE_VIDEO_UNICO)


def salvar_template(t: dict):
    d = _templates_dir()
    (d / f"{t['id']}.json").write_text(
        json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def carregar_templates() -> list[dict]:
    d = _templates_dir()
    ts = []
    for f in sorted(d.glob("*.json")):
        try:
            ts.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    ts.sort(key=lambda x: (not x.get("padrao", False), x.get("criado_em", "")))
    return ts


def deletar_template(tid: str):
    f = _templates_dir() / f"{tid}.json"
    if f.exists():
        f.unlink()


def carregar_template_por_id(tid: str) -> dict | None:
    f = _templates_dir() / f"{tid}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Preview de estrutura de arquivos (mostra ao usuário o que colocar na pasta)
# ═══════════════════════════════════════════════════════════════════════════════

def preview_estrutura(t: dict) -> str:
    lines = ["📁 cenas/"]

    if t.get("abertura"):
        lines.append("  ├─ abertura.png          ← tela de abertura")

    tipo = t.get("tipo", "livre")

    if tipo == "livre":
        lines.append("  ├─ cena_01.png")
        lines.append("  ├─ cena_02.png")
        lines.append("  └─ ...  (qualquer nome — ordem alfabética)")

    elif tipo == "numerado":
        n     = t.get("n_itens", 10)
        ordem = t.get("ordem", "decrescente")
        seq   = list(range(n, 0, -1)) if ordem == "decrescente" else list(range(1, n + 1))
        for i, num in enumerate(seq):
            prefix = "├─" if (i < len(seq) - 1 or t.get("fechamento")) else "└─"
            lines.append(f"  {prefix} {num}.png")
        if n > 5:
            lines = lines[:4] + [f"  │  ..."] + lines[-2:]

    elif tipo == "secoes":
        secoes = t.get("secoes", [])
        for i, s in enumerate(secoes):
            nome_arq = s["label"].lower().replace(" ", "_")
            obs      = "" if s.get("obrigatorio", True) else "  ← opcional"
            prefix   = "├─" if (i < len(secoes) - 1 or t.get("fechamento")) else "└─"
            lines.append(f"  {prefix} {nome_arq}.png{obs}")
        if not secoes:
            lines.append("  └─ (defina as seções abaixo)")

    if t.get("fechamento"):
        lines.append("  └─ fechamento.png        ← tela de encerramento")

    lines += [
        "",
        "📁 roteiro/",
    ]

    if tipo == "numerado":
        n     = t.get("n_itens", 10)
        ordem = t.get("ordem", "decrescente")
        seq   = list(range(n, 0, -1)) if ordem == "decrescente" else list(range(1, n + 1))
        lines.append("  ├─ roteiro_pt.txt  ← use marcadores:")
        lines.append(f"  │     {seq[0]} – Título do item {seq[0]}")
        lines.append(f"  │     Texto sobre o item...")
        if len(seq) > 1:
            lines.append(f"  │     {seq[1]} – Título do item {seq[1]}")
            lines.append(f"  │     Texto sobre o item...")
        lines.append("  └─ roteiro_en.txt  ← mesmo formato em inglês")

    elif tipo == "secoes":
        secoes = t.get("secoes", [])
        lines.append("  ├─ roteiro_pt.txt  ← use marcadores:")
        for s in secoes[:3]:
            lines.append(f"  │     [{s['label']}]")
            lines.append(f"  │     Texto desta seção...")
        if len(secoes) > 3:
            lines.append(f"  │     ...")
        lines.append("  └─ roteiro_en.txt  ← mesmo formato em inglês")

    else:  # livre
        lines.append("  ├─ roteiro_pt.txt  ← narração contínua")
        lines.append("  └─ roteiro_en.txt  ← narração em inglês")

    lines += [
        "",
        "📁 audio/",
        "  ├─ audio_pt.mp3",
        "  └─ audio_en.mp3",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Widgets auxiliares
# ═══════════════════════════════════════════════════════════════════════════════

def _lbl(master, text, size=FONT_SIZE_MD, bold=False, color=TEXT, **kw):
    w = "bold" if bold else "normal"
    return ctk.CTkLabel(master, text=text, font=(FONT_FAMILY, size, w),
                        text_color=color, **kw)


def _sep(master):
    return ctk.CTkFrame(master, height=1, fg_color=BORDER)


def _card(master, **kw):
    return ctk.CTkFrame(master,
                        fg_color=BG3, corner_radius=CORNER_R,
                        border_width=1, border_color=BORDER, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
# Tela principal de templates (split-pane)
# ═══════════════════════════════════════════════════════════════════════════════

class TelaTemplates(ctk.CTkFrame):
    """Tela de gerenciamento de templates. Left=lista, Right=editor."""

    def __init__(self, master, janela):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._janela      = janela
        self._templates: list[dict] = []
        self._selecionado: dict | None = None
        self._editor: _EditorTemplate | None = None

        self._build()

    # ── Construção ──────────────────────────────────────────────────────────

    def _build(self):
        # Título
        header = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        _lbl(header, "📋  Templates de Vídeo", size=FONT_SIZE_LG, bold=True).pack(
            side="left", padx=PAD, pady=14)
        _lbl(header,
             "Crie e edite modelos reutilizáveis para qualquer tipo de vídeo",
             size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left", padx=(0, PAD))

        _sep(self).pack(fill="x")

        # Corpo split-pane
        corpo = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        corpo.pack(fill="both", expand=True)

        # ── Lista (esquerda 280px) ──
        self._painel_lista = ctk.CTkFrame(corpo, fg_color=BG2, corner_radius=0, width=280)
        self._painel_lista.pack(side="left", fill="y")
        self._painel_lista.pack_propagate(False)
        self._build_lista()

        ctk.CTkFrame(corpo, width=1, fg_color=BORDER).pack(side="left", fill="y")

        # ── Editor (direita) ──
        self._painel_editor = ctk.CTkFrame(corpo, fg_color=BG, corner_radius=0)
        self._painel_editor.pack(side="left", fill="both", expand=True)
        self._mostrar_vazio()

    def _build_lista(self):
        pl = self._painel_lista

        # Cabeçalho da lista
        top = ctk.CTkFrame(pl, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 8))
        _lbl(top, "MEUS TEMPLATES", size=9, bold=True, color=SUBTEXT).pack(side="left")
        ctk.CTkButton(
            top, text="+ Novo",
            command=self._novo_template,
            height=28, width=70,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="right")

        _sep(pl).pack(fill="x", padx=8)

        # Importar / Exportar
        io_row = ctk.CTkFrame(pl, fg_color="transparent")
        io_row.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkButton(
            io_row, text="📥 Importar",
            command=self._importar_template,
            height=26, width=108,
            fg_color=BG3, hover_color=BG4,
            border_color=INFO, border_width=1,
            text_color=INFO, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            io_row, text="📤 Exportar",
            command=self._exportar_template,
            height=26, width=108,
            fg_color=BG3, hover_color=BG4,
            border_color=BORDER, border_width=1,
            text_color=SUBTEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left")

        _sep(pl).pack(fill="x", padx=8, pady=(6, 0))

        # Scroll da lista
        self._scroll_lista = ctk.CTkScrollableFrame(
            pl, fg_color="transparent", corner_radius=0)
        self._scroll_lista.pack(fill="both", expand=True, padx=4, pady=4)

    def _renderizar_lista(self):
        # Limpa lista existente
        for w in self._scroll_lista.winfo_children():
            w.destroy()

        for t in self._templates:
            self._criar_card_lista(t)

        # Placeholder se vazio
        if not self._templates:
            _lbl(self._scroll_lista,
                 "Nenhum template.\nClique em + Novo.",
                 size=FONT_SIZE_SM, color=SUBTEXT, justify="center").pack(pady=40)

    def _criar_card_lista(self, t: dict):
        selecionado = self._selecionado and self._selecionado["id"] == t["id"]
        cor_borda   = ACCENT if selecionado else BORDER
        cor_fundo   = BG3    if selecionado else "transparent"

        frame = ctk.CTkFrame(
            self._scroll_lista,
            fg_color=cor_fundo, corner_radius=8,
            border_width=1, border_color=cor_borda,
            cursor="hand2",
        )
        frame.pack(fill="x", pady=3, padx=2)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)

        # Ícone + nome
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        _lbl(row, t.get("icone", "🎬"), size=20).pack(side="left")
        _lbl(row, t.get("nome", "Template"), size=FONT_SIZE_MD,
             bold=True, anchor="w").pack(side="left", padx=(6, 0), fill="x", expand=True)
        if t.get("padrao"):
            _lbl(row, "padrão", size=9, color=INFO).pack(side="right")

        # Tipo badge
        tipo_labels = {"livre": "Livre", "numerado": "Numerado", "secoes": "Seções"}
        tipo_cores  = {"livre": SUBTEXT, "numerado": SUCCESS, "secoes": INFO}
        tipo        = t.get("tipo", "livre")
        _lbl(inner, tipo_labels.get(tipo, tipo),
             size=FONT_SIZE_SM, color=tipo_cores.get(tipo, SUBTEXT)).pack(anchor="w")

        # Descrição curta
        desc = t.get("descricao", "")
        if desc:
            _lbl(inner, desc[:60] + ("…" if len(desc) > 60 else ""),
                 size=FONT_SIZE_SM, color=SUBTEXT, anchor="w",
                 wraplength=230, justify="left").pack(anchor="w", pady=(2, 0))

        # Clique
        for widget in (frame, inner, row):
            widget.bind("<Button-1>", lambda e, _t=t: self._selecionar(copy_dict(_t)))

    # ── Ações ────────────────────────────────────────────────────────────────

    def _selecionar(self, t: dict):
        self._selecionado = t
        self._renderizar_lista()
        self._abrir_editor(t)

    def _novo_template(self):
        novo = {
            **_SCHEMA,
            "id":        str(uuid.uuid4()),
            "nome":      "Novo Template",
            "icone":     "🎬",
            "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        self._selecionar(novo)

    def _abrir_editor(self, t: dict):
        # Limpa painel direito
        for w in self._painel_editor.winfo_children():
            w.destroy()
        self._editor = _EditorTemplate(
            self._painel_editor, t,
            on_salvar=self._ao_salvar,
            on_deletar=self._ao_deletar,
        )
        self._editor.pack(fill="both", expand=True)

    def _mostrar_vazio(self):
        for w in self._painel_editor.winfo_children():
            w.destroy()
        frame = ctk.CTkFrame(self._painel_editor, fg_color="transparent")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        _lbl(frame, "📋", size=48).pack()
        _lbl(frame, "Selecione um template\nou crie um novo",
             size=FONT_SIZE_LG, color=SUBTEXT, justify="center").pack(pady=8)
        ctk.CTkButton(
            frame, text="+ Criar Primeiro Template",
            command=self._novo_template,
            height=42, width=220,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(pady=(12, 0))

    def _ao_salvar(self, t: dict):
        salvar_template(t)
        self._selecionado = t
        self.ao_exibir()

    def _ao_deletar(self, tid: str):
        deletar_template(tid)
        self._selecionado = None
        self.ao_exibir()
        self._mostrar_vazio()

    def _importar_template(self):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        caminho = fd.askopenfilename(
            title="Importar Template",
            filetypes=[("Template JSON", "*.json"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        try:
            dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        except Exception as e:
            mb.showerror("Erro ao importar", f"Arquivo inválido:\n{e}")
            return

        # Valida campos mínimos
        if not isinstance(dados, dict) or "nome" not in dados:
            mb.showerror("Erro ao importar",
                         "O arquivo não parece ser um template GeradorBB.")
            return

        # Gera novo ID para evitar colisão
        dados["id"] = str(uuid.uuid4())
        dados.setdefault("icone", "🎬")
        dados.setdefault("tipo", "livre")
        dados.pop("padrao", None)  # importado nunca é padrão

        salvar_template(dados)
        self._selecionado = dados
        self.ao_exibir()
        self._selecionar(copy_dict(dados))

    def _exportar_template(self):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        if not self._selecionado:
            mb.showinfo("Exportar Template",
                        "Selecione um template na lista antes de exportar.")
            return
        t   = self._selecionado
        sug = f"{t.get('nome', 'template').replace(' ', '_')}.json"
        caminho = fd.asksaveasfilename(
            title="Exportar Template",
            defaultextension=".json",
            initialfile=sug,
            filetypes=[("Template JSON", "*.json"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        try:
            Path(caminho).write_text(
                json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            mb.showinfo("Exportar Template",
                        f"Template exportado com sucesso:\n{caminho}")
        except Exception as e:
            mb.showerror("Erro ao exportar", str(e))

    def ao_exibir(self):
        self._templates = carregar_templates()
        self._renderizar_lista()

        if not self._templates:
            self._selecionado = None
            self._mostrar_vazio()
            return

        # Se nenhum selecionado ainda, abre o primeiro automaticamente
        if not self._selecionado:
            self._selecionar(copy_dict(self._templates[0]))
        else:
            # Verifica se o selecionado ainda existe; se não, abre o primeiro
            tid = self._selecionado.get("id")
            if not any(t["id"] == tid for t in self._templates):
                self._selecionar(copy_dict(self._templates[0]))


# ═══════════════════════════════════════════════════════════════════════════════
# Editor de template (painel direito)
# ═══════════════════════════════════════════════════════════════════════════════

class _EditorTemplate(ctk.CTkFrame):
    """Formulário completo de edição de um template."""

    def __init__(self, master, template: dict, on_salvar, on_deletar):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._t          = copy_dict(template)
        self._on_salvar  = on_salvar
        self._on_deletar = on_deletar
        self._icone_var  = ctk.StringVar(value=self._t.get("icone", "🎬"))
        self._tipo_var   = ctk.StringVar(value=self._t.get("tipo", "livre"))
        self._build()

    # ── Construção ──────────────────────────────────────────────────────────

    def _build(self):
        # Atalho Ctrl+S para salvar
        self.winfo_toplevel().bind("<Control-s>", lambda e: self._salvar())

        # Scroll externo
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self._scroll.pack(fill="both", expand=True)
        sc = self._scroll

        is_padrao = self._t.get("padrao", False)

        # ─── Título do editor ───────────────────────────────────────────────
        hdr = ctk.CTkFrame(sc, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD, pady=(16, 0))
        titulo = "✏️  Editar Template" if self._t.get("criado_em") else "✨  Novo Template"
        _lbl(hdr, titulo, size=FONT_SIZE_LG, bold=True).pack(side="left")
        if is_padrao:
            _lbl(hdr, " — template padrão (não pode ser excluído)",
                 size=FONT_SIZE_SM, color=INFO).pack(side="left")

        _sep(sc).pack(fill="x", padx=PAD, pady=(12, 0))

        # ─── Identidade ─────────────────────────────────────────────────────
        self._secao(sc, "Identidade")

        id_row = ctk.CTkFrame(sc, fg_color="transparent")
        id_row.pack(fill="x", padx=PAD, pady=(0, 10))
        id_row.columnconfigure(0, weight=0)
        id_row.columnconfigure(1, weight=1)

        # Ícone (coluna 0)
        ic_col = ctk.CTkFrame(id_row, fg_color="transparent")
        ic_col.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 16))
        _lbl(ic_col, "Ícone", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        self._ic_btn = ctk.CTkButton(
            ic_col, textvariable=self._icone_var,
            command=self._picker_icone,
            width=60, height=60, corner_radius=12,
            fg_color=BG3, hover_color=BG5,
            text_color=TEXT,
            font=(FONT_FAMILY, 28),
        )
        self._ic_btn.pack(pady=(4, 0))

        # Nome (coluna 1)
        nome_col = ctk.CTkFrame(id_row, fg_color="transparent")
        nome_col.grid(row=0, column=1, sticky="ew")
        _lbl(nome_col, "Nome do Template", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        self._nome_entry = ctk.CTkEntry(
            nome_col, placeholder_text="Ex: TOP 10, Vilão da Semana...",
            height=38, corner_radius=8,
            fg_color=BG3, border_color=BORDER, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        self._nome_entry.insert(0, self._t.get("nome", ""))
        self._nome_entry.pack(fill="x", pady=(4, 0))

        # Descrição (coluna 1, linha 1)
        desc_col = ctk.CTkFrame(id_row, fg_color="transparent")
        desc_col.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        _lbl(desc_col, "Descrição curta", size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w")
        self._desc_entry = ctk.CTkEntry(
            desc_col, placeholder_text="Breve descrição do que este template produz...",
            height=36, corner_radius=8,
            fg_color=BG3, border_color=BORDER, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        self._desc_entry.insert(0, self._t.get("descricao", ""))
        self._desc_entry.pack(fill="x", pady=(4, 0))

        # ─── Abertura / Fechamento ──────────────────────────────────────────
        _sep(sc).pack(fill="x", padx=PAD, pady=(8, 0))
        self._secao(sc, "Telas de Abertura e Fechamento  —  opcionais em todos os modelos")

        ab_row = ctk.CTkFrame(sc, fg_color="transparent")
        ab_row.pack(fill="x", padx=PAD, pady=(0, 10))

        self._ab_var = ctk.BooleanVar(value=self._t.get("abertura", False))
        self._fc_var = ctk.BooleanVar(value=self._t.get("fechamento", False))

        for var, label, desc in (
            (self._ab_var, "Abertura",   "Imagem/vídeo antes do conteúdo principal  →  abertura.png"),
            (self._fc_var, "Fechamento", "Imagem/vídeo após o conteúdo principal    →  fechamento.png"),
        ):
            box = _card(ab_row)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            inner = ctk.CTkFrame(box, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            sw = ctk.CTkSwitch(
                inner, text=label, variable=var,
                font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=TEXT,
                fg_color=BG4, progress_color=ACCENT,
                command=self._atualizar_preview,
            )
            sw.pack(anchor="w")
            _lbl(inner, desc, size=FONT_SIZE_SM, color=SUBTEXT, anchor="w").pack(
                anchor="w", pady=(2, 0))

        # ─── Tipo de conteúdo ───────────────────────────────────────────────
        _sep(sc).pack(fill="x", padx=PAD, pady=(8, 0))
        self._secao(sc, "Tipo de Conteúdo")

        tipos = [
            ("livre",    "🗂️  Livre",    "Cenas em qualquer ordem. O app usa os arquivos\nque estiverem na pasta, em ordem alfabética."),
            ("numerado", "🔢  Numerado", "N cenas numeradas: 1.png, 2.png, …\nIdeal para rankings como Top 10."),
            ("secoes",   "📑  Seções",   "Cenas com nomes específicos: origem.png, poderes.png…\nIdeal para perfis, reviews e formatos fixos."),
        ]

        self._tipo_frames: dict[str, ctk.CTkFrame] = {}
        for val, label, desc in tipos:
            row = _card(sc)
            row.pack(fill="x", padx=PAD, pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)
            top_row = ctk.CTkFrame(inner, fg_color="transparent")
            top_row.pack(fill="x")
            ctk.CTkRadioButton(
                top_row, text=label, variable=self._tipo_var, value=val,
                command=self._ao_trocar_tipo,
                font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=TEXT,
                fg_color=ACCENT, hover_color=ACCENT3,
            ).pack(side="left")
            _lbl(inner, desc, size=FONT_SIZE_SM, color=SUBTEXT,
                 justify="left", anchor="w", wraplength=480).pack(anchor="w", pady=(4, 0))
            self._tipo_frames[val] = inner

        # ─── Área dinâmica por tipo ─────────────────────────────────────────
        self._area_dinamica = ctk.CTkFrame(sc, fg_color="transparent")
        self._area_dinamica.pack(fill="x", padx=PAD, pady=(8, 0))
        self._construir_area_dinamica()

        # ─── Preview de estrutura ───────────────────────────────────────────
        _sep(sc).pack(fill="x", padx=PAD, pady=(8, 0))
        self._secao(sc, "Estrutura de Arquivos Esperada")
        _lbl(sc, "Estes são os arquivos que você precisa colocar no projeto para este template.",
             size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w", padx=PAD)

        preview_card = ctk.CTkFrame(sc, fg_color=BG4, corner_radius=CORNER_R,
                                    border_width=1, border_color=BORDER)
        preview_card.pack(fill="x", padx=PAD, pady=(6, 0))

        self._preview_txt = ctk.CTkTextbox(
            preview_card, height=220,
            fg_color="transparent", text_color=INFO,
            font=FONT_MONO, state="disabled",
            corner_radius=0,
        )
        self._preview_txt.pack(fill="x", padx=4, pady=4)
        self._atualizar_preview()

        # ─── Botões ─────────────────────────────────────────────────────────
        _sep(sc).pack(fill="x", padx=PAD, pady=(16, 0))

        btns = ctk.CTkFrame(sc, fg_color="transparent")
        btns.pack(fill="x", padx=PAD, pady=(10, 4))

        _lbl(sc, "Ctrl+S para salvar rapidamente",
             size=9, color=SUBTEXT).pack(anchor="e", padx=PAD, pady=(0, 16))

        self._btn_salvar = ctk.CTkButton(
            btns, text="💾  Salvar Template",
            command=self._salvar,
            height=44, width=200,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        self._btn_salvar.pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btns, text="📋  Duplicar",
            command=self._duplicar,
            height=44, width=140,
            fg_color="transparent", hover_color=BG3,
            text_color=INFO, border_color=INFO, border_width=1,
            corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="right")

        if not is_padrao:
            ctk.CTkButton(
                btns, text="🗑  Excluir",
                command=self._confirmar_delete,
                height=44, width=110,
                fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
                text_color=DANGER, border_color=DANGER, border_width=1,
                corner_radius=CORNER_R,
                font=(FONT_FAMILY, FONT_SIZE_SM),
            ).pack(side="left")

    # ── Área dinâmica ────────────────────────────────────────────────────────

    def _construir_area_dinamica(self):
        for w in self._area_dinamica.winfo_children():
            w.destroy()

        tipo = self._tipo_var.get()

        if tipo == "numerado":
            self._build_area_numerado()
        elif tipo == "secoes":
            self._build_area_secoes()
        # livre: sem configuração adicional

    def _build_area_numerado(self):
        ad = self._area_dinamica
        box = _card(ad)
        box.pack(fill="x", pady=(0, 4))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        # Quantidade de itens
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))
        _lbl(row1, "Quantidade de itens:", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")
        self._n_var = ctk.IntVar(value=self._t.get("n_itens", 10))
        n_entry = ctk.CTkEntry(
            row1, textvariable=self._n_var,
            width=70, height=32, corner_radius=8,
            fg_color=BG3, border_color=BORDER, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            justify="center",
        )
        n_entry.pack(side="left", padx=(10, 0))
        n_entry.bind("<KeyRelease>", lambda e: self._atualizar_preview())
        _lbl(row1, "  (mínimo 2, máximo 50)", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")

        # Ordem de contagem
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x")
        _lbl(row2, "Contagem:", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")
        self._ordem_var = ctk.StringVar(value=self._t.get("ordem", "decrescente"))
        ctk.CTkOptionMenu(
            row2,
            variable=self._ordem_var,
            values=["decrescente", "crescente"],
            command=lambda v: self._atualizar_preview(),
            width=180, height=32, corner_radius=8,
            fg_color=BG3, button_color=ACCENT, button_hover_color=ACCENT3,
            text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="left", padx=(10, 0))
        _lbl(row2,
             "  decrescente = 10→1  /  crescente = 1→10",
             size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")

    def _build_area_secoes(self):
        ad = self._area_dinamica

        # Header das seções
        hdr = ctk.CTkFrame(ad, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        _lbl(hdr, "Seções do template", size=FONT_SIZE_MD, bold=True).pack(side="left")
        _lbl(hdr, " — defina cada cena pelo nome", size=FONT_SIZE_SM, color=SUBTEXT).pack(side="left")
        ctk.CTkButton(
            hdr, text="+ Adicionar Seção",
            command=self._adicionar_secao,
            height=30, width=140,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="right")

        # Container das seções
        self._secoes_container = ctk.CTkFrame(ad, fg_color="transparent")
        self._secoes_container.pack(fill="x")

        # Garante que a lista existe
        if "secoes" not in self._t:
            self._t["secoes"] = []

        self._renderizar_secoes()

        # Dica de nomenclatura
        dica = ctk.CTkFrame(ad, fg_color=BG4, corner_radius=8)
        dica.pack(fill="x", pady=(10, 0))
        _lbl(dica,
             "💡  O nome da seção vira o nome do arquivo. Ex: 'Origem' → origem.png",
             size=FONT_SIZE_SM, color=SUBTEXT).pack(anchor="w", padx=12, pady=8)

    def _renderizar_secoes(self):
        for w in self._secoes_container.winfo_children():
            w.destroy()

        secoes = self._t.get("secoes", [])
        if not secoes:
            _lbl(self._secoes_container,
                 "Nenhuma seção. Clique em + Adicionar Seção.",
                 size=FONT_SIZE_SM, color=SUBTEXT).pack(pady=10)
            return

        for i, s in enumerate(secoes):
            self._criar_linha_secao(i, s, len(secoes))

    def _criar_linha_secao(self, idx: int, secao: dict, total: int):
        row = _card(self._secoes_container)
        row.pack(fill="x", pady=2)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)

        # Número
        _lbl(inner, f"{idx+1:02d}", size=FONT_SIZE_SM, color=SUBTEXT, width=24).pack(side="left")

        # Entry com o nome
        entry = ctk.CTkEntry(
            inner,
            placeholder_text="Nome da seção (ex: Origem, Poderes...)",
            height=32, corner_radius=6,
            fg_color=BG4, border_color=BORDER, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        entry.insert(0, secao.get("label", ""))
        entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entry.bind("<KeyRelease>", lambda e, i=idx, w=entry: self._on_secao_edit(i, w.get()))

        # Toggle obrigatório
        ob_var = ctk.BooleanVar(value=secao.get("obrigatorio", True))
        ctk.CTkCheckBox(
            inner, text="obrigatória", variable=ob_var,
            font=(FONT_FAMILY, FONT_SIZE_SM), text_color=SUBTEXT,
            fg_color=ACCENT, hover_color=ACCENT3, width=18, height=18,
            command=lambda i=idx, v=ob_var: self._on_secao_ob(i, v.get()),
        ).pack(side="left", padx=(10, 0))

        # Botões de ordem
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(side="left", padx=(8, 0))
        for symbol, delta in (("▲", -1), ("▼", +1)):
            ctk.CTkButton(
                btn_row, text=symbol,
                command=lambda i=idx, d=delta: self._mover_secao(i, d),
                width=26, height=26, corner_radius=4,
                fg_color=BG3, hover_color=BG5,
                text_color=SUBTEXT, font=(FONT_FAMILY, 10),
            ).pack(side="left", padx=1)

        # Excluir
        ctk.CTkButton(
            inner, text="✕",
            command=lambda i=idx: self._remover_secao(i),
            width=26, height=26, corner_radius=4,
            fg_color="transparent", hover_color=ACCENT_GHOST_HOVER,
            text_color=DANGER, font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        ).pack(side="left", padx=(4, 0))

    # ── Eventos de seções ────────────────────────────────────────────────────

    def _adicionar_secao(self):
        if "secoes" not in self._t:
            self._t["secoes"] = []
        self._t["secoes"].append({"label": "Nova Seção", "obrigatorio": True})
        self._renderizar_secoes()
        self._atualizar_preview()

    def _remover_secao(self, idx: int):
        self._t["secoes"].pop(idx)
        self._renderizar_secoes()
        self._atualizar_preview()

    def _mover_secao(self, idx: int, delta: int):
        s = self._t["secoes"]
        novo = idx + delta
        if 0 <= novo < len(s):
            s[idx], s[novo] = s[novo], s[idx]
        self._renderizar_secoes()
        self._atualizar_preview()

    def _on_secao_edit(self, idx: int, valor: str):
        if idx < len(self._t.get("secoes", [])):
            self._t["secoes"][idx]["label"] = valor
        self._atualizar_preview()

    def _on_secao_ob(self, idx: int, val: bool):
        if idx < len(self._t.get("secoes", [])):
            self._t["secoes"][idx]["obrigatorio"] = val
        self._atualizar_preview()

    # ── Picker de ícone (popup) ──────────────────────────────────────────────

    def _picker_icone(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Escolher Ícone")
        pop.geometry("420x320")
        pop.resizable(False, False)
        pop.grab_set()
        pop.configure(fg_color=BG2)

        _lbl(pop, "Escolha um ícone para o template",
             size=FONT_SIZE_MD, bold=True).pack(pady=(14, 8), padx=PAD)

        grid = ctk.CTkScrollableFrame(pop, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))

        cols = 8
        for i, ic in enumerate(ICONES):
            def _escolher(ic=ic):
                self._icone_var.set(ic)
                self._t["icone"] = ic
                pop.destroy()

            ctk.CTkButton(
                grid, text=ic,
                command=_escolher,
                width=42, height=42, corner_radius=8,
                fg_color=BG3, hover_color=ACCENT3,
                text_color=TEXT, font=(FONT_FAMILY, 20),
            ).grid(row=i // cols, column=i % cols, padx=3, pady=3)

    # ── Tipo de conteúdo ─────────────────────────────────────────────────────

    def _ao_trocar_tipo(self):
        self._t["tipo"] = self._tipo_var.get()
        self._construir_area_dinamica()
        self._atualizar_preview()

    # ── Preview ──────────────────────────────────────────────────────────────

    def _atualizar_preview(self):
        # Coleta estado atual para preview
        snap = self._snapshot()
        texto = preview_estrutura(snap)
        self._preview_txt.configure(state="normal")
        self._preview_txt.delete("1.0", "end")
        self._preview_txt.insert("1.0", texto)
        self._preview_txt.configure(state="disabled")

    def _snapshot(self) -> dict:
        """Monta dict com o estado atual do formulário para preview."""
        snap = copy_dict(self._t)
        snap["abertura"]  = self._ab_var.get()
        snap["fechamento"] = self._fc_var.get()
        snap["tipo"]      = self._tipo_var.get()
        if snap["tipo"] == "numerado":
            try:
                snap["n_itens"] = max(2, min(50, int(self._n_var.get())))
            except Exception:
                snap["n_itens"] = 10
            snap["ordem"] = self._ordem_var.get() if hasattr(self, "_ordem_var") else "decrescente"
        return snap

    # ── Salvar / Duplicar / Delete ───────────────────────────────────────────

    def _coletar(self) -> dict | None:
        nome = self._nome_entry.get().strip()
        if not nome:
            _popup_aviso(self, "O nome do template não pode ficar vazio.")
            return None
        snap = self._snapshot()
        snap["nome"]      = nome
        snap["descricao"] = self._desc_entry.get().strip()
        snap["icone"]     = self._icone_var.get()
        if snap["tipo"] == "numerado":
            try:
                snap["n_itens"] = max(2, min(50, int(self._n_var.get())))
            except Exception:
                snap["n_itens"] = 10
        if not snap.get("id"):
            snap["id"] = str(uuid.uuid4())
        if not snap.get("criado_em"):
            snap["criado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
        return snap

    def _salvar(self):
        t = self._coletar()
        if t:
            self._t = t
            self._on_salvar(t)
            # Feedback visual rápido no botão
            try:
                self._btn_salvar.configure(text="✅  Salvo!", fg_color=SUCCESS)
                self.after(1500, lambda: self._btn_salvar.configure(
                    text="💾  Salvar Template", fg_color=ACCENT))
            except Exception:
                pass

    def _duplicar(self):
        t = self._coletar()
        if not t:
            return
        novo = copy_dict(t)
        novo["id"]        = str(uuid.uuid4())
        novo["padrao"]    = False
        novo["nome"]      = t["nome"] + " (cópia)"
        novo["criado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
        self._on_salvar(novo)

    def _confirmar_delete(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Confirmar")
        pop.geometry("340x160")
        pop.resizable(False, False)
        pop.grab_set()
        pop.configure(fg_color=BG2)

        _lbl(pop, f"Excluir \"{self._t.get('nome')}\"?",
             size=FONT_SIZE_MD, bold=True).pack(pady=(20, 6), padx=PAD)
        _lbl(pop, "Esta ação não pode ser desfeita.",
             size=FONT_SIZE_SM, color=SUBTEXT).pack()

        row = ctk.CTkFrame(pop, fg_color="transparent")
        row.pack(pady=16)
        ctk.CTkButton(row, text="Cancelar", command=pop.destroy,
                      width=110, height=36, fg_color=BG3, hover_color=BG5,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left", padx=8)
        ctk.CTkButton(row, text="Excluir", width=110, height=36,
                      fg_color=DANGER, hover_color=DANGER_HOVER,
                      text_color=TEXT, corner_radius=8,
                      font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                      command=lambda: (pop.destroy(),
                                       self._on_deletar(self._t["id"]))).pack(side="left")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _secao(self, master, titulo: str):
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", padx=PAD, pady=(14, 6))
        ctk.CTkFrame(row, width=4, height=18, corner_radius=2, fg_color=ACCENT).pack(
            side="left", padx=(0, 8))
        _lbl(row, titulo, size=FONT_SIZE_MD, bold=True).pack(side="left")


# ═══════════════════════════════════════════════════════════════════════════════
# Popup de seleção de template (usado na tela de Gerar Vídeo)
# ═══════════════════════════════════════════════════════════════════════════════

class SeletorTemplate(ctk.CTkFrame):
    """Widget compacto para selecionar o template ativo dentro da tela de Gerar."""

    def __init__(self, master, on_change=None, **kw):
        super().__init__(master, fg_color=BG3, corner_radius=CORNER_R,
                         border_width=1, border_color=BORDER, **kw)
        self._on_change = on_change
        self._templates: list[dict] = []
        self._ativo_id  = ""
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        _lbl(inner, "📋  Template:", size=FONT_SIZE_SM, bold=True, color=SUBTEXT).pack(
            side="left")

        self._icone_lbl = _lbl(inner, "🎬", size=18)
        self._icone_lbl.pack(side="left", padx=(10, 0))

        self._nome_lbl = _lbl(inner, "Carregando...", size=FONT_SIZE_MD, bold=True)
        self._nome_lbl.pack(side="left", padx=(6, 0))

        self._tipo_lbl = _lbl(inner, "", size=FONT_SIZE_SM, color=SUBTEXT)
        self._tipo_lbl.pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            inner, text="Trocar",
            command=self._abrir_picker,
            height=28, width=70,
            fg_color="transparent", hover_color=BG5,
            text_color=INFO, border_color=INFO, border_width=1,
            corner_radius=6, font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="right")

    def atualizar(self, template_id: str = ""):
        self._templates = carregar_templates()
        if not self._templates:
            inicializar_templates()
            self._templates = carregar_templates()

        # Tenta usar o id fornecido; senão usa o padrão; senão o primeiro
        t = None
        if template_id:
            t = next((x for x in self._templates if x["id"] == template_id), None)
        if not t:
            t = next((x for x in self._templates if x.get("padrao")), None)
        if not t and self._templates:
            t = self._templates[0]

        if t:
            self._ativo_id = t["id"]
            self._icone_lbl.configure(text=t.get("icone", "🎬"))
            self._nome_lbl.configure(text=t.get("nome", ""))
            tipo_map = {"livre": "Livre", "numerado": "Numerado", "secoes": "Seções"}
            self._tipo_lbl.configure(text=tipo_map.get(t.get("tipo", "livre"), ""))

    def template_ativo(self) -> dict | None:
        return next((x for x in self._templates if x["id"] == self._ativo_id), None)

    def _abrir_picker(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Escolher Template")
        pop.geometry("480x420")
        pop.resizable(False, False)
        pop.grab_set()
        pop.configure(fg_color=BG2)

        _lbl(pop, "Escolha o template para este projeto",
             size=FONT_SIZE_MD, bold=True).pack(pady=(16, 10), padx=PAD)

        scroll = ctk.CTkScrollableFrame(pop, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=PAD)

        for t in self._templates:
            def _escolher(t=t):
                self._ativo_id = t["id"]
                self._icone_lbl.configure(text=t.get("icone", "🎬"))
                self._nome_lbl.configure(text=t.get("nome", ""))
                tipo_map = {"livre": "Livre", "numerado": "Numerado", "secoes": "Seções"}
                self._tipo_lbl.configure(text=tipo_map.get(t.get("tipo", "livre"), ""))
                pop.destroy()
                if self._on_change:
                    self._on_change(t)

            row = _card(scroll)
            row.pack(fill="x", pady=4)
            row.configure(cursor="hand2")
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)

            top = ctk.CTkFrame(inner, fg_color="transparent")
            top.pack(fill="x")
            _lbl(top, t.get("icone", "🎬"), size=22).pack(side="left")
            _lbl(top, t.get("nome", ""), size=FONT_SIZE_MD, bold=True).pack(
                side="left", padx=(8, 0))
            selecionado = t["id"] == self._ativo_id
            if selecionado:
                _lbl(top, "  ✓ ativo", size=FONT_SIZE_SM, color=SUCCESS).pack(side="right")

            desc = t.get("descricao", "")
            if desc:
                _lbl(inner, desc, size=FONT_SIZE_SM, color=SUBTEXT,
                     anchor="w", wraplength=400).pack(anchor="w", pady=(3, 0))

            row.bind("<Button-1>", lambda e, _t=t: _escolher(_t))
            inner.bind("<Button-1>", lambda e, _t=t: _escolher(_t))
            top.bind("<Button-1>", lambda e, _t=t: _escolher(_t))

        ctk.CTkButton(
            pop, text="Fechar",
            command=pop.destroy,
            height=36, width=100,
            fg_color=BG3, hover_color=BG5,
            text_color=SUBTEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(pady=12)


# ═══════════════════════════════════════════════════════════════════════════════
# Utils
# ═══════════════════════════════════════════════════════════════════════════════

def copy_dict(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


def _popup_aviso(parent, msg: str):
    pop = ctk.CTkToplevel(parent)
    pop.title("Atenção")
    pop.geometry("320x130")
    pop.resizable(False, False)
    pop.grab_set()
    pop.configure(fg_color=BG2)
    _lbl(pop, msg, size=FONT_SIZE_SM, color=WARNING, wraplength=280,
         justify="center").pack(pady=(24, 12), padx=PAD)
    ctk.CTkButton(pop, text="OK", command=pop.destroy,
                  height=32, width=80, fg_color=ACCENT, hover_color=ACCENT3,
                  text_color=TEXT, corner_radius=8,
                  font=(FONT_FAMILY, FONT_SIZE_SM)).pack()


def construir_templates(master, janela):
    """Entry-point para gui_main.py instanciar a tela."""
    return TelaTemplates(master, janela)
