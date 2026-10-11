# gui_login.py — Janela de login / cadastro / recuperar senha
#
# Janela 420×600px, centralizada, sem resize.
# Chama auth.py para validar credenciais (mock hoje, Supabase depois).

import base64
import json
import customtkinter as ctk
from pathlib import Path
from gui_theme import (
    BG, BG2, BG3, BG4, ACCENT, ACCENT2, ACCENT3, SUCCESS, DANGER, TEXT, SUBTEXT, BORDER,
    BG_ERRO, BG_ERRO_BORDER, BG_SUCESSO_ACTIVE, BG_SUCESSO_ACTIVE_BORDER,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL,
    FONT_SIZE_XXL, FONT_TITLE, FONT_BODY, FONT_SMALL, CORNER_R, PAD,
)
import auth

_CRED_FILE = Path(__file__).parent / "credenciais.json"


def _salvar_credenciais(email: str, senha: str):
    data = {
        "email": email,
        "senha": base64.b64encode(senha.encode()).decode(),
    }
    _CRED_FILE.write_text(json.dumps(data), encoding="utf-8")


def _carregar_credenciais() -> tuple[str, str]:
    """Retorna (email, senha) ou ('', '')."""
    try:
        if _CRED_FILE.exists():
            d = json.loads(_CRED_FILE.read_text(encoding="utf-8"))
            email = d.get("email", "")
            senha = base64.b64decode(d.get("senha", "").encode()).decode()
            return email, senha
    except Exception:
        pass
    return "", ""


def _apagar_credenciais():
    if _CRED_FILE.exists():
        _CRED_FILE.unlink()

# ---------------------------------------------------------------------------
# Helpers de estilo
# ---------------------------------------------------------------------------

def _entry(master, placeholder="", show=""):
    e = ctk.CTkEntry(
        master,
        placeholder_text=placeholder,
        show=show,
        height=44,
        corner_radius=8,
        fg_color=BG3,
        border_color=BORDER,
        border_width=1,
        text_color=TEXT,
        placeholder_text_color=SUBTEXT,
        font=(FONT_FAMILY, FONT_SIZE_MD),
    )
    return e


def _btn_primary(master, text, command, width=340):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=46,
        corner_radius=CORNER_R,
        fg_color=ACCENT,
        hover_color=ACCENT3,
        text_color=TEXT,
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
    )


def _label_link(master, text, command):
    lbl = ctk.CTkLabel(
        master,
        text=text,
        text_color=ACCENT,
        cursor="hand2",
        font=(FONT_FAMILY, FONT_SIZE_SM),
    )
    lbl.bind("<Button-1>", lambda _: command())
    # underline efeito hover
    lbl.bind("<Enter>", lambda _: lbl.configure(text_color=ACCENT2))
    lbl.bind("<Leave>", lambda _: lbl.configure(text_color=ACCENT))
    return lbl


def _label_erro(master):
    return ctk.CTkLabel(
        master,
        text="",
        text_color=DANGER,
        font=(FONT_FAMILY, FONT_SIZE_SM),
        wraplength=340,
    )


def _separador_deco(master, width=340):
    """Separador decorativo com linha + ponto central."""
    f = ctk.CTkFrame(master, fg_color="transparent", height=20)
    f.pack(fill="x", pady=(8, 12))
    f.pack_propagate(False)
    ctk.CTkFrame(f, height=1, fg_color=BORDER).place(relx=0, rely=0.5, relwidth=1, anchor="w")
    return f


# ---------------------------------------------------------------------------
# Janela principal de login
# ---------------------------------------------------------------------------

