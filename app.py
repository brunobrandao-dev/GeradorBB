#!/usr/bin/env python3
# app.py — Ponto de entrada do GeradorBB
#
# Uma única janela CTk que troca de conteúdo: login → principal.

import sys
from pathlib import Path

# ── Verifica CustomTkinter ────────────────────────────────────────────────────
try:
    import customtkinter as ctk
except ImportError:
    try:
        import tkinter as tk
        import tkinter.messagebox as mb
        r = tk.Tk(); r.withdraw()
        mb.showerror(
            "GeradorBB — Dependência faltando",
            "O pacote 'customtkinter' não está instalado.\n\n"
            "Abra o terminal e rode:\n\n    pip install customtkinter",
        )
        r.destroy()
    except Exception:
        pass
    sys.exit(1)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

import auth
from gui_theme import BG


class App(ctk.CTk):
    """
    Janela única que gerencia todo o ciclo de vida:
      login → validar licença → janela principal
    """

    def __init__(self):
        super().__init__()
        self.title("GeradorBB — Acesso")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self._centrar(440, 700)
        self.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
        self.after(60, self._iniciar)

    def _centrar(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)

    # ------------------------------------------------------------------

    def _limpar(self):
        for w in self.winfo_children():
            w.destroy()

    def _iniciar(self):
        sessao = auth.carregar_sessao()
        if sessao is None:
            self._mostrar_login()
        else:
            self._validar_e_abrir(sessao)

    # ── Login ──────────────────────────────────────────────────────────

    def _mostrar_login(self):
        self._limpar()
        self.title("GeradorBB — Acesso")
        self._centrar(440, 700)

        from gui_login import construir_login
        construir_login(self, on_sucesso=self._apos_login)

    def _apos_login(self, user: dict):
        self._validar_e_abrir(user)

    # ── Validação ──────────────────────────────────────────────────────

    def _validar_e_abrir(self, user: dict):
        licenca = auth.verificar_licenca(user.get("user_id", ""))
        if not licenca["valida"]:
            self._mostrar_licenca(licenca)
            return
        self._mostrar_principal(user, licenca)

    # ── Licença inválida ───────────────────────────────────────────────

    def _mostrar_licenca(self, licenca: dict):
        self._limpar()
        self.title("GeradorBB — Licença")
        self._centrar(400, 420)

        from gui_licenca import construir_licenca
        construir_licenca(self, licenca)

    # ── Principal ──────────────────────────────────────────────────────

    def _mostrar_principal(self, user: dict, licenca: dict):
        self._limpar()
        self.title("GeradorBB")
        self.minsize(960, 640)
        self.resizable(True, True)

        from gui_theme import BG, BG3, ACCENT, TEXT, SUBTEXT, FONT_FAMILY

        # ── Esconde a janela principal durante o carregamento ──────────────
        self.withdraw()

        # ── Janela de loading (única coisa visível enquanto carrega) ───────
        loading = ctk.CTkToplevel(self)
        loading.title("GeradorBB")
        loading.configure(fg_color=BG)
        loading.resizable(False, False)
        loading.protocol("WM_DELETE_WINDOW", lambda: None)  # bloqueia fechar

        LW, LH = 320, 150
        loading.update_idletasks()
        sw = loading.winfo_screenwidth()
        sh = loading.winfo_screenheight()
        loading.geometry(f"{LW}x{LH}+{(sw - LW) // 2}+{(sh - LH) // 2}")
        loading.lift()
        loading.focus_force()

        ctk.CTkLabel(
            loading, text="GeradorBB",
            font=(FONT_FAMILY, 26, "bold"),
            text_color=TEXT,
        ).pack(pady=(28, 2))
        ctk.CTkLabel(
            loading, text="Preparando o ambiente...",
            font=(FONT_FAMILY, 12),
            text_color=SUBTEXT,
        ).pack()
        bar = ctk.CTkProgressBar(
            loading, mode="indeterminate", width=220,
            progress_color=ACCENT, fg_color=BG3,
            height=3, corner_radius=2,
        )
        bar.pack(pady=(14, 0))
        bar.start()
        loading.update()

        # ── Constrói toda a UI (janela oculta, sem travar o cliente) ───────
        from gui_main import construir_principal
        construir_principal(self, user=user, licenca=licenca)

        # ── Tudo pronto: fecha loading e revela o app completo ─────────────
        bar.stop()
        loading.destroy()
        self._centrar(1280, 800)
        self.resizable(True, True)   # _centrar força False — reabilita aqui
        self.deiconify()
        self.state("zoomed")

        self.after(3000, self._checar_atualizacao)

    def _checar_atualizacao(self):
        try:
            import updater
            updater.verificar_atualizacao(
                on_resultado=lambda info: self.after(0, lambda: self._popup_update(info))
            )
        except Exception:
            pass

    def _popup_update(self, info: dict):
        """Popup de atualização completo — notificação + progresso + reinício."""
        from gui_theme import (
            BG, BG2, BG3, BG4, ACCENT, ACCENT3, SUCCESS, WARNING, DANGER,
            TEXT, SUBTEXT, BORDER, FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD,
            FONT_SIZE_LG, CORNER_R, PAD,
        )
        import updater as _upd

        versao = info.get("versao", "?")
        notas  = info.get("notas", "").strip()
        url    = info.get("url_download", "")

        tem_notas = bool(notas)
        ALTURA = 460 if tem_notas else 360

        # ── Janela ──────────────────────────────────────────────────────────
        pop = ctk.CTkToplevel(self)
        pop.title("GeradorBB — Atualização")
        pop.configure(fg_color=BG)
        pop.resizable(False, False)
        pop.grab_set()
        pop.lift()
        pop.focus_force()

        # Centraliza
        W = 480
        pop.update_idletasks()
        sw = pop.winfo_screenwidth()
        sh = pop.winfo_screenheight()
        pop.geometry(f"{W}x{ALTURA}+{(sw - W)//2}+{(sh - ALTURA)//2}")
        pop.protocol("WM_DELETE_WINDOW", lambda: None)   # bloqueado durante download

        # ── Header colorido ──────────────────────────────────────────────────
        header = ctk.CTkFrame(pop, fg_color=ACCENT, corner_radius=0, height=68)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text=f"🚀  Nova versão {versao} disponível!",
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT,
        ).pack(expand=True)

        body = ctk.CTkFrame(pop, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Notas de versão ──────────────────────────────────────────────────
        if tem_notas:
            ctk.CTkLabel(
                body,
                text="O que há de novo:",
                font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
                text_color=SUBTEXT,
                anchor="w",
            ).pack(anchor="w")
            caixa_notas = ctk.CTkTextbox(
                body, height=88,
                fg_color=BG2, border_color=BORDER, border_width=1,
                text_color=TEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
                corner_radius=CORNER_R,
            )
            caixa_notas.pack(fill="x", pady=(4, 14))
            caixa_notas.insert("1.0", notas)
            caixa_notas.configure(state="disabled")

        # ── Etapas visuais ───────────────────────────────────────────────────
        etapas_frame = ctk.CTkFrame(body, fg_color=BG2, corner_radius=CORNER_R,
                                    border_width=1, border_color=BORDER)
        etapas_frame.pack(fill="x", pady=(0, 12))

        etapas_inner = ctk.CTkFrame(etapas_frame, fg_color="transparent")
        etapas_inner.pack(fill="x", padx=16, pady=12)

        _ETAPAS = [("⬇️", "Baixar"), ("📦", "Extrair"), ("🔧", "Instalar")]
        _etapa_widgets = []   # [(icone_lbl, texto_lbl), ...]

        for i, (icone, nome) in enumerate(_ETAPAS):
            col = ctk.CTkFrame(etapas_inner, fg_color="transparent")
            col.pack(side="left", expand=True)

            circulo = ctk.CTkFrame(col, width=40, height=40, corner_radius=20,
                                   fg_color=BG3)
            circulo.pack()
            circulo.pack_propagate(False)
            ico_lbl = ctk.CTkLabel(
                circulo, text=icone,
                font=(FONT_FAMILY, 16),
                text_color=SUBTEXT,
            )
            ico_lbl.pack(expand=True)

            txt_lbl = ctk.CTkLabel(
                col, text=nome,
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=SUBTEXT,
            )
            txt_lbl.pack(pady=(4, 0))
            _etapa_widgets.append((circulo, ico_lbl, txt_lbl))

            # Linha conectora entre etapas
            if i < len(_ETAPAS) - 1:
                linha_col = ctk.CTkFrame(etapas_inner, fg_color="transparent")
                linha_col.pack(side="left", expand=True)
                ctk.CTkFrame(linha_col, height=2, fg_color=BG3).pack(
                    fill="x", pady=(19, 0))

        def _marcar_etapa(idx_ativo: int):
            """Colore as etapas: verde = concluída, accent = ativa, cinza = pendente."""
            for i, (circ, ico, txt) in enumerate(_etapa_widgets):
                if i < idx_ativo:
                    circ.configure(fg_color=SUCCESS)
                    ico.configure(text_color=TEXT)
                    txt.configure(text_color=SUCCESS)
                elif i == idx_ativo:
                    circ.configure(fg_color=ACCENT)
                    ico.configure(text_color=TEXT)
                    txt.configure(text_color=TEXT)
                else:
                    circ.configure(fg_color=BG3)
                    ico.configure(text_color=SUBTEXT)
                    txt.configure(text_color=SUBTEXT)

        # ── Barra de progresso ───────────────────────────────────────────────
        lbl_status = ctk.CTkLabel(
            body,
            text="Pronto para atualizar.",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
            anchor="w",
        )
        lbl_status.pack(anchor="w")

        bar_frame = ctk.CTkFrame(body, fg_color="transparent")
        bar_frame.pack(fill="x", pady=(4, 0))
        bar_frame.columnconfigure(0, weight=1)

        bar = ctk.CTkProgressBar(
            bar_frame, height=18, corner_radius=9,
            progress_color=ACCENT, fg_color=BG3,
        )
        bar.set(0)
        bar.grid(row=0, column=0, sticky="ew")

        lbl_pct = ctk.CTkLabel(
            bar_frame, text="",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT, width=46, anchor="e",
        )
        lbl_pct.grid(row=0, column=1, padx=(8, 0))

        # ── Botões ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))

        def _fechar():
            pop.grab_release()
            pop.protocol("WM_DELETE_WINDOW", pop.destroy)
            pop.destroy()

        btn_depois = ctk.CTkButton(
            btn_row, text="Agora não",
            command=_fechar,
            width=120, height=38,
            fg_color="transparent", hover_color=BG3,
            text_color=SUBTEXT, corner_radius=CORNER_R,
            border_width=1, border_color=BORDER,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        )
        btn_depois.pack(side="right", padx=(8, 0))

        btn_atualizar = ctk.CTkButton(
            btn_row, text="⬆️  Atualizar Agora",
            command=lambda: _iniciar(),
            width=190, height=38,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=CORNER_R,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        )
        btn_atualizar.pack(side="right")

        # ── Lógica de update ─────────────────────────────────────────────────
        def _iniciar():
            btn_atualizar.configure(state="disabled")
            btn_depois.configure(state="disabled")
            # bloqueia fechar durante o processo
            pop.protocol("WM_DELETE_WINDOW", lambda: None)
            _marcar_etapa(0)
            lbl_status.configure(text="Conectando ao servidor...", text_color=SUBTEXT)

        def _on_progresso(pct: int, etapa: str):
            def _ui():
                if etapa == "baixando":
                    _marcar_etapa(0)
                    bar.configure(mode="determinate")
                    bar.set(pct / 100)
                    lbl_pct.configure(text=f"{pct}%")
                    lbl_status.configure(
                        text=f"Baixando atualização... {pct}%",
                        text_color=SUBTEXT,
                    )
                elif etapa == "extraindo":
                    _marcar_etapa(1)
                    bar.configure(mode="indeterminate")
                    bar.start()
                    lbl_pct.configure(text="")
                    lbl_status.configure(
                        text="Extraindo arquivos...", text_color=SUBTEXT)
                elif etapa == "preparando":
                    _marcar_etapa(2)
                    lbl_status.configure(
                        text="Preparando instalação...", text_color=SUBTEXT)
            pop.after(0, _ui)

        def _on_fim(ok: bool, resultado: str):
            def _ui():
                if ok:
                    bar.stop()
                    bar.configure(mode="determinate")
                    bar.set(1.0)
                    bar.configure(progress_color=SUCCESS)
                    lbl_pct.configure(text="100%", text_color=SUCCESS)
                    # Todas as etapas verdes
                    for circ, ico, txt in _etapa_widgets:
                        circ.configure(fg_color=SUCCESS)
                        ico.configure(text_color=TEXT)
                        txt.configure(text_color=SUCCESS)
                    # Contagem regressiva 3..2..1
                    def _countdown(n):
                        if n > 0:
                            lbl_status.configure(
                                text=f"✅  Tudo pronto! Reiniciando em {n}s...",
                                text_color=SUCCESS,
                            )
                            pop.after(1000, lambda: _countdown(n - 1))
                        else:
                            lbl_status.configure(
                                text="Reiniciando...", text_color=SUCCESS)
                            pop.after(400, lambda: _upd.aplicar_atualizacao(resultado))
                    _countdown(3)
                else:
                    bar.stop()
                    bar.configure(mode="determinate", progress_color=DANGER)
                    bar.set(1.0)
                    lbl_pct.configure(text="")
                    lbl_status.configure(
                        text=f"✗  Erro ao atualizar: {resultado}",
                        text_color=DANGER,
                    )
                    btn_depois.configure(state="normal", text="Fechar")
            pop.after(0, _ui)

        # Sobrescreve o command do botão para incluir o kick-off do download
        def _iniciar_completo():
            _iniciar()
            _upd.baixar_e_instalar(
                url, versao,
                on_progresso=_on_progresso,
                on_fim=_on_fim,
            )

        btn_atualizar.configure(command=_iniciar_completo)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
