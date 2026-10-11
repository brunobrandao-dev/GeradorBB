# gui_theme.py — Design system centralizado do GeradorBB
# Todas as telas devem importar daqui — nunca cores/tamanhos hardcoded.

# ── Cores de fundo ─────────────────────────────────────────────────────────────
BG      = "#0b0b14"   # fundo principal
BG2     = "#13131f"   # sidebar / cards
BG3     = "#1c1c2e"   # hover / destaque suave
BG4     = "#090910"   # status bar / log
BG5     = "#1a1a30"   # cards secundários

# ── Cores de acento ────────────────────────────────────────────────────────────
ACCENT  = "#e94560"   # vermelho/rosa principal
ACCENT2 = "#ff6b9d"   # rosa claro
ACCENT3 = "#c4293e"   # hover dos botões accent

# ── Cores semânticas ──────────────────────────────────────────────────────────
SUCCESS             = "#00d084"
SUCCESS_HOVER       = "#00a86b"   # hover de botão de sucesso
SUCCESS_TEXT        = "#000000"   # texto sobre fundo SUCCESS (contraste)
WARNING             = "#ffc107"
DANGER              = "#ff4757"
DANGER_HOVER        = "#cc2233"   # hover de botão de perigo
DANGER_MUTED        = "#6b1c1c"   # botão de perigo com fundo discreto (ícone de remover)
INFO                = "#4fc3f7"
ACCENT_GHOST_HOVER  = "#1a0508"   # hover de botão transparente com conteúdo ACCENT

# ── Textos e bordas ───────────────────────────────────────────────────────────
TEXT    = "#f0f0ff"
SUBTEXT = "#8888a8"
BORDER  = "#22223a"
BORDER2 = "#2e2e4e"

# ── Cores de elemento no preview do canvas ───────────────────────────────────
# (usadas nos indicadores da legenda e no desenho do canvas de preview)
COLOR_LOGO       = "#e94560"   # = ACCENT
COLOR_LEGENDA    = "#ffdd00"   # amarelo
COLOR_PERSONAGEM = "#22cc55"   # verde
COLOR_BORDA      = "#50a0ff"   # azul

# ── Fundo especial de linhas ───────────────────────────────────────────────────
BG_ROW_SUCCESS   = "#0b1f12"   # linha da fila com item em execução/sucesso

# ── Banners contextuais (aviso / sucesso / info / erro) ──────────────────────
# Aviso (amarelo escuro — chave não configurada, ação necessária)
BG_AVISO           = "#1a1600"
BG_AVISO_BORDER    = "#4a3d00"
BG_AVISO_BTN       = "#302800"
BG_AVISO_BTN_HOVER = "#403500"
TEXT_AVISO         = "#ffc107"   # = WARNING

# Sucesso/boas-vindas (verde escuro — primeiro acesso, parabéns)
BG_SUCESSO         = "#0a1a0a"
BG_SUCESSO_BORDER  = "#1a4a1a"
BG_SUCESSO_ACTIVE  = "#0a2a1a"   # banner de sucesso com login confirmado
BG_SUCESSO_ACTIVE_BORDER = "#1a5a35"
TEXT_SUCESSO_LIGHT = "#90ee90"   # texto secundário verde claro

# Info (azul escuro — dicas, informações)
BG_INFO            = "#0a1020"
BG_INFO_BORDER     = "#1a3060"

# Erro (vermelho escuro — mensagens de erro no login)
BG_ERRO            = "#2a0a10"
BG_ERRO_BORDER     = "#5a1a25"

# ── Fontes ────────────────────────────────────────────────────────────────────
FONT_FAMILY   = "Segoe UI"
FONT_TITLE    = ("Segoe UI", 22, "bold")
FONT_H2       = ("Segoe UI", 15, "bold")
FONT_BODY     = ("Segoe UI", 12)
FONT_SMALL    = ("Segoe UI", 10)
FONT_MONO     = ("Consolas", 11)

FONT_SIZE_SM  = 11
FONT_SIZE_MD  = 13
FONT_SIZE_LG  = 16
FONT_SIZE_XL  = 22
FONT_SIZE_XXL = 32

# ── Layout ───────────────────────────────────────────────────────────────────
SIDEBAR_W  = 255
CORNER_R   = 10
PAD        = 16

# Alturas padrão de componentes (usar em todas as telas para consistência)
BTN_H      = 38    # altura padrão de botão
BTN_H_LG   = 44    # botão de ação principal
BTN_H_SM   = 30    # botão pequeno / ícone
ENTRY_H    = 38    # altura de campo de texto
TABBAR_H   = 46    # barra de abas
STATUSBAR_H = 28   # barra de status inferior

# Padding interno de cards
CARD_PAD_X = 16    # horizontal
CARD_PAD_Y = 14    # vertical (topo/fundo)
