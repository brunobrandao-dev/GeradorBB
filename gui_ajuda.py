# gui_ajuda.py — Assistente flutuante do GeradorBB
#
# Painel lateral que abre sobre qualquer tela sem interromper o fluxo.
# Chave carregada de config_ia.enc (não versionado).

from __future__ import annotations

import re
import sys
import json
import threading
import datetime
from pathlib import Path

import customtkinter as ctk

from gui_theme import (
    BG, BG2, BG3, BG4, ACCENT, ACCENT3, SUCCESS, WARNING, DANGER, INFO,
    TEXT, SUBTEXT, BORDER, BORDER2,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG,
    CORNER_R, PAD,
)


def _ler_chave_assistente() -> str:
    """Lê a chave do assistente de config_ia.enc (não versionado)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    try:
        dados = json.loads((base / "config_ia.enc").read_text(encoding="utf-8"))
        return dados.get("assistente_key", "")
    except Exception:
        return ""


# ── Chave e modelo do assistente ─────────────────────────────────────────────
_CHAVE_ASSISTENTE  = _ler_chave_assistente()
_MODELO_ASSISTENTE = "gemini-3.8-flash"

# ── Largura do painel flutuante ───────────────────────────────────────────────
_PAINEL_W = 280
_PAINEL_H = 420

# ---------------------------------------------------------------------------
# Prompt de sistema
# ---------------------------------------------------------------------------

_PROMPT_SISTEMA = """Você é o assistente oficial do GeradorBB, embutido dentro do próprio aplicativo.

REGRA PRINCIPAL — OBRIGATÓRIA:
Você responde SOMENTE perguntas sobre o GeradorBB e como usá-lo.
Se o usuário perguntar qualquer coisa fora do app (matemática, receitas, política, outros softwares, curiosidades gerais, etc.), responda educadamente que só pode ajudar com o GeradorBB.
Exemplo de recusa: "Só consigo ajudar com dúvidas sobre o GeradorBB. Tem alguma dúvida sobre como usar o app?"

SOBRE O GERADORBB:
Software desktop (Windows) que gera vídeos verticais automáticos (YouTube Shorts / Reels).
O usuário organiza imagens, roteiros e áudios — o app gera o vídeo com legendas sincronizadas, zoom, música de fundo e narração.

FUNCIONALIDADES:

1. GERAR VÍDEO
   - Gera vídeos em PT (português) e/ou EN (inglês)
   - Escolha o template, organize as cenas e clique em Gerar
   - Vídeo salvo em Documentos/GeradorBB/canais/[canal]/videos/

2. CENAS
   - Define a ordem das imagens/vídeos que aparecerão no vídeo
   - Arquivos ficam em canais/[canal]/projeto/cenas/

3. ROTEIRO
   - Edita o texto da narração em PT e EN
   - Usado tanto para as legendas quanto para a narração
   - Mostra contador de palavras e estimativa de duração

4. TEMPLATES
   - Definem a estrutura do vídeo (tipos: livre, numerado, seções)
   - Controlam quantas cenas aparecem, ordem, abertura e fechamento
   - É possível criar templates personalizados

5. PERSONAGEM
   - Adiciona um personagem animado/PNG sobre o vídeo
   - Pode ser ativado/desativado nas configurações

6. PREVIEW
   - Gera um preview de ~40 segundos para conferir o layout antes de gerar o vídeo completo

7. MEUS VÍDEOS
   - Biblioteca de todos os vídeos gerados
   - Permite abrir, renomear e excluir vídeos

8. CONFIGURAÇÕES
   - Resolução (padrão 1080x1920), FPS, fundo (preto/desfocado)
   - Fonte, tamanho e posição das legendas
   - Modelo de transcrição (tiny/base/small/medium/large)
   - Volume da música de fundo

9. PROJETOS
   - Vários projetos separados (ex: um por canal)
   - Cada projeto tem suas próprias cenas, roteiros, áudios e vídeos
   - Projeto ativo selecionado no menu superior da sidebar

ESTRUTURA DE ARQUIVOS:
- Tudo em Documentos/GeradorBB/
- canais/[canal]/projeto/cenas/ → imagens das cenas
- canais/[canal]/projeto/audio/ → pt.mp3 e en.mp3
- canais/[canal]/projeto/roteiro/ → textos do roteiro
- canais/[canal]/projeto/musica/ → música de fundo (opcional)
- canais/[canal]/videos/ → vídeos gerados

FLUXO BÁSICO:
Cenas → Roteiro → Gerar Vídeo

