# gui_licenca.py — Modal de licença expirada / inválida

import customtkinter as ctk
import webbrowser
from gui_theme import (
    BG, BG2, ACCENT, ACCENT3, DANGER, TEXT, SUBTEXT,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG,
    FONT_SIZE_XL, FONT_SIZE_XXL, CORNER_R, PAD,
)
import auth

URL_RENOVAR = "https://geradorbb.com.br/renovar"


class JanelaLicenca(ctk.CTk):
    """
    Janela exibida quando a licença está expirada ou inválida.
    Após fechar (via Sair), o app encerra.
    """

    def __init__(self, licenca: dict):
        super().__init__()
        self._info = licenca

        self.title("GeradorBB — Licença")
        self.geometry("400x420")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        # Centraliza
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - 400) // 2
        y  = (sh - 420) // 2
        self.geometry(f"400x420+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._sair)
        self.grab_set()   # modal
        self.lift()
        self.focus_force()

        self._build_ui()

    def _build_ui(self):
        # Ícone de cadeado
        ctk.CTkLabel(
            self,
            text="🔒",
            font=(FONT_FAMILY, 64),
            text_color=DANGER,
        ).pack(pady=(36, 8))

        # Título
        expirou = self._info.get("expira") is not None
        titulo  = "Sua licença expirou" if expirou else "Acesso não autorizado"
        ctk.CTkLabel(
            self,
            text=titulo,
            font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
            text_color=TEXT,
        ).pack(pady=(0, 8))

        # Subtítulo com data
        if expirou:
            sub = f"Expirada em {self._info.get('expira', '—')}"
        else:
            sub = "Nenhuma licença ativa encontrada para esta conta."
        ctk.CTkLabel(
            self,
            text=sub,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
            wraplength=320,
        ).pack(pady=(0, 32))

        # Botão renovar
        ctk.CTkButton(
            self,
            text="Renovar licença",
            command=self._renovar,
            width=260,
            height=44,
            corner_radius=CORNER_R,
            fg_color=ACCENT,
            hover_color=ACCENT3,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(pady=(0, 12))

        # Botão sair
        ctk.CTkButton(
            self,
            text="Sair",
            command=self._sair,
            width=260,
            height=40,
            corner_radius=CORNER_R,
            fg_color="transparent",
            hover_color=BG2,
            border_color=DANGER,
            border_width=1,
            text_color=DANGER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        ).pack()

    def _renovar(self):
        webbrowser.open(URL_RENOVAR)

    def _sair(self):
        import sys
        auth.logout()
        sys.exit(0)


# ---------------------------------------------------------------------------
# Função para uso com janela externa (master já existente)
# ---------------------------------------------------------------------------

def construir_licenca(master, licenca: dict):
    """Constrói a UI de licença inválida/expirada dentro da janela `master` existente."""
    import sys

    info = licenca

    # Ícone de cadeado
    ctk.CTkLabel(
        master,
        text="🔒",
        font=(FONT_FAMILY, 64),
        text_color=DANGER,
    ).pack(pady=(36, 8))

    # Título
    expirou = info.get("expira") is not None
    titulo  = "Sua licença expirou" if expirou else "Acesso não autorizado"
    ctk.CTkLabel(
        master,
        text=titulo,
        font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
        text_color=TEXT,
    ).pack(pady=(0, 8))

    # Subtítulo com data
    if expirou:
        sub = f"Expirada em {info.get('expira', '—')}"
    else:
        sub = "Nenhuma licença ativa encontrada para esta conta."
    ctk.CTkLabel(
        master,
        text=sub,
        font=(FONT_FAMILY, FONT_SIZE_SM),
        text_color=SUBTEXT,
        wraplength=320,
    ).pack(pady=(0, 32))

    # Botão renovar
    ctk.CTkButton(
        master,
        text="Renovar licença",
        command=lambda: webbrowser.open(URL_RENOVAR),
        width=260,
        height=44,
        corner_radius=CORNER_R,
        fg_color=ACCENT,
        hover_color=ACCENT3,
        text_color=TEXT,
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
    ).pack(pady=(0, 12))

    # Botão sair
    def _sair_fn():
        auth.logout()
        sys.exit(0)

    ctk.CTkButton(
        master,
        text="Sair",
        command=_sair_fn,
        width=260,
        height=40,
        corner_radius=CORNER_R,
        fg_color="transparent",
        hover_color=BG2,
        border_color=DANGER,
        border_width=1,
        text_color=DANGER,
        font=(FONT_FAMILY, FONT_SIZE_MD),
    ).pack()