class JanelaLogin(ctk.CTk):
    """
    Janela de login/cadastro/recuperar senha.
    Chama `on_sucesso(user_dict)` quando o login for bem-sucedido.
    """

    def __init__(self, on_sucesso):
        super().__init__()
        self.on_sucesso = on_sucesso
        self._senha_visivel_login    = False
        self._senha_visivel_cad      = False
        self._senha_visivel_cad_conf = False
        self._lembrar_var = ctk.BooleanVar(value=_CRED_FILE.exists())

        self.title("GeradorBB — Acesso")
        self.geometry("440x700")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        # Centraliza na tela
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - 440) // 2
        y  = (sh - 700) // 2
        self.geometry(f"440x700+{x}+{y}")

        # Impede fechar sem estar logado
        self.protocol("WM_DELETE_WINDOW", self._on_fechar)
        self.lift()
        self.focus_force()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Elemento decorativo de fundo — círculo accent simulado no topo
        _deco = ctk.CTkFrame(self, width=180, height=180,
                             corner_radius=90, fg_color=ACCENT)
        _deco.place(x=-60, y=-60)
        # Segundo círculo menor
        _deco2 = ctk.CTkFrame(self, width=80, height=80,
                              corner_radius=40, fg_color=ACCENT2)
        _deco2.place(x=380, y=600)

        # Card central — usa pack para garantir renderização correta no Windows
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=25, pady=30)

        card = ctk.CTkFrame(wrapper, fg_color=BG2,
                            corner_radius=16,
                            border_width=1, border_color=BORDER,
                            width=390, height=640)
        card.pack(expand=True)
        card.pack_propagate(False)

        # Cabeçalho dentro do card
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(pady=(28, 0))

        # Ícone grande
        ctk.CTkLabel(
            header,
            text="🎬",
            font=(FONT_FAMILY, 40),
        ).pack()

        ctk.CTkLabel(
            header,
            text="GeradorBB",
            font=FONT_TITLE,
            text_color=ACCENT,
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            header,
            text="Gerador de Vídeos Top 10",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
        ).pack(pady=(2, 0))

        # Separador decorativo
        sep_frame = ctk.CTkFrame(card, fg_color="transparent", height=14)
        sep_frame.pack(fill="x", padx=32, pady=(10, 0))
        ctk.CTkFrame(sep_frame, height=1, fg_color=BORDER).place(
            relx=0, rely=0.5, relwidth=1, anchor="w")

        # Container de frames (login / cadastro / recuperar)
        self._container = ctk.CTkFrame(card, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=24, pady=(10, 20))

        self._frame_login     = self._build_frame_login()
        self._frame_cadastro  = self._build_frame_cadastro()
        self._frame_recuperar = self._build_frame_recuperar()

        self._mostrar_frame(self._frame_login)

    def _mostrar_frame(self, frame):
        for f in (self._frame_login, self._frame_cadastro, self._frame_recuperar):
            f.pack_forget()
        frame.pack(fill="both", expand=True)

    # ---- Frame Login ----

    def _build_frame_login(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Entrar na sua conta",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._login_email = _entry(f, "seu@email.com")
        self._login_email.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(f, text="Senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")

        senha_row = ctk.CTkFrame(f, fg_color="transparent")
        senha_row.pack(fill="x", pady=(2, 4))
        self._login_senha = _entry(senha_row, "••••••••", show="•")
        self._login_senha.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            senha_row, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_login,
        ).pack(side="left", padx=(4, 0))

        # Checkbox "Lembrar e-mail e senha"
        ctk.CTkCheckBox(
            f, text="Lembrar e-mail e senha",
            variable=self._lembrar_var,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
            fg_color=ACCENT, hover_color=ACCENT2,
            checkmark_color=TEXT, border_color=BORDER,
        ).pack(anchor="w", pady=(6, 2))

        # Mensagem de erro
        self._login_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                              corner_radius=6, border_width=1,
                                              border_color=BG_ERRO_BORDER)
        self._login_erro = ctk.CTkLabel(self._login_erro_frame, text="",
                                        text_color=DANGER,
                                        font=(FONT_FAMILY, FONT_SIZE_SM),
                                        wraplength=310)
        self._login_erro.pack(padx=10, pady=6)

        self._btn_login = _btn_primary(f, "Entrar", self._fazer_login)
        self._btn_login.pack(pady=(8, 10), fill="x")

        links = ctk.CTkFrame(f, fg_color="transparent")
        links.pack()
        _label_link(links, "Criar conta",
                    lambda: self._mostrar_frame(self._frame_cadastro)).pack(side="left", padx=8)
        ctk.CTkLabel(links, text="·", text_color=SUBTEXT,
                     font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")
        _label_link(links, "Esqueci minha senha",
                    lambda: self._mostrar_frame(self._frame_recuperar)).pack(side="left", padx=8)

        # Preenche campos se houver credenciais salvas
        email_salvo, senha_salva = _carregar_credenciais()
        if email_salvo:
            self._login_email.insert(0, email_salvo)
            self._login_senha.insert(0, senha_salva)

        return f

    # ---- Frame Cadastro ----

    def _build_frame_cadastro(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Criar nova conta",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(f, text="Nome", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._cad_nome = _entry(f, "Seu nome completo")
        self._cad_nome.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._cad_email = _entry(f, "seu@email.com")
        self._cad_email.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(f, text="Senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        row1 = ctk.CTkFrame(f, fg_color="transparent")
        row1.pack(fill="x", pady=(2, 8))
        self._cad_senha = _entry(row1, "Mínimo 6 caracteres", show="•")
        self._cad_senha.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row1, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_cad,
        ).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(f, text="Confirmar senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", pady=(2, 4))
        self._cad_conf = _entry(row2, "Repita a senha", show="•")
        self._cad_conf.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row2, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_cad_conf,
        ).pack(side="left", padx=(4, 0))

        self._cad_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                            corner_radius=6, border_width=1,
                                            border_color=BG_ERRO_BORDER)
        self._cad_erro = ctk.CTkLabel(self._cad_erro_frame, text="",
                                      text_color=DANGER,
                                      font=(FONT_FAMILY, FONT_SIZE_SM),
                                      wraplength=310)
        self._cad_erro.pack(padx=10, pady=6)

        self._btn_cad = _btn_primary(f, "Criar conta", self._fazer_cadastro)
        self._btn_cad.pack(pady=(8, 10), fill="x")

        _label_link(f, "← Já tenho conta",
                    lambda: self._mostrar_frame(self._frame_login)).pack()

        return f

    # ---- Frame Recuperar ----

    def _build_frame_recuperar(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Recuperar senha",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(f, text="Digite seu e-mail e enviaremos um link para redefinir sua senha.",
                     text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
                     wraplength=340, justify="left").pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._rec_email = _entry(f, "seu@email.com")
        self._rec_email.pack(fill="x", pady=(2, 4))

        self._rec_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                            corner_radius=6, border_width=1,
                                            border_color=BG_ERRO_BORDER)
        self._rec_erro = ctk.CTkLabel(self._rec_erro_frame, text="",
                                      text_color=DANGER,
                                      font=(FONT_FAMILY, FONT_SIZE_SM),
                                      wraplength=310)
        self._rec_erro.pack(padx=10, pady=6)

        self._rec_msg = ctk.CTkLabel(f, text="", text_color=SUCCESS,
                                     font=(FONT_FAMILY, FONT_SIZE_SM), wraplength=340)
        self._rec_msg.pack(pady=(0, 6))

        self._btn_rec = _btn_primary(f, "Enviar link", self._fazer_recuperar)
        self._btn_rec.pack(pady=(8, 10), fill="x")

        _label_link(f, "← Voltar",
                    lambda: self._mostrar_frame(self._frame_login)).pack()

        return f

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _toggle_senha_login(self):
        self._senha_visivel_login = not self._senha_visivel_login
        self._login_senha.configure(show="" if self._senha_visivel_login else "•")

    def _toggle_senha_cad(self):
        self._senha_visivel_cad = not self._senha_visivel_cad
        self._cad_senha.configure(show="" if self._senha_visivel_cad else "•")

    def _toggle_senha_cad_conf(self):
        self._senha_visivel_cad_conf = not self._senha_visivel_cad_conf
        self._cad_conf.configure(show="" if self._senha_visivel_cad_conf else "•")

    def _set_erro_login(self, msg: str):
        self._login_erro.configure(text=msg)
        if msg:
            self._login_erro_frame.pack(fill="x", pady=(0, 8), before=self._btn_login)
        else:
            self._login_erro_frame.pack_forget()

    def _set_erro_cad(self, msg: str):
        self._cad_erro.configure(text=msg)
        if msg:
            self._cad_erro_frame.pack(fill="x", pady=(0, 6), before=self._btn_cad)
        else:
            self._cad_erro_frame.pack_forget()

    def _set_erro_rec(self, msg: str):
        self._rec_erro.configure(text=msg)
        if msg:
            self._rec_erro_frame.pack(fill="x", pady=(0, 6), before=self._btn_rec)
        else:
            self._rec_erro_frame.pack_forget()

    def _fazer_login(self):
        self._set_erro_login("")
        self._btn_login.configure(text="Entrando...", state="disabled")
        self.update()

        email = self._login_email.get().strip()
        senha = self._login_senha.get()

        resultado = auth.login(email, senha)

        if resultado["ok"]:
            if self._lembrar_var.get():
                _salvar_credenciais(email, senha)
            else:
                _apagar_credenciais()
            self.destroy()
            self.on_sucesso(resultado["user"])
        else:
            self._set_erro_login(resultado["erro"])
            self._btn_login.configure(text="Entrar", state="normal")

    def _fazer_cadastro(self):
        self._set_erro_cad("")
        email = self._cad_email.get().strip()
        nome  = self._cad_nome.get().strip()
        senha = self._cad_senha.get()
        conf  = self._cad_conf.get()

        if senha != conf:
            self._set_erro_cad("As senhas não coincidem.")
            return

        self._btn_cad.configure(text="Criando conta...", state="disabled")
        self.update()

        try:
            resultado = auth.cadastrar(email, senha, nome)
        except Exception as ex:
            import traceback
            from pathlib import Path
            Path(__file__).parent.joinpath("erro_login.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            resultado = {"ok": False, "erro": f"Erro interno: {ex}"}

        if resultado["ok"]:
            if resultado.get("confirmar_email"):
                # Supabase pediu confirmação por e-mail — volta para login com aviso
                self._btn_cad.configure(text="Criar conta", state="normal")
                self._mostrar_frame(self._frame_login)
                self._login_erro.configure(
                    text="Conta criada! Verifique seu e-mail e clique no link de confirmacao antes de entrar.",
                    text_color=SUCCESS,
                )
                self._login_erro_frame.configure(fg_color=BG_SUCESSO_ACTIVE, border_color=BG_SUCESSO_ACTIVE_BORDER)
                self._login_erro_frame.pack(fill="x", pady=(0, 8), before=self._btn_login)
            else:
                self.destroy()
                self.on_sucesso(resultado["user"])
        else:
            self._set_erro_cad(resultado["erro"])
            self._btn_cad.configure(text="Criar conta", state="normal")

    def _fazer_recuperar(self):
        self._set_erro_rec("")
        self._rec_msg.configure(text="")
        email = self._rec_email.get().strip()

        self._btn_rec.configure(text="Enviando...", state="disabled")
        self.update()

        resultado = auth.recuperar_senha(email)

        self._btn_rec.configure(text="Enviar link", state="normal")
        if resultado["ok"]:
            self._rec_msg.configure(text=resultado["msg"])
        else:
            self._set_erro_rec(resultado["erro"])

    def _on_fechar(self):
        # Não permite fechar sem autenticar — encerra o app
        import sys
        sys.exit(0)


# ---------------------------------------------------------------------------
# Controller para uso com janela externa (master já existente)
# ---------------------------------------------------------------------------

class _LoginController:
    """
    Constrói a UI de login dentro de `master` (janela CTk existente).
    Não herda de CTk — apenas usa master como container.
    """

    def __init__(self, master, on_sucesso):
        self._master = master
        self.on_sucesso = on_sucesso
        self._senha_visivel_login    = False
        self._senha_visivel_cad      = False
        self._senha_visivel_cad_conf = False
        self._lembrar_var = ctk.BooleanVar(value=_CRED_FILE.exists())
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Elemento decorativo de fundo — círculo accent simulado no topo
        _deco = ctk.CTkFrame(self._master, width=180, height=180,
                             corner_radius=90, fg_color=ACCENT)
        _deco.place(x=-60, y=-60)
        # Segundo círculo menor
        _deco2 = ctk.CTkFrame(self._master, width=80, height=80,
                              corner_radius=40, fg_color=ACCENT2)
        _deco2.place(x=380, y=600)

        # Card central — usa pack para garantir renderização correta no Windows
        wrapper = ctk.CTkFrame(self._master, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=25, pady=30)

        card = ctk.CTkFrame(wrapper, fg_color=BG2,
                            corner_radius=16,
                            border_width=1, border_color=BORDER,
                            width=390, height=640)
        card.pack(expand=True)
        card.pack_propagate(False)

        # Cabeçalho dentro do card
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(pady=(28, 0))

        # Ícone grande
        ctk.CTkLabel(
            header,
            text="🎬",
            font=(FONT_FAMILY, 40),
        ).pack()

        ctk.CTkLabel(
            header,
            text="GeradorBB",
            font=FONT_TITLE,
            text_color=ACCENT,
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            header,
            text="Gerador de Vídeos Top 10",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
        ).pack(pady=(2, 0))

        # Separador decorativo
        sep_frame = ctk.CTkFrame(card, fg_color="transparent", height=14)
        sep_frame.pack(fill="x", padx=32, pady=(10, 0))
        ctk.CTkFrame(sep_frame, height=1, fg_color=BORDER).place(
            relx=0, rely=0.5, relwidth=1, anchor="w")

        # Container de frames (login / cadastro / recuperar)
        self._container = ctk.CTkFrame(card, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=24, pady=(10, 20))

        self._frame_login     = self._build_frame_login()
        self._frame_cadastro  = self._build_frame_cadastro()
        self._frame_recuperar = self._build_frame_recuperar()

        self._mostrar_frame(self._frame_login)

    def _mostrar_frame(self, frame):
        for f in (self._frame_login, self._frame_cadastro, self._frame_recuperar):
            f.pack_forget()
        frame.pack(fill="both", expand=True)

    # ---- Frame Login ----

    def _build_frame_login(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Entrar na sua conta",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._login_email = _entry(f, "seu@email.com")
        self._login_email.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(f, text="Senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")

        senha_row = ctk.CTkFrame(f, fg_color="transparent")
        senha_row.pack(fill="x", pady=(2, 4))
        self._login_senha = _entry(senha_row, "••••••••", show="•")
        self._login_senha.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            senha_row, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_login,
        ).pack(side="left", padx=(4, 0))

        # Checkbox "Lembrar e-mail e senha"
        ctk.CTkCheckBox(
            f, text="Lembrar e-mail e senha",
            variable=self._lembrar_var,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=SUBTEXT,
            fg_color=ACCENT, hover_color=ACCENT2,
            checkmark_color=TEXT, border_color=BORDER,
        ).pack(anchor="w", pady=(6, 2))

        self._login_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                              corner_radius=6, border_width=1,
                                              border_color=BG_ERRO_BORDER)
        self._login_erro = ctk.CTkLabel(self._login_erro_frame, text="",
                                        text_color=DANGER,
                                        font=(FONT_FAMILY, FONT_SIZE_SM),
                                        wraplength=310)
        self._login_erro.pack(padx=10, pady=6)

        self._btn_login = _btn_primary(f, "Entrar", self._fazer_login)
        self._btn_login.pack(pady=(8, 10), fill="x")

        links = ctk.CTkFrame(f, fg_color="transparent")
        links.pack()
        _label_link(links, "Criar conta",
                    lambda: self._mostrar_frame(self._frame_cadastro)).pack(side="left", padx=8)
        ctk.CTkLabel(links, text="·", text_color=SUBTEXT,
                     font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")
        _label_link(links, "Esqueci minha senha",
                    lambda: self._mostrar_frame(self._frame_recuperar)).pack(side="left", padx=8)

        # Preenche campos se houver credenciais salvas
        email_salvo, senha_salva = _carregar_credenciais()
        if email_salvo:
            self._login_email.insert(0, email_salvo)
            self._login_senha.insert(0, senha_salva)

        return f

    # ---- Frame Cadastro ----

    def _build_frame_cadastro(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Criar nova conta",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(f, text="Nome", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._cad_nome = _entry(f, "Seu nome completo")
        self._cad_nome.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._cad_email = _entry(f, "seu@email.com")
        self._cad_email.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(f, text="Senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        row1 = ctk.CTkFrame(f, fg_color="transparent")
        row1.pack(fill="x", pady=(2, 8))
        self._cad_senha = _entry(row1, "Mínimo 6 caracteres", show="•")
        self._cad_senha.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row1, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_cad,
        ).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(f, text="Confirmar senha", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", pady=(2, 4))
        self._cad_conf = _entry(row2, "Repita a senha", show="•")
        self._cad_conf.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row2, text="👁", width=40, height=44,
            fg_color=BG3, hover_color=BG2, text_color=SUBTEXT,
            corner_radius=8, border_width=1, border_color=BORDER,
            command=self._toggle_senha_cad_conf,
        ).pack(side="left", padx=(4, 0))

        self._cad_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                            corner_radius=6, border_width=1,
                                            border_color=BG_ERRO_BORDER)
        self._cad_erro = ctk.CTkLabel(self._cad_erro_frame, text="",
                                      text_color=DANGER,
                                      font=(FONT_FAMILY, FONT_SIZE_SM),
                                      wraplength=310)
        self._cad_erro.pack(padx=10, pady=6)

        self._btn_cad = _btn_primary(f, "Criar conta", self._fazer_cadastro)
        self._btn_cad.pack(pady=(8, 10), fill="x")

        _label_link(f, "← Já tenho conta",
                    lambda: self._mostrar_frame(self._frame_login)).pack()

        return f

    # ---- Frame Recuperar ----

    def _build_frame_recuperar(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")

        ctk.CTkLabel(f, text="Recuperar senha",
                     font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(f, text="Digite seu e-mail e enviaremos um link para redefinir sua senha.",
                     text_color=SUBTEXT, font=(FONT_FAMILY, FONT_SIZE_SM),
                     wraplength=340, justify="left").pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(f, text="E-mail", font=(FONT_FAMILY, FONT_SIZE_SM),
                     text_color=SUBTEXT).pack(anchor="w")
        self._rec_email = _entry(f, "seu@email.com")
        self._rec_email.pack(fill="x", pady=(2, 4))

        self._rec_erro_frame = ctk.CTkFrame(f, fg_color=BG_ERRO,
                                            corner_radius=6, border_width=1,
                                            border_color=BG_ERRO_BORDER)
        self._rec_erro = ctk.CTkLabel(self._rec_erro_frame, text="",
                                      text_color=DANGER,
                                      font=(FONT_FAMILY, FONT_SIZE_SM),
                                      wraplength=310)
        self._rec_erro.pack(padx=10, pady=6)

        self._rec_msg = ctk.CTkLabel(f, text="", text_color=SUCCESS,
                                     font=(FONT_FAMILY, FONT_SIZE_SM), wraplength=340)
        self._rec_msg.pack(pady=(0, 6))

        self._btn_rec = _btn_primary(f, "Enviar link", self._fazer_recuperar)
        self._btn_rec.pack(pady=(8, 10), fill="x")

        _label_link(f, "← Voltar",
                    lambda: self._mostrar_frame(self._frame_login)).pack()

        return f

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _toggle_senha_login(self):
        self._senha_visivel_login = not self._senha_visivel_login
        self._login_senha.configure(show="" if self._senha_visivel_login else "•")

    def _toggle_senha_cad(self):
        self._senha_visivel_cad = not self._senha_visivel_cad
        self._cad_senha.configure(show="" if self._senha_visivel_cad else "•")

    def _toggle_senha_cad_conf(self):
        self._senha_visivel_cad_conf = not self._senha_visivel_cad_conf
        self._cad_conf.configure(show="" if self._senha_visivel_cad_conf else "•")

    def _set_erro_login(self, msg: str):
        self._login_erro.configure(text=msg)
        if msg:
            self._login_erro_frame.pack(fill="x", pady=(0, 8), before=self._btn_login)
        else:
            self._login_erro_frame.pack_forget()

    def _set_erro_cad(self, msg: str):
        self._cad_erro.configure(text=msg)
        if msg:
            self._cad_erro_frame.pack(fill="x", pady=(0, 6), before=self._btn_cad)
        else:
            self._cad_erro_frame.pack_forget()

    def _set_erro_rec(self, msg: str):
        self._rec_erro.configure(text=msg)
        if msg:
            self._rec_erro_frame.pack(fill="x", pady=(0, 6), before=self._btn_rec)
        else:
            self._rec_erro_frame.pack_forget()

    def _fazer_login(self):
        self._set_erro_login("")
        self._btn_login.configure(text="Entrando...", state="disabled")
        self._master.update()

        email = self._login_email.get().strip()
        senha = self._login_senha.get()

        resultado = auth.login(email, senha)

        if resultado["ok"]:
            if self._lembrar_var.get():
                _salvar_credenciais(email, senha)
            else:
                _apagar_credenciais()
            self.on_sucesso(resultado["user"])
        else:
            self._set_erro_login(resultado["erro"])
            self._btn_login.configure(text="Entrar", state="normal")

    def _fazer_cadastro(self):
        self._set_erro_cad("")
        email = self._cad_email.get().strip()
        nome  = self._cad_nome.get().strip()
        senha = self._cad_senha.get()
        conf  = self._cad_conf.get()

        if senha != conf:
            self._set_erro_cad("As senhas não coincidem.")
            return

        self._btn_cad.configure(text="Criando conta...", state="disabled")
        self._master.update()

        try:
            resultado = auth.cadastrar(email, senha, nome)
        except Exception as ex:
            import traceback
            from pathlib import Path
            Path(__file__).parent.joinpath("erro_login.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            resultado = {"ok": False, "erro": f"Erro interno: {ex}"}

        if resultado["ok"]:
            if resultado.get("confirmar_email"):
                # Supabase pediu confirmação por e-mail — volta para login com aviso
                self._btn_cad.configure(text="Criar conta", state="normal")
                self._mostrar_frame(self._frame_login)
                self._login_erro.configure(
                    text="Conta criada! Verifique seu e-mail e clique no link de confirmacao antes de entrar.",
                    text_color=SUCCESS,
                )
                self._login_erro_frame.configure(fg_color=BG_SUCESSO_ACTIVE, border_color=BG_SUCESSO_ACTIVE_BORDER)
                self._login_erro_frame.pack(fill="x", pady=(0, 8), before=self._btn_login)
            else:
                self.on_sucesso(resultado["user"])
        else:
            self._set_erro_cad(resultado["erro"])
            self._btn_cad.configure(text="Criar conta", state="normal")

    def _fazer_recuperar(self):
        self._set_erro_rec("")
        self._rec_msg.configure(text="")
        email = self._rec_email.get().strip()

        self._btn_rec.configure(text="Enviando...", state="disabled")
        self._master.update()

        resultado = auth.recuperar_senha(email)

        self._btn_rec.configure(text="Enviar link", state="normal")
        if resultado["ok"]:
            self._rec_msg.configure(text=resultado["msg"])
        else:
            self._set_erro_rec(resultado["erro"])

    def _on_fechar(self):
        import sys
        sys.exit(0)


def construir_login(master, on_sucesso):
    """Constrói a UI de login dentro da janela `master` existente."""
    return _LoginController(master, on_sucesso)