ATALHOS ÚTEIS:
- Ctrl+3 = Gerar Vídeo | Ctrl+4 = Cenas | Ctrl+5 = Roteiro | Ctrl+S = Salvar
- F5 = recarregar tela | F11 = tela cheia

LICENÇA:
- Requer licença ativa para funcionar
- Dias restantes exibidos no dashboard

COMO RESPONDER:
- Linguagem simples e direta — muitos usuários não são técnicos
- Respostas curtas para perguntas simples, detalhadas quando necessário
- Se não souber algo específico do GeradorBB, diga honestamente
- NUNCA responda sobre assuntos fora do GeradorBB
- Responda sempre em português do Brasil"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _limpar_markdown(texto: str) -> str:
    """Remove marcadores Markdown para exibição limpa no chat."""
    texto = re.sub(r'\*\*(.*?)\*\*', r'\1', texto)   # **negrito**
    texto = re.sub(r'\*(.*?)\*',     r'\1', texto)   # *itálico*
    texto = re.sub(r'`(.*?)`',       r'\1', texto)   # `código`
    texto = re.sub(r'^#{1,6}\s+',    '',    texto, flags=re.MULTILINE)  # # títulos
    return texto.strip()


# ---------------------------------------------------------------------------
# Bolha de mensagem
# ---------------------------------------------------------------------------

class _Bolha(ctk.CTkFrame):
    def __init__(self, master, texto: str, eh_usuario: bool):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="x", padx=6, pady=2)

        lado  = "e" if eh_usuario else "w"
        cor   = ACCENT if eh_usuario else BG3
        wrap  = _PAINEL_W - 40

        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(anchor=lado)

        balao = ctk.CTkFrame(wrapper, fg_color=cor, corner_radius=12,
                             border_width=0 if eh_usuario else 1,
                             border_color=BORDER)
        balao.pack(anchor=lado)

        ctk.CTkLabel(
            balao,
            text=_limpar_markdown(texto),
            font=(FONT_FAMILY, 11),
            text_color=TEXT,
            wraplength=wrap,
            justify="left",
            anchor="w",
        ).pack(padx=10, pady=(6, 2))

        hora = datetime.datetime.now().strftime("%H:%M")
        ctk.CTkLabel(
            balao,
            text=hora,
            font=(FONT_FAMILY, 8),
            text_color=SUBTEXT,
            anchor="e",
        ).pack(padx=8, pady=(0, 4), anchor="e")


# ---------------------------------------------------------------------------
# Painel flutuante
# ---------------------------------------------------------------------------

class PainelAssistente(ctk.CTkFrame):
    """
    Painel de chat que flutua sobre a tela atual (lado direito).
    Uso: painel.toggle(content_frame) para mostrar/esconder.
    """

    def __init__(self, master):
        super().__init__(
            master,
            width=_PAINEL_W,
            height=_PAINEL_H,
            fg_color=BG2,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
        )
        self._historico: list[dict] = []
        self._aguardando = False
        self._visivel    = False
        self._build_ui()

    # ── Construção ──────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Cabeçalho ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG3, corner_radius=10, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="💬  Assistente",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            header, text="✕",
            command=self.fechar,
            width=28, height=28,
            fg_color="transparent", hover_color=BG4,
            text_color=SUBTEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        ).pack(side="right", padx=6)

        ctk.CTkButton(
            header, text="🗑",
            command=self._limpar,
            width=28, height=28,
            fg_color="transparent", hover_color=BG4,
            text_color=SUBTEXT, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_SM),
        ).pack(side="right")

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x")

        # ── Chat scrollável ──────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color=BG3,
            scrollbar_button_hover_color=ACCENT,
        )
        self._scroll.pack(fill="both", expand=True)

        # ── Barra de entrada ─────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x")

        input_bar = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0)
        input_bar.pack(fill="x")

        self._lbl_digitando = ctk.CTkLabel(
            input_bar, text="",
            font=(FONT_FAMILY, 9, "italic"),
            text_color=SUBTEXT,
        )
        self._lbl_digitando.pack(anchor="w", padx=8, pady=(4, 0))

        row = ctk.CTkFrame(input_bar, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(2, 8))
        row.columnconfigure(0, weight=1)

        self._entry = ctk.CTkTextbox(
            row, height=40,
            fg_color=BG3, text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            border_color=BORDER, border_width=1,
            corner_radius=8, wrap="word",
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._entry.bind("<Return>",       self._on_enter)
        self._entry.bind("<Shift-Return>", lambda e: None)

        self._btn_enviar = ctk.CTkButton(
            row, text="➤",
            command=self._enviar,
            width=36, height=40,
            fg_color=ACCENT, hover_color=ACCENT3,
            text_color=TEXT, corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        )
        self._btn_enviar.grid(row=0, column=1)

        # Mensagem de boas-vindas
        self._adicionar_bolha(
            "Olá! 👋 Sou o assistente do GeradorBB.\n"
            "Pergunte qualquer coisa sobre como usar o app!",
            eh_usuario=False,
        )

    # ── Visibilidade ─────────────────────────────────────────────────────────

    def toggle(self, anchor_frame):
        """Mostra ou esconde o painel sobre anchor_frame."""
        if self._visivel:
            self.fechar()
        else:
            self.abrir(anchor_frame)

    def abrir(self, anchor_frame):
        self.place(
            in_=anchor_frame,
            relx=1.0, rely=1.0,
            anchor="se",
            x=-10, y=-10,
        )
        self.lift()
        self._visivel = True
        self._entry.focus_set()

    def fechar(self):
        self.place_forget()
        self._visivel = False

    # ── Mensagens ────────────────────────────────────────────────────────────

    def _adicionar_bolha(self, texto: str, eh_usuario: bool):
        _Bolha(self._scroll, texto, eh_usuario)
        self.after(80, self._scroll_bottom)

    def _scroll_bottom(self):
        try:
            canvas = getattr(self._scroll, "_parent_canvas", None)
            if canvas:
                canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _limpar(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._historico.clear()
        self._adicionar_bolha("Conversa reiniciada. Como posso ajudar?", eh_usuario=False)

    # ── Envio ────────────────────────────────────────────────────────────────

    def _on_enter(self, event):
        if not event.state & 0x1:
            self._enviar()
            return "break"

    def _enviar(self):
        if self._aguardando:
            return
        texto = self._entry.get("1.0", "end").strip()
        if not texto:
            return

        self._entry.delete("1.0", "end")
        self._adicionar_bolha(texto, eh_usuario=True)
        self._aguardando = True
        self._btn_enviar.configure(state="disabled", text="...")
        self._lbl_digitando.configure(text="digitando...")

        def _run():
            try:
                resposta = self._chamar_gemini(texto)
            except Exception as err:
                resposta = f"Erro ao processar sua pergunta.\nDetalhe: {err}"
            finally:
                def _ui():
                    self._adicionar_bolha(resposta, eh_usuario=False)
                    self._aguardando = False
                    self._btn_enviar.configure(state="normal", text="➤")
                    self._lbl_digitando.configure(text="")
                self.after(0, _ui)

        threading.Thread(target=_run, daemon=True).start()

    # ── Chamada Gemini ────────────────────────────────────────────────────────

    def _chamar_gemini(self, pergunta: str) -> str:
        try:
            from google import genai
            from google.genai import types as _t

            client   = genai.Client(api_key=_CHAVE_ASSISTENTE)
            contents = []

            if not self._historico:
                contents.append(_t.Content(role="user",  parts=[_t.Part(text=_PROMPT_SISTEMA)]))
                contents.append(_t.Content(role="model", parts=[_t.Part(text="Entendido! Estou pronto para ajudar.")]))

            for msg in self._historico[-20:]:
                txt = msg["parts"][0] if isinstance(msg["parts"][0], str) else str(msg["parts"][0])
                contents.append(_t.Content(role=msg["role"], parts=[_t.Part(text=txt)]))

            contents.append(_t.Content(role="user", parts=[_t.Part(text=pergunta)]))

            r        = client.models.generate_content(model=_MODELO_ASSISTENTE, contents=contents)
            resposta = r.text.strip()

            self._historico.append({"role": "user",  "parts": [pergunta]})
            self._historico.append({"role": "model", "parts": [resposta]})

            return resposta

        except ImportError:
            return "Módulo de IA não encontrado. Reinstale o GeradorBB."
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg:
                return "Limite de uso da IA atingido. Aguarde alguns minutos."
            if "503" in msg or "unavailable" in msg or "high demand" in msg:
                return "Serviço sobrecarregado. Tente novamente em alguns segundos."
            if "401" in msg or "api_key" in msg or "invalid" in msg:
                return "Erro de autenticação. Entre em contato com o suporte."
            raise


# ---------------------------------------------------------------------------
# Compatibilidade — TelaAjuda agora é apenas um stub (não usada como tela)
# ---------------------------------------------------------------------------

class TelaAjuda(ctk.CTkFrame):
    """Mantido por compatibilidade. Uso real: PainelAssistente."""
    def __init__(self, master, janela=None):
        super().__init__(master, fg_color=BG, corner_radius=0)

    def ao_exibir(self):
        pass

    def atualizar_projeto(self, projeto_dir: Path):
        pass
