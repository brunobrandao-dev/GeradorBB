"""
Rankadorama — Gerador automático de vídeos Top 10
==================================================

Como usar:
  1. Coloque as imagens em  cenas/
        abertura_pt.png  abertura_en.png  +  1.png … 10.png  +  fechamento_pt.png  fechamento_en.png
  2. Coloque os roteiros em  roteiro/
        roteiro_pt.txt   roteiro_en.txt
  3. Coloque os áudios em  audio/   (ex.: ElevenLabs_pt.mp3, ElevenLabs_en.mp3)
  4. (Opcional) Música de fundo em  musica/
  5. Rode:  python rankadorama.py   ou dê dois cliques em  INICIAR.bat

Os vídeos aparecem em  videos/AAAA-MM-DD/portugues/  e  videos/AAAA-MM-DD/ingles/
"""

# ── Força UTF-8 + line buffering no stdout/stderr ────────────────────────────
# line_buffering=True faz flush em cada \n, garantindo que o GUI receba logs
# em tempo real quando stdout é um pipe (subprocess.PIPE no GeradorBB.exe).
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    try:
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Redireciona caches para pasta persistente ─────────────────────────────────
# Em modo frozen (engine.exe), __file__ aponta para _MEIPASS (pasta temporária
# que é deletada ao fechar). Usamos GERADORBB_DATA_DIR (env enviada pelo GUI)
# ou derivamos de Documents\GeradorBB\ para manter o cache entre sessões.
import os as _os
from pathlib import Path as _P

_data_dir_env = _os.environ.get("GERADORBB_DATA_DIR")
if _data_dir_env:
    _CACHE = _P(_data_dir_env) / "cache"
elif getattr(_sys, "frozen", False):
    # Frozen sem env var: usa Documents\GeradorBB\cache
    try:
        import ctypes as _ct, ctypes.wintypes as _wt
        _buf = _ct.create_unicode_buffer(_wt.MAX_PATH)
        _ct.windll.shell32.SHGetFolderPathW(0, 0x0005, 0, 0, _buf)
        _CACHE = _P(_buf.value) / "GeradorBB" / "cache"
    except Exception:
        _CACHE = _P(_os.environ.get("USERPROFILE", "")) / "Documents" / "GeradorBB" / "cache"
else:
    # Desenvolvimento: cache/ ao lado de engine.py
    _CACHE = _P(__file__).resolve().parent / "cache"

_CACHE.mkdir(parents=True, exist_ok=True)
_sys.pycache_prefix  = str(_CACHE / "pycache")
_os.environ.setdefault("TORCH_HOME", str(_CACHE / "torch"))
_os.environ.setdefault("HF_HOME",    str(_CACHE / "torch"))
# ─────────────────────────────────────────────────────────────────────────────

import datetime
import difflib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

# Evita janela de terminal piscando no Windows ao chamar FFmpeg/ffprobe
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
import unicodedata
from pathlib import Path

# ======================== CONFIGURAÇÕES ========================
# Mude aqui o que quiser, sem mexer no resto do código.

LARGURA, ALTURA = 1080, 1920        # tamanho do vídeo (vertical)
FPS = 30

MODELO_WHISPER = "small"            # "base" (rápido) | "small" (bom) | "medium" (mais preciso, mais lento)

FUNDO = "preto"                     # "preto" ou "desfocado"

MARCA_DAGUA = "@RankaDorama"        # fallback de texto (usado só se logo.png não existir)
TAMANHO_MARCA = 46
MARCA_X, MARCA_Y = 20, 245          # posição do texto fallback (px)

LARGURA_LOGO = 340         # largura do logo em px no vídeo (altura proporcional)
LOGO_X = 20                # posição X do logo (px, canto superior esquerdo)
LOGO_Y = 248               # posição Y do logo (px, canto superior esquerdo)

BORDA_ARQUIVO = ""         # nome do arquivo PNG em projeto/bordas/ (vazio = sem borda)
BORDA_ATIVA   = False      # se True, aplica borda sobre o vídeo final

PALAVRAS_POR_LEGENDA = 1            # quantas palavras aparecem por vez (descrição)
DURACAO_MINIMA_LEGENDA = 0.30       # segundos mínimos por bloco (junta palavras curtas)
FONTE = "Arial"
TAMANHO_FONTE = 64
NEGRITO = 0                         # 1 = negrito, 0 = normal
COR_TEXTO = "&H0000FFFF"            # amarelo (formato ASS: &HAABBGGRR)
COR_CONTORNO = "&H00000000"         # preto
CONTORNO = 2
SOMBRA = 2
POSICAO_LEGENDA = 300               # distância da parte de baixo da tela (px)

ZOOM_MAXIMO = 0.0                   # 0 = imagens paradas; ex: 0.06 = 6% de zoom lento
ZOOM_ABERTURA_FECHAMENTO = False    # True = aplica zoom também na abertura e fechamento
VOLUME_MUSICA = 0.10                # 0.0 a 1.0 (só se houver música em musica/)

LAYOUT = "padrao"                   # "padrao" | "tela_cheia" | "card" | "numero" | "dividido"
COR_FUNDO_CARD = "1a1a2e"          # hex sem # — fundo dos layouts "card" e "dividido"
DURACAO_FADE = 0.0                  # segundos de fade entre imagens (0 = desativado, ex: 0.2)

FFMPEG_PRESET_FINAL = "medium"      # "ultrafast"(rápido/grande) | "fast" | "medium" | "slow"(lento/pequeno)
FFMPEG_CRF_FINAL = 20               # qualidade final: 18 (alta) → 28 (baixa); padrão 20

PREVIEW_DURACAO = 40                # segundos do preview rápido (opção 4 do menu)

TEMA_MENU = "padrao"               # cor do menu: "padrao"|"azul"|"verde"|"rosa"|"roxo"|"amarelo"
COR_LEGENDA = "amarelo"            # cor da legenda: "amarelo"|"branco"|"ciano"|"verde"|"rosa"|"laranja"

MODO_TEMA  = "padrao"   # "padrao" (sempre _1) | "aleatorio" (sorteia) | "selecionar" (TEMA_ATIVO)
TEMA_ATIVO = 1          # número do tema quando MODO_TEMA = "selecionar"
LOGO_ATIVA = 1          # número do logo quando MODO_TEMA = "selecionar"

GERAR_INSTA       = True           # gera versão 4:5 para Instagram junto com o vídeo principal
GERAR_INSTA_LINGUAS = ["pt"]      # idiomas que geram Instagram: ["pt"] só PT | ["pt","en"] os dois
GERAR_SRT    = False              # salva arquivo .srt de legendas junto com o vídeo
BOUNCE_LEGENDA = True             # animação de pop/bounce ao aparecer cada palavra da legenda
SALVAR_FRAMES = False             # True = salva frame PNG de cada item em videos/frames/
ALTURA_INSTA = 1350               # altura do vídeo Instagram 4:5 (largura permanece LARGURA = 1080)
# Posição da marca/logo na versão Instagram — calculada em % para funcionar em qualquer resolução
MARCA_INSTA_X_PCT = 0.03          # 3% da largura  → ex.: 1080×0.03 = 32px
MARCA_INSTA_Y_PCT = 0.03          # 3% da altura   → ex.: 1350×0.03 = 41px

AVISO_LIMITE_SEGUNDOS = 180         # avisa se passar de 3 minutos

MUSICA_MODO  = "aleatorio"          # "aleatorio" | "selecionar"
MUSICA_ATIVA = ""                   # nome do arquivo quando MUSICA_MODO = "selecionar"

# ===============================================================

_TEMAS_MENU = {
    "padrao":  "\033[1;97m",
    "azul":    "\033[1;96m",
    "verde":   "\033[1;92m",
    "rosa":    "\033[1;95m",
    "roxo":    "\033[1;94m",
    "amarelo": "\033[1;93m",
}
def _r():
    """Retorna o código de reset ANSI (vazio se ANSI não disponível)."""
    return "\033[0m" if _ansi_ok else ""


# ── Helpers de cor ──────────────────────────────────────────────────────────
def _verde(t):   return f"\033[92m{t}\033[0m" if _ansi_ok else t
def _vermelho(t): return f"\033[91m{t}\033[0m" if _ansi_ok else t
def _cinza(t):   return f"\033[90m{t}\033[0m" if _ansi_ok else t
def _negrito(t): return f"\033[1m{t}\033[0m" if _ansi_ok else t

import threading as _threading


class _Spinner:
    """Spinner animado para operações longas."""
    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, msg):
        self.msg = msg
        self._stop = _threading.Event()
        self._t = _threading.Thread(target=self._run, daemon=True)

    def _run(self):
        i = 0
        while not self._stop.is_set():
            f = self._FRAMES[i % len(self._FRAMES)]
            print(f"\r  {f}  {self.msg}", end="", flush=True)
            i += 1
            time.sleep(0.1)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join()
        print(f"\r     {self.msg}  ", flush=True)


def _ultimo_historico():
    """Retorna o último registro de historico.json ou None."""
    arq = PASTA_SAIDA / "historico.json"
    try:
        h = json.loads(arq.read_text(encoding="utf-8"))
        return h[-1] if h else None
    except Exception:
        return None


_CORES_LEGENDA = {
    "amarelo": "&H0000FFFF",
    "branco":  "&H00FFFFFF",
    "ciano":   "&H00FFFF00",
    "verde":   "&H0000FF00",
    "rosa":    "&H00FF69FF",
    "laranja": "&H000080FF",
}


_ansi_ok = False

def _habilitar_ansi():
    global _ansi_ok
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            k.GetConsoleMode(h, ctypes.byref(mode))
            k.SetConsoleMode(h, mode.value | 0x0004)
            _ansi_ok = True
        except Exception:
            _ansi_ok = False
    else:
        _ansi_ok = True


def _c():
    """Retorna o código ANSI de cor para o tema atual."""
    if not _ansi_ok:
        return ""
    return _TEMAS_MENU.get(TEMA_MENU, _TEMAS_MENU["padrao"])


LAYOUTS = {
    "padrao":     "Padrão      — imagem centralizada, fundo preto/desfocado",
    "tela_cheia": "Tela Cheia  — imagem preenche toda a tela",
    "card":       "Card        — imagem com moldura e fundo colorido",
    "numero":     "Número      — padrão + nº do item em destaque atrás da imagem",
    "dividido":   "Dividido    — imagem no topo, faixa colorida embaixo",
}

PASTA = Path(__file__).resolve().parent
PASTA_PROJETO        = PASTA / "projeto"
PASTA_IMAGENS        = PASTA_PROJETO / "cenas"
PASTA_ROTEIRO        = PASTA_PROJETO / "roteiro"
PASTA_AUDIO          = PASTA_PROJETO / "audio"
PASTA_MUSICA         = PASTA_PROJETO / "musica"
PASTA_DORAMAS        = PASTA_PROJETO / "doramas"
PASTA_TEMAS          = PASTA_PROJETO / "temas"
PASTA_LOGOS          = PASTA_PROJETO / "logos"
PASTA_BORDAS         = PASTA_PROJETO / "bordas"
PASTA_SAIDA          = PASTA / "videos"

EXT_IMAGEM = [".png", ".jpg", ".jpeg", ".webp"]
EXT_VIDEO = [".mp4", ".mov", ".webm", ".mkv"]
EXT_AUDIO = [".mp3", ".wav", ".m4a", ".ogg", ".m4b"]

NUMEROS = {
    "pt": {"dez": "10", "nove": "9", "oito": "8", "sete": "7", "seis": "6", "cinco": "5",
           "quatro": "4", "tres": "3", "dois": "2", "duas": "2", "um": "1", "uma": "1"},
    "en": {"ten": "10", "nine": "9", "eight": "8", "seven": "7", "six": "6", "five": "5",
           "four": "4", "three": "3", "two": "2", "one": "1"},
}


# ------------------------- utilidades -------------------------

_CONFIG_FILE = PASTA / "config.json"
_CONFIG_VARS = ["FUNDO", "PALAVRAS_POR_LEGENDA", "VOLUME_MUSICA", "MODELO_WHISPER",
                "ZOOM_MAXIMO", "ZOOM_ABERTURA_FECHAMENTO", "POSICAO_LEGENDA",
                "LAYOUT", "COR_FUNDO_CARD", "DURACAO_FADE",
                "FFMPEG_PRESET_FINAL", "FFMPEG_CRF_FINAL", "PREVIEW_DURACAO",
                "TEMA_MENU", "COR_LEGENDA",
                "MODO_TEMA", "TEMA_ATIVO", "LOGO_ATIVA",
                "GERAR_INSTA", "GERAR_INSTA_LINGUAS", "GERAR_SRT", "BOUNCE_LEGENDA", "SALVAR_FRAMES",
                "LOGO_X", "LOGO_Y", "LARGURA_LOGO",
                "MUSICA_MODO", "MUSICA_ATIVA", "REGIAO_OCR"]


def salvar_config():
    import engine as _gv
    dados = {v: getattr(_gv, v) for v in _CONFIG_VARS}
    _CONFIG_FILE.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def carregar_config():
    if not _CONFIG_FILE.exists():
        return
    import engine as _gv
    try:
        dados = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        for k, v in dados.items():
            if k in _CONFIG_VARS and hasattr(_gv, k):
                setattr(_gv, k, v)
    except Exception as e:
        print(f"  ⚠️  config.json não pôde ser lido ({e}) — usando configurações padrão.")


def limpar():
    os.system("cls" if os.name == "nt" else "clear")


def fmt_duracao(s):
    m, seg = divmod(int(s), 60)
    return f"{m}m {seg:02d}s" if m else f"{seg}s"


def secao(titulo):
    cor = _c()
    print(f"\n{cor}{'─' * 42}{_r()}")
    print(f"{cor}  {titulo}{_r()}")
    print(f"{cor}{'─' * 42}{_r()}")


def _input_gui(prompt: str, default: str = "s") -> str:
    """
    Substitui input() quando chamado pelo GUI (sem terminal interativo).
    Retorna `default` automaticamente se stdin não for um tty.
    """
    try:
        if not sys.stdin or not sys.stdin.isatty():
            print(f"{prompt}[auto: {default}]")
            return default
        return input(prompt).strip().lower()
    except (EOFError, OSError):
        print(f"{prompt}[auto: {default}]")
        return default


def erro(msg):
    print(f"\n❌ {msg}\n")
    if sys.stdin and sys.stdin.isatty():
        _input_gui("Aperte Enter para fechar...")
    sys.exit(1)


def ler_texto(caminho):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return caminho.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return caminho.read_text(encoding="utf-8", errors="ignore")


def achar_arquivo(pasta, nome, extensoes):
    for ext in extensoes:
        for variante in (ext, ext.upper()):
            p = pasta / f"{nome}{variante}"
            if p.exists():
                return p
    return None


# ------------------------- temas e logos -------------------------

def _listar_temas():
    """Retorna lista de números de temas disponíveis em temas/ (ex.: [1, 2, 3])."""
    if not PASTA_TEMAS.exists():
        return []
    nums = set()
    for p in PASTA_TEMAS.iterdir():
        m = re.search(r'_(\d+)\.[^.]+$', p.name)
        if m:
            nums.add(int(m.group(1)))
    return sorted(nums)


def _listar_logos():
    """Retorna lista de números de logos disponíveis em logos/."""
    if not PASTA_LOGOS.exists():
        return []
    nums = set()
    for p in PASTA_LOGOS.iterdir():
        if p.suffix.lower() in EXT_IMAGEM:
            m = re.search(r'_(\d+)$', p.stem)
            if m:
                nums.add(int(m.group(1)))
    return sorted(nums)


def _resolver_tema():
    """Retorna o número do tema a usar (ou None se temas/ não existir/estiver vazio)."""
    import engine as _gv
    temas = _listar_temas()
    if not temas:
        return None
    if _gv.MODO_TEMA == "aleatorio":
        return random.choice(temas)
    if _gv.MODO_TEMA == "selecionar":
        if _gv.TEMA_ATIVO in temas:
            return _gv.TEMA_ATIVO
        print(f"  ⚠️  Tema {_gv.TEMA_ATIVO} não existe em temas/ — usando tema {temas[0]}.")
    return temas[0]


def _resolver_logo():
    """Retorna o número do logo a usar (ou None se logos/ não existir/estiver vazio)."""
    import engine as _gv
    logos = _listar_logos()
    if not logos:
        return None
    if _gv.MODO_TEMA == "aleatorio":
        return random.choice(logos)
    if _gv.MODO_TEMA == "selecionar":
        if _gv.LOGO_ATIVA in logos:
            return _gv.LOGO_ATIVA
        print(f"  ⚠️  Logo {_gv.LOGO_ATIVA} não existe em logos/ — usando logo {logos[0]}.")
    return logos[0]


def preparar_logo(n_logo=None):
    """Recorta bordas transparentes do logo e redimensiona.
    Procura primeiro em logos/logo_N.png; se não existir, usa cenas/logo.png.
    Retorna (logo_path, None) ou (None, None) se não encontrar nenhum logo."""
    n = n_logo if n_logo is not None else _resolver_logo()
    if n is not None:
        logo_src = achar_arquivo(PASTA_LOGOS, f"logo_{n}", EXT_IMAGEM)
    else:
        logo_src = None
    if not logo_src:
        logo_src = achar_arquivo(PASTA_IMAGENS, "logo", EXT_IMAGEM)
    if not logo_src:
        return None, None
    try:
        from PIL import Image
    except ImportError:
        return None, None
    with Image.open(logo_src) as img:
        # Validação: avisa se logo não tem canal alfa (transparência)
        if img.mode not in ("RGBA", "LA") and "transparency" not in img.info:
            print(f"  ⚠️  Logo '{logo_src.name}' não tem fundo transparente (modo: {img.mode}).")
            print(f"     Use um PNG com fundo transparente para melhor resultado.")
        img = img.convert("RGBA")
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        w, h = img.size
        new_h = max(1, round(h * LARGURA_LOGO / w))
        img = img.resize((LARGURA_LOGO, new_h), Image.LANCZOS)
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="rnk_logo_")
        os.close(fd)
        img.save(tmp_path, "PNG")
    return Path(tmp_path), None


def achar_roteiro(lingua):
    """Retorna (arq_eleven, arq_legendas).
    Procura elevenlabs_{lingua}.txt; cai em roteiro_{lingua}.txt como legado.
    arq_legendas = legendas_{lingua}.txt se existir, senão igual a arq_eleven."""
    eleven = PASTA_ROTEIRO / f"elevenlabs_{lingua}.txt"
    if not eleven.exists():
        eleven = PASTA_ROTEIRO / f"roteiro_{lingua}.txt"
    if not eleven.exists():
        return None, None
    leg = PASTA_ROTEIRO / f"legendas_{lingua}.txt"
    return eleven, (leg if leg.exists() else eleven)


def achar_audio(pasta, lingua):
    for p in sorted(pasta.glob("*")):
        if p.suffix.lower() in EXT_AUDIO:
            if re.search(r'(^|[_\-\.])' + lingua + r'($|[_\-\.])', p.stem.lower()):
                return p
    return None


def rodar(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore",
                       creationflags=_NO_WINDOW)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        erro("O FFmpeg deu erro (detalhes acima).")
    return r


def duracao_audio(caminho):
    r = rodar(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(caminho)])
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        erro(f"Não consegui ler a duração do áudio '{caminho.name}': {e}")


def validar_audio(caminho):
    """Verifica se o arquivo tem stream de áudio válido."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(caminho)],
        capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    if "audio" not in r.stdout:
        erro(f"'{caminho.name}' não contém áudio válido ou está corrompido.\n"
             f"   Baixe o arquivo novamente do ElevenLabs.")


def normalizar(palavra, lingua):
    p = unicodedata.normalize("NFKD", palavra.lower())
    p = "".join(c for c in p if not unicodedata.combining(c))
    p = re.sub(r"[^a-z0-9]", "", p)
    return NUMEROS.get(lingua, {}).get(p, p)


def eh_palavra(token):
    return re.search(r"\w", token) is not None


# ------------------------- roteiro -------------------------

def limpar_roteiro(texto):
    """Fica só com o texto narrado (ignora títulos, descrições e avisos)."""
    linhas = []
    for linha in texto.splitlines():
        l = linha.strip()
        if not l:
            continue
        if re.match(r"descri[cç][aã]o\s*:?$|description\s*:?$", l, re.I):
            break
        if l.startswith(("**", "---", "⚠", "🇧🇷", "🇺🇸", "🎙", "📝", "#")):
            continue
        linhas.append(l)
    return linhas


def tokenizar(linhas):
    """Retorna lista de tokens e o índice do token onde cada item (10..1) começa."""
    tokens, linha_de = [], []
    inicio_item = {}
    ultima_linha_item = None
    for i, linha in enumerate(linhas):
        m = re.match(r"^(\d{1,2})\s*[–—-]", linha)
        if m:
            inicio_item[int(m.group(1))] = len(tokens)
            ultima_linha_item = i
        elif ultima_linha_item is not None and "fim" not in inicio_item:
            inicio_item["fim"] = len(tokens)   # começo do encerramento
        for t in linha.split():
            tokens.append(t)
            linha_de.append(i)
    return tokens, linha_de, inicio_item


# ------------------------- tempos (Whisper) -------------------------

_whisper_cache = {}         # modelo fica em memória entre PT e EN
_ultimo_alinhamento_pct = 0 # percentual do último alinhamento (para histórico)
_ultimo_device = "cpu"      # device usado pelo último modelo Whisper carregado

def transcrever(audio, lingua):
    try:
        from faster_whisper import WhisperModel
        import numpy as np
    except ImportError:
        erro("Falta instalar o faster-whisper. Rode: pip install -r requirements.txt")
    if MODELO_WHISPER not in _whisper_cache:
        # Adiciona DLLs do CUDA (instaladas via pip) ao PATH do Windows
        try:
            import site
            from pathlib import Path as _P
            for _sp in site.getsitepackages():
                _nvidia = _P(_sp) / "nvidia"
                if _nvidia.exists():
                    for _pkg in _nvidia.iterdir():
                        _bin = _pkg / "bin"
                        if _bin.exists() and str(_bin) not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = str(_bin) + os.pathsep + os.environ["PATH"]
                            if os.name == "nt":
                                os.add_dll_directory(str(_bin))
        except Exception:
            pass

        # Detecta GPU via CTranslate2 (motor interno do faster-whisper)
        _usar_gpu = False
        device, compute_type = "cpu", "int8"
        try:
            import ctranslate2
            tipos_cuda = ctranslate2.get_supported_compute_types("cuda")
            if tipos_cuda:
                _usar_gpu = True
                device       = "cuda"
                compute_type = "float16" if "float16" in tipos_cuda else "int8"
        except Exception:
            pass
        # Fallback: tenta torch se ctranslate2 não informou
        if not _usar_gpu:
            try:
                import torch
                if torch.cuda.is_available():
                    _usar_gpu = True
                    device, compute_type = "cuda", "float16"
            except ImportError:
                pass

        gpu_info = "CPU"
        if _usar_gpu:
            try:
                import torch
                gpu_info = f"GPU ({torch.cuda.get_device_name(0)})"
            except Exception:
                gpu_info = "GPU"
        print(f"  🎧 Carregando modelo Whisper ({MODELO_WHISPER}) em {gpu_info} — aguarde...")
        try:
            _whisper_cache[MODELO_WHISPER] = WhisperModel(MODELO_WHISPER, device=device, compute_type=compute_type)
        except Exception as e:
            if _usar_gpu:
                print(f"     ⚠️  GPU falhou ({e}) — usando CPU")
                _whisper_cache[MODELO_WHISPER] = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
                gpu_info = "CPU"
                device = "cpu"
        print(f"     Modelo pronto.")
        global _ultimo_device
        _ultimo_device = device
    else:
        print(f"  🎧 Transcrevendo o áudio  (modelo: {MODELO_WHISPER} — já carregado)")
    modelo = _whisper_cache[MODELO_WHISPER]
    print(f"     Analisando áudio — aguarde...")
    # decodifica via FFmpeg para evitar incompatibilidade com o av
    r = subprocess.run(
        ["ffmpeg", "-i", str(audio), "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"],
        capture_output=True, creationflags=_NO_WINDOW)
    amostras = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    dur_est = len(amostras) / 16000
    _dev_atual = _ultimo_device if MODELO_WHISPER in _whisper_cache else "cpu"
    gpu_or_cpu = "GPU" if _dev_atual == "cuda" else "CPU"
    velocidade = 10 if gpu_or_cpu == "GPU" else 3
    est_s = max(5, round(dur_est / velocidade))
    print(f"     {dur_est:.0f}s de áudio — est. {est_s}s em {gpu_or_cpu}...")

    def _transcrever(mdl):
        segs, _ = mdl.transcribe(amostras, language=lingua, word_timestamps=True)
        result = []
        for seg in segs:
            for w in seg.words:
                result.append((w.word.strip(), w.start, w.end))
        return result

    try:
        return _transcrever(modelo)
    except RuntimeError as e:
        print(f"\n     ⚠️  GPU falhou ({e})")
        print(f"     Continuando em CPU...")
        _whisper_cache[MODELO_WHISPER] = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
        return _transcrever(_whisper_cache[MODELO_WHISPER])


def alinhar(tokens, palavras_whisper, lingua, duracao):
    """Dá um tempo (início, fim) para cada token do SEU roteiro."""
    a = [normalizar(t, lingua) for t in tokens]
    b = [normalizar(w[0], lingua) for w in palavras_whisper]
    tempos = [None] * len(tokens)

    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for bloco in sm.get_matching_blocks():
        for k in range(bloco.size):
            i, j = bloco.a + k, bloco.b + k
            if a[i]:
                tempos[i] = (palavras_whisper[j][1], palavras_whisper[j][2])

    acertos = sum(1 for t in tempos if t)
    pct = int(acertos / len(tokens) * 100) if tokens else 0
    global _ultimo_alinhamento_pct
    _ultimo_alinhamento_pct = pct
    icone = "✅" if pct >= 60 else "⚠️ "
    print(f"  {icone} {acertos} / {len(tokens)} palavras encontradas no áudio  ({pct}%)")
    if pct < 60:
        print(f"     Alinhamento fraco — as legendas podem sair fora de sincronia.")
        resp = _input_gui("     Continuar mesmo assim? [S/N]: ", "s")
        if resp != "s":
            erro("Geração cancelada. Verifique se o áudio e o roteiro são do mesmo texto.")

    # preenche as palavras não encontradas dividindo o tempo entre as vizinhas
    i = 0
    while i < len(tokens):
        if tempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(tokens) and tempos[j] is None:
            j += 1
        ini = tempos[i - 1][1] if i > 0 else 0.0
        fim = tempos[j][0] if j < len(tokens) else (palavras_whisper[-1][2] if palavras_whisper else duracao)
        passo = max(fim - ini, 0.01) / (j - i)
        for k in range(i, j):
            tempos[k] = (ini + passo * (k - i), ini + passo * (k - i + 1))
        i = j
    return tempos


# ------------------------- legendas -------------------------

def tokens_legenda(tokens_eleven, linhas_legenda, lingua):
    """Pega o texto da legenda no lugar de cada palavra do ElevenLabs."""
    tokens_leg, linha_leg, _ = tokenizar(linhas_legenda)
    if len(tokens_leg) == len(tokens_eleven):
        return tokens_leg, linha_leg
    print("   ⚠️ Os dois roteiros não têm o mesmo número de palavras. Vou alinhar pelo conteúdo.")
    return tokens_leg, linha_leg


def mapear_tempos_legenda(tokens_eleven, tempos, tokens_leg, lingua):
    if len(tokens_leg) == len(tokens_eleven):
        return list(tempos)
    a = [normalizar(t, lingua) for t in tokens_eleven]
    b = [normalizar(t, lingua) for t in tokens_leg]
    novos = [None] * len(tokens_leg)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                novos[j1 + k] = tempos[i1 + k]
        elif j2 > j1:
            ini = tempos[i1][0] if i1 < len(tempos) else tempos[-1][1]
            fim = tempos[i2 - 1][1] if i2 > i1 else ini + 0.3 * (j2 - j1)
            passo = max(fim - ini, 0.01) / (j2 - j1)
            for k in range(j2 - j1):
                novos[j1 + k] = (ini + passo * k, ini + passo * (k + 1))
    return novos


def montar_blocos(tokens, linhas_de, tempos, inicio_item=None):
    # Marca tokens que fazem parte do título de cada item (ex.: "7 – Loucos Um Pelo Outro:")
    no_titulo = set()
    fim_titulo = set()
    if inicio_item:
        for n, pos in inicio_item.items():
            if not isinstance(n, int):
                continue
            for i in range(pos, min(pos + 30, len(tokens))):
                no_titulo.add(i)
                if tokens[i].endswith(':'):
                    fim_titulo.add(i)
                    break

    blocos, atual = [], []

    def fechar():
        if atual:
            blocos.append(atual.copy())
            atual.clear()

    for i, t in enumerate(tokens):
        if atual and linhas_de[i] != linhas_de[atual[-1]]:
            fechar()
        atual.append(i)
        n_palavras = sum(1 for k in atual if eh_palavra(tokens[k]))
        if i in fim_titulo:
            fechar()
        elif i not in no_titulo:
            if (re.search(r"[.!?:,;]$", t) or n_palavras >= PALAVRAS_POR_LEGENDA) and eh_palavra(t):
                fechar()
    fechar()

    resultado = []
    for idx, bloco in enumerate(blocos):
        texto = " ".join(tokens[k] for k in bloco)
        if bloco[-1] in fim_titulo:
            texto = texto.rstrip(': ')
        ini, fim = tempos[bloco[0]][0], tempos[bloco[-1]][1]
        resultado.append([ini, fim, texto])
    for k in range(len(resultado) - 1):
        prox = resultado[k + 1][0]
        if prox - resultado[k][1] < 0.5:
            resultado[k][1] = prox

    # Junta blocos mais curtos que o mínimo com o seguinte
    final = []
    i = 0
    while i < len(resultado):
        ini, fim, texto = resultado[i]
        while (fim - ini) < DURACAO_MINIMA_LEGENDA and i + 1 < len(resultado):
            i += 1
            fim = resultado[i][1]
            texto = texto + " " + resultado[i][2]
        final.append([ini, fim, texto])
        i += 1
    return final


def fmt_ass(s):
    s = max(s, 0)
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def fmt_srt(s):
    s = max(s, 0)
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def salvar_ass(blocos, caminho, duracao_total, com_marca=True):
    cor = _CORES_LEGENDA.get(COR_LEGENDA, COR_TEXTO)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {LARGURA}
PlayResY: {ALTURA}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Padrao,{FONTE},{TAMANHO_FONTE},{cor},{cor},{COR_CONTORNO},&H80000000,{-1 if NEGRITO else 0},0,0,0,100,100,0,0,1,{CONTORNO},{SOMBRA},2,60,60,{POSICAO_LEGENDA},1
Style: Marca,{FONTE},{TAMANHO_MARCA},&H00FFFFFF,&H00FFFFFF,&H00000000,&H55000000,-1,0,0,0,100,100,0,0,3,6,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = [cab]
    if MARCA_DAGUA and blocos and com_marca:
        linhas.append(f"Dialogue: 1,0:00:00.00,{fmt_ass(duracao_total)},Marca,,0,0,0,,"
                      f"{{\\pos({MARCA_X},{MARCA_Y})}}{MARCA_DAGUA}\n")
    for ini, fim, texto in blocos:
        texto = texto.replace("{", "(").replace("}", ")")
        bounce = "{\\fscx0\\fscy0\\t(0,120,\\fscx110\\fscy110)\\t(120,220,\\fscx100\\fscy100)}" if BOUNCE_LEGENDA else ""
        linhas.append(f"Dialogue: 0,{fmt_ass(ini)},{fmt_ass(fim)},Padrao,,0,0,0,,{bounce}{texto}\n")
    caminho.write_text("".join(linhas), encoding="utf-8")


def salvar_srt(blocos, caminho):
    partes = []
    for n, (ini, fim, texto) in enumerate(blocos, 1):
        partes.append(f"{n}\n{fmt_srt(ini)} --> {fmt_srt(fim)}\n{texto}\n")
    caminho.write_text("\n".join(partes), encoding="utf-8")


# ------------------------- vídeo -------------------------

def eh_video(arquivo):
    return arquivo.suffix.lower() in EXT_VIDEO


def _dim_imagem(imagem):
    """Retorna (largura, altura) da imagem ou vídeo."""
    if eh_video(imagem):
        r = rodar(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
                   "-select_streams", "v:0", str(imagem)])
        st = json.loads(r.stdout)["streams"][0]
        return int(st["width"]), int(st["height"])
    from PIL import Image
    with Image.open(imagem) as im:
        return im.size


def _escalar(w, h, caixa_w, caixa_h):
    """Retorna (fw, fh) — dimensões par-par para caber na caixa."""
    e = min(caixa_w / w, caixa_h / h)
    return int(w * e) // 2 * 2, int(h * e) // 2 * 2


def calcular_capa_geometria(imagem_path, largura=None, altura=None, layout=None):
    """Retorna (x, y, w, h) da capa dentro do frame do vídeo para o layout atual.
    Espelha exatamente o cálculo de render_trecho."""
    larg = largura or LARGURA
    alt  = altura  or ALTURA
    lay  = layout  or LAYOUT

    try:
        w_orig, h_orig = _dim_imagem(imagem_path)
    except Exception:
        return 0, 0, larg, alt   # fallback: frame inteiro

    if lay == "tela_cheia":
        return 0, 0, larg, alt

    if lay == "card":
        caixa_w, caixa_h = int(larg * 0.86), int(alt * 0.66)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        x = (larg - iw) // 2
        y = (alt  - ih) // 2
    elif lay == "dividido":
        caixa_w, caixa_h = larg, int(alt * 0.63)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        x = (larg - iw) // 2
        y = 0
    else:   # padrao, numero
        caixa_w, caixa_h = larg, int(alt * 0.78)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        x = (larg - iw) // 2
        y = (alt  - ih) // 2

    return x, y, iw, ih


def _frente_filtro(entrada_label, iw, ih, z, frames, is_video):
    """Retorna filter_str que produz [frente] no tamanho iw×ih."""
    if is_video:
        return f"{entrada_label}fps={FPS},scale={iw}:{ih},setsar=1[frente];"
    if z > 0:
        print("       ↳ zoom — trecho mais lento...", flush=True)
        return (f"{entrada_label}scale={iw*2}:{ih*2}:flags=lanczos,"
                f"zoompan=z='min(1+{z}*on/{frames},1+{z})'"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:fps={FPS}:s={iw}x{ih},setsar=1[frente];")
    return f"{entrada_label}scale={iw}:{ih},setsar=1[frente];"


def render_trecho(imagem, duracao, saida, com_zoom=True, layout=None, numero=None):
    layout = layout or LAYOUT
    z = ZOOM_MAXIMO if com_zoom else 0
    frames = max(1, int(duracao * FPS))
    is_video = eh_video(imagem)
    w_orig, h_orig = _dim_imagem(imagem)

    # ── Tela Cheia ────────────────────────────────────────────────────
    if layout == "tela_cheia":
        if is_video:
            entrada = ["-stream_loop", "-1", "-t", f"{duracao:.3f}", "-i", str(imagem)]
            filtro = (f"[0:v]fps={FPS},scale={LARGURA}:{ALTURA}:"
                      f"force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA},"
                      f"setsar=1,format=yuv420p[v]")
        else:
            from PIL import Image
            menor = Path(saida).with_suffix(".png")
            with Image.open(imagem) as im:
                im.convert("RGB").save(menor)
            entrada = ["-loop", "1", "-framerate", str(FPS), "-t", f"{duracao:.3f}", "-i", str(menor)]
            if z > 0:
                print("       ↳ zoom — trecho mais lento...", flush=True)
                filtro = (f"[0:v]scale={LARGURA*2}:{ALTURA*2}:"
                          f"force_original_aspect_ratio=increase,crop={LARGURA*2}:{ALTURA*2},"
                          f"zoompan=z='min(1+{z}*on/{frames},1+{z})'"
                          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                          f":d={frames}:fps={FPS}:s={LARGURA}x{ALTURA},"
                          f"setsar=1,format=yuv420p[v]")
            else:
                filtro = (f"[0:v]scale={LARGURA}:{ALTURA}:"
                          f"force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA},"
                          f"setsar=1,format=yuv420p[v]")
        rodar(["ffmpeg", "-y", *entrada, "-filter_complex", filtro, "-map", "[v]", "-an",
               "-t", f"{duracao:.3f}", "-r", str(FPS), "-c:v", "libx264",
               "-preset", "ultrafast", "-crf", "16", str(saida)])
        return

    # ── Card, Dividido, Padrão, Número ────────────────────────────────
    if layout == "card":
        caixa_w, caixa_h = int(LARGURA * 0.86), int(ALTURA * 0.66)
        ov_y = "(H-h)/2"
    elif layout == "dividido":
        caixa_w, caixa_h = LARGURA, int(ALTURA * 0.63)
        ov_y = "0"
    else:  # padrao, numero
        caixa_w, caixa_h = LARGURA, int(ALTURA * 0.78)
        ov_y = "(H-h)/2"

    iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)

    if is_video:
        entrada = ["-stream_loop", "-1", "-t", f"{duracao:.3f}", "-i", str(imagem)]
    else:
        from PIL import Image
        menor = Path(saida).with_suffix(".png")
        with Image.open(imagem) as im:
            im.convert("RGB").resize((iw, ih), Image.LANCZOS).save(menor)
        entrada = ["-loop", "1", "-framerate", str(FPS), "-t", f"{duracao:.3f}", "-i", str(menor)]

    frente = _frente_filtro("[0:v]", iw, ih, z, frames, is_video)

    # Fundo por layout
    if layout in ("card", "dividido"):
        fundo = f"color=c=#{COR_FUNDO_CARD}:s={LARGURA}x{ALTURA}:r={FPS}:d={duracao:.3f}[fundo];"
        if layout == "card":
            # moldura sutil ao redor da imagem
            mx, my = (LARGURA - iw) // 2, (ALTURA - ih) // 2
            fundo += (f"[fundo]drawbox=x={mx-4}:y={my-4}:w={iw+8}:h={ih+8}"
                      f":color=white@0.15:t=3[fundo];")
    elif layout == "numero" and isinstance(numero, int):
        num_txt = str(numero)
        if FUNDO == "desfocado":
            fundo = (f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
                     f"crop={LARGURA}:{ALTURA},gblur=sigma=40,eq=brightness=-0.18,"
                     f"fps={FPS}[bg];[bg]drawtext=font=Arial:text='{num_txt}'"
                     f":fontsize=440:fontcolor=white@0.07:x=(W-tw)/2:y=(H-th)/2[fundo];")
        else:
            fundo = (f"color=c=black:s={LARGURA}x{ALTURA}:r={FPS}:d={duracao:.3f}[bg];"
                     f"[bg]drawtext=font=Arial:text='{num_txt}'"
                     f":fontsize=440:fontcolor=white@0.07:x=(W-tw)/2:y=(H-th)/2[fundo];")
    else:  # padrao (ou numero sem numero fornecido)
        if FUNDO == "desfocado":
            fundo = (f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
                     f"crop={LARGURA}:{ALTURA},gblur=sigma=40,eq=brightness=-0.18,fps={FPS}[fundo];")
        else:
            fundo = f"color=c=black:s={LARGURA}x{ALTURA}:r={FPS}:d={duracao:.3f}[fundo];"

    filtro = fundo + frente + f"[fundo][frente]overlay=(W-w)/2:{ov_y}:shortest=1,format=yuv420p[v]"
    rodar(["ffmpeg", "-y", *entrada, "-filter_complex", filtro, "-map", "[v]", "-an",
           "-t", f"{duracao:.3f}", "-r", str(FPS), "-c:v", "libx264",
           "-preset", "ultrafast", "-crf", "16", str(saida)])


def _aplicar_borda(video_path: Path, tmp_dir: Path):
    """Aplica o PNG de borda decorativa sobre o vídeo final (última camada)."""
    if not BORDA_ATIVA:
        return
    nome = BORDA_ARQUIVO
    if not nome or nome == "Nenhuma":
        return
    borda_src = PASTA_BORDAS / nome
    if not borda_src.exists():
        print(f"  [borda] arquivo nao encontrado: {borda_src}")
        return

    borda_tmp = tmp_dir / "borda_overlay.png"
    shutil.copy(borda_src, borda_tmp)

    entrada_tmp = tmp_dir / "pre_borda.mp4"
    shutil.move(str(video_path), str(entrada_tmp))

    try:
        rodar([
            "ffmpeg", "-y",
            "-i", "pre_borda.mp4",
            "-i", "borda_overlay.png",
            "-filter_complex",
            "[1:v]scale=1080:1920[borda];"
            "[0:v][borda]overlay=0:0:format=auto[vout]",
            "-map", "[vout]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "copy", "-pix_fmt", "yuv420p",
            "final.mp4",
        ], cwd=tmp_dir)
        print(f"  [borda] aplicada: {nome}")
    except Exception as e:
        # Se falhar, restaura o vídeo original sem borda
        shutil.move(str(entrada_tmp), str(video_path))
        print(f"  [borda] erro ao aplicar: {e}")


def _aplicar_overlays(video_path: Path, audio_path: Path, tempos, inicio_item,
                      tokens, lingua: str, top_n: int, duracao: float,
                      tmp_dir: Path, imagens: dict = None) -> bool:
    """
    Tenta gerar overlays do personagem e objetos e aplica sobre video_path.
    imagens: dict {n: Path} das capas usadas no vídeo (para calcular posição real).
    Substitui video_path pelo resultado se bem-sucedido.
    Retorna True se pelo menos um overlay foi aplicado.
    """
    inputs_extra = []
    filtros = []
    v_prev = "0:v"
    idx_next = 1  # índice do próximo input extra (0 = vídeo principal)

    # ── Personagem (clipes MP4 com fundo removido) ───────────────────────────
    try:
        import personagem as _pers
        p_cfg = _pers.cfg()
        if p_cfg.get("ativo", True):
            pasta_pers = PASTA / "projeto" / "personagem"
            p_saida = tmp_dir / "personagem_overlay.mkv"

            p_ok = _pers.gerar_overlay(
                audio_path, tempos, inicio_item, top_n,
                duracao, FPS, LARGURA, ALTURA, POSICAO_LEGENDA,
                p_saida, pasta_pers, capa_rect=None
            )
            if p_ok:
                px, py = _pers.ler_posicao(p_saida)
                inputs_extra += ["-i", str(p_saida)]
                filtros.append(
                    f"[{v_prev}][{idx_next}:v]overlay={px}:{py}:shortest=1[v{idx_next}]"
                )
                v_prev = f"v{idx_next}"
                idx_next += 1
    except ImportError:
        print("  ℹ️  módulo personagem.py não encontrado — pulando personagem.")
    except Exception as e:
        print(f"  ⚠️  Personagem: {e}")

    # ── Objetos ───────────────────────────────────────────────────────────────
    try:
        import objetos as _obj
        o_cfg = _obj.cfg()
        if o_cfg.get("objetos_ativo", True) and tokens:
            obj_json = PASTA / "projeto" / "objetos" / "objetos.json"
            obj_config = _obj.carregar_config(obj_json)
            if obj_config:
                exibicoes = _obj.calcular_exibicoes(
                    tempos, tokens, lingua, obj_config, inicio_item, top_n, duracao
                )
                if exibicoes:
                    o_saida = tmp_dir / "objetos_overlay.webm"
                    pasta_obj = PASTA / "projeto" / "objetos"
                    o_ok = _obj.gerar_overlay(
                        exibicoes, pasta_obj, duracao, FPS,
                        LARGURA, ALTURA, POSICAO_LEGENDA, o_saida
                    )
                    if o_ok:
                        ox, oy = map(int, (Path(str(o_saida) + ".pos")
                                          .read_text().split(",")))
                        inputs_extra += ["-i", str(o_saida)]
                        filtros.append(
                            f"[{v_prev}][{idx_next}:v]overlay={ox}:{oy}:shortest=1[v{idx_next}]"
                        )
                        v_prev = f"v{idx_next}"
                        idx_next += 1
    except ImportError:
        print("  ℹ️  módulo objetos.py não encontrado — pulando objetos.")
    except Exception as e:
        print(f"  ⚠️  Objetos: {e}")

    if not filtros:
        return False

    # ── Aplica overlays via FFmpeg ────────────────────────────────────────────
    # Renomeia última saída de filtro para "vout"
    filtros[-1] = filtros[-1].rsplit(f"[v{idx_next - 1}]", 1)[0] + "[vout]"

    saida_tmp = tmp_dir / "final_overlay.mp4"
    cmd = (
        ["ffmpeg", "-y", "-i", str(video_path)]
        + inputs_extra
        + ["-filter_complex", ";".join(filtros)]
        + ["-map", "[vout]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
           "-c:a", "copy", str(saida_tmp)]
    )
    r = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="ignore",
        creationflags=_NO_WINDOW
    )
    if r.returncode != 0:
        print(f"  ⚠️  Overlay final: FFmpeg erro:\n{r.stderr[-500:]}")
        return False

    saida_tmp.replace(video_path)
    print(f"  ✅ Overlays aplicados ao vídeo final.")
    return True


def montar_video(lingua, imagens, audio, tempos, inicio_item, blocos, nome_saida,
                 logo_path=None, logo_sombra=None, duracao_max=None, top_n=10, pasta_saida=None,
                 tokens=None, cortes_prebuilt=None):
    duracao = duracao_audio(audio)
    if duracao_max:
        duracao = min(duracao, duracao_max)
    if duracao > AVISO_LIMITE_SEGUNDOS:
        print(f"   ⚠️ O áudio tem {duracao:.0f}s, passa de 3 minutos (limite do YouTube Shorts)!")

    # Cortes: usa lista pré-computada pelo template, ou constrói no modo legado (numerado)
    if cortes_prebuilt is not None:
        cortes = cortes_prebuilt
    else:
        # Modo legado (Top N hardcoded)
        cortes = []
        for n in range(top_n, 0, -1):
            if n not in inicio_item:
                erro(f"Não achei o item '{n} –' no roteiro ({lingua}).")
            cortes.append((n, max(tempos[inicio_item[n]][0] - 0.15, 0)))

        if "fim" in inicio_item:
            cortes.append((f"fechamento_{lingua}", max(tempos[inicio_item["fim"]][0] - 0.15, 0)))
        else:
            print("   ⚠️ Não achei o texto de encerramento; sem imagem de fechamento.")

    # (imagem, duracao_trecho, com_zoom, numero)
    trechos = []

    if cortes_prebuilt is None:
        # Modo legado: abertura separada antes dos cortes
        if cortes and cortes[0][1] > 0.05:
            chave_ab = f"abertura_{lingua}"
            if chave_ab in imagens:
                trechos.append((imagens[chave_ab], cortes[0][1], ZOOM_ABERTURA_FECHAMENTO, None))

    for k, (chave, ini) in enumerate(cortes):
        fim = cortes[k + 1][1] if k + 1 < len(cortes) else duracao
        if ini >= duracao:
            break
        dur_trecho = min(fim, duracao) - ini
        if dur_trecho <= 0:
            continue
        img = imagens.get(chave)
        if img is None:
            print(f"   ⚠️ Imagem não encontrada para cena '{chave}' — pulando.")
            continue
        is_fixo    = isinstance(chave, str)
        numero_int = chave if isinstance(chave, int) else None
        com_zoom   = (not is_fixo) or ZOOM_ABERTURA_FECHAMENTO
        trechos.append((img, dur_trecho, com_zoom, numero_int))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lista = []
        n_trechos = len(trechos)
        inicio_render = time.time()
        for k, (img, dur, com_zoom, num) in enumerate(trechos):
            decorrido = time.time() - inicio_render
            print(f"  🎬 Trecho {k + 1:>2} / {n_trechos}  ({fmt_duracao(dur)})"
                  f"  [{fmt_duracao(decorrido)}]", flush=True)
            arq = tmp / f"t{k:02d}.mp4"
            render_trecho(img, dur, arq, com_zoom=com_zoom, numero=num)
            lista.append(f"file '{arq.name}'")
            if SALVAR_FRAMES and isinstance(num, int):
                frame_dir = (pasta_saida if pasta_saida else PASTA_SAIDA) / "frames"
                frame_dir.mkdir(parents=True, exist_ok=True)
                frame_out = frame_dir / f"frame_{num:02d}.png"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(arq), "-vframes", "1", "-q:v", "2", str(frame_out)],
                    capture_output=True, creationflags=_NO_WINDOW
                )
        (tmp / "lista.txt").write_text("\n".join(lista), encoding="utf-8")

        if DURACAO_FADE > 0 and n_trechos > 1:
            print(f"\n  🎞️  Aplicando fade entre trechos ({DURACAO_FADE}s)...")
            durs = [d for _, d, _, _ in trechos]
            cmd_x = ["ffmpeg", "-y"]
            for k in range(n_trechos):
                cmd_x += ["-i", f"t{k:02d}.mp4"]
            partes, prev, off = [], "[0:v]", 0.0
            for i in range(1, n_trechos):
                off += durs[i - 1] - DURACAO_FADE
                prox = "[v_out]" if i == n_trechos - 1 else f"[vx{i}]"
                partes.append(
                    f"{prev}[{i}:v]xfade=transition=fade"
                    f":duration={DURACAO_FADE:.2f}:offset={off:.3f}{prox}"
                )
                prev = f"[vx{i}]"
            cmd_x += ["-filter_complex", ";".join(partes), "-map", "[v_out]",
                      "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
                      "video.mp4"]
            rodar(cmd_x, cwd=tmp)
        else:
            rodar(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt",
                   "-vf", f"fps={FPS},setpts=N/FRAME_RATE/TB",
                   "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
                   "video.mp4"], cwd=tmp)

        tem_logo = logo_path is not None
        salvar_ass(blocos, tmp / "legenda.ass", duracao, com_marca=not tem_logo)
        shutil.copy(audio, tmp / f"audio{audio.suffix}")

        if PASTA_MUSICA.exists():
            _musicas = [p for p in PASTA_MUSICA.glob("*") if p.suffix.lower() in EXT_AUDIO]
            import engine as _gv_m
            if _gv_m.MUSICA_MODO == "selecionar" and _gv_m.MUSICA_ATIVA:
                musica_path = PASTA_MUSICA / _gv_m.MUSICA_ATIVA
                musica = musica_path if musica_path.exists() else (random.choice(_musicas) if _musicas else None)
            else:
                musica = random.choice(_musicas) if _musicas else None
            if musica:
                print(f"  🎵 Música: {musica.name}")
        else:
            musica = None

        print("\n  ✍️  Finalizando — comprimindo e adicionando áudio + legenda...")
        cmd = ["ffmpeg", "-y", "-i", "video.mp4", "-i", f"audio{audio.suffix}"]
        idx = 2

        if musica:
            shutil.copy(musica, tmp / f"musica{musica.suffix}")
            cmd += ["-stream_loop", "-1", "-i", f"musica{musica.suffix}"]
            musica_idx = idx; idx += 1
        else:
            musica_idx = None

        if tem_logo:
            shutil.copy(logo_path, tmp / "logo.png")
            cmd += ["-i", "logo.png"]
            logo_idx = idx; idx += 1

        if musica or tem_logo:
            fc = [f"[0:v]ass=legenda.ass[v0]"]
            v = "[v0]"
            if tem_logo:
                fc.append(f"{v}[{logo_idx}:v]overlay={LOGO_X}:{LOGO_Y}[v_out]")
                v = "[v_out]"
            else:
                fc[0] = fc[0].replace("[v0]", "[v_out]")
                v = "[v_out]"
            if musica:
                fc.append(f"[{musica_idx}:a]volume={VOLUME_MUSICA}[m];"
                          f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a_mix]")
            cmd += ["-filter_complex", ";".join(fc), "-map", v,
                    "-map", "[a_mix]" if musica else "1:a"]
        else:
            cmd += ["-vf", "ass=legenda.ass", "-map", "0:v", "-map", "1:a"]
        preset_usar = "ultrafast" if duracao_max else FFMPEG_PRESET_FINAL
        crf_usar    = 28          if duracao_max else FFMPEG_CRF_FINAL
        cmd += ["-c:v", "libx264", "-preset", preset_usar, "-crf", str(crf_usar), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{duracao:.3f}", "-movflags", "+faststart",
                "final.mp4"]
        rodar(cmd, cwd=tmp)

        # ── Overlays: personagem e objetos ────────────────────────────────────
        _aplicar_overlays(
            tmp / "final.mp4", Path(audio), tempos, inicio_item,
            tokens, lingua, top_n, duracao, tmp, imagens=imagens
        )

        # ── Overlay: borda decorativa (última camada — por cima de tudo) ─────
        _aplicar_borda(tmp / "final.mp4", tmp)

        pasta_dest = pasta_saida if pasta_saida else PASTA_SAIDA
        pasta_dest.mkdir(parents=True, exist_ok=True)
        destino = pasta_dest / f"{nome_saida}.mp4"
        shutil.move(str(tmp / "final.mp4"), destino)
    return destino, duracao


# ------------------------- timestamps export -------------------------

def _fmt_ts(segundos):
    """Formata segundos como M:SS (ex: 73 → '1:13')."""
    s = int(max(0, segundos))
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"


def _gerar_timestamps(lingua, tempos, inicio_item, top_n, pasta_destino):
    """Gera timestamps.txt na pasta de shorts com marcações de tempo para YouTube."""
    try:
        nomes = _extrair_nomes_roteiro(top_n)
        hoje = datetime.datetime.now().strftime("%d/%m/%Y")
        lang_label = "PT" if lingua == "pt" else "EN"
        linhas = [f"Timestamps — [{lang_label}] — {hoje}", ""]

        # Introdução — começa em 0:00
        linhas.append("0:00 Introdução")

        for n in range(top_n, 0, -1):
            if n not in inicio_item:
                continue
            idx = inicio_item[n]
            if idx < len(tempos) and tempos[idx] is not None:
                t = tempos[idx][0]
            else:
                continue
            nome_item = (nomes[n][lingua] or nomes[n]["pt"] or nomes[n]["en"] or f"Item {n}")
            linhas.append(f"{_fmt_ts(t)} → #{n} {nome_item}")

        if "fim" in inicio_item:
            idx_fim = inicio_item["fim"]
            if idx_fim < len(tempos) and tempos[idx_fim] is not None:
                t_fim = tempos[idx_fim][0]
                linhas.append(f"{_fmt_ts(t_fim)} Encerramento")

        arq = pasta_destino / "timestamps.txt"
        arq.write_text("\n".join(linhas), encoding="utf-8")
        print(f"     Timestamps: {arq.name}")
    except Exception as e:
        print(f"     ⚠️  Não foi possível gerar timestamps: {e}")


# ------------------------- Instagram helpers -------------------------

def _calcular_posicao_marca_insta(imagem):
    """Retorna (marca_x, marca_y, img_w, img_h): posição da marca relativa à área da imagem
    dentro do frame Instagram. Deve ser chamada com ALTURA já igual a ALTURA_INSTA."""
    try:
        w_orig, h_orig = _dim_imagem(imagem)
    except Exception:
        return round(0.03 * LARGURA), round(0.03 * ALTURA), LARGURA, ALTURA

    if LAYOUT == "tela_cheia":
        img_x, img_y, img_w, img_h = 0, 0, LARGURA, ALTURA
    elif LAYOUT == "card":
        caixa_w, caixa_h = int(LARGURA * 0.86), int(ALTURA * 0.66)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        img_x, img_y, img_w, img_h = (LARGURA - iw) // 2, (ALTURA - ih) // 2, iw, ih
    elif LAYOUT == "dividido":
        caixa_w, caixa_h = LARGURA, int(ALTURA * 0.63)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        img_x, img_y, img_w, img_h = (LARGURA - iw) // 2, 0, iw, ih
    else:  # padrao, numero
        caixa_w, caixa_h = LARGURA, int(ALTURA * 0.78)
        iw, ih = _escalar(w_orig, h_orig, caixa_w, caixa_h)
        img_x, img_y, img_w, img_h = (LARGURA - iw) // 2, (ALTURA - ih) // 2, iw, ih

    marca_x = round(img_x + 0.015 * img_w)
    marca_y = round(img_y + 0.025 * img_h)
    return marca_x, marca_y, img_w, img_h


def _preparar_logo_insta(img_w):
    """Redimensiona o logo para 22% de img_w para o vídeo Instagram.
    Retorna (logo_path, None) ou (None, None) se logo não existir."""
    n = _resolver_logo()
    logo_src = achar_arquivo(PASTA_LOGOS, f"logo_{n}", EXT_IMAGEM) if n is not None else None
    if not logo_src:
        logo_src = achar_arquivo(PASTA_IMAGENS, "logo", EXT_IMAGEM)
    if not logo_src:
        return None, None
    try:
        from PIL import Image
    except ImportError:
        return None, None

    target_w = max(20, round(0.22 * img_w))
    with Image.open(logo_src) as img:
        img = img.convert("RGBA")
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        w, h = img.size
        target_h = max(1, round(h * target_w / w))
        img = img.resize((target_w, target_h), Image.LANCZOS)
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="rnk_logo_insta_")
        os.close(fd)
        img.save(tmp_path, "PNG")
    return Path(tmp_path), None


# ========================= TEMPLATE ENGINE =========================

def _carregar_template_arquivo(path: str) -> dict | None:
    """Carrega template JSON de um arquivo. Retorna None em caso de erro."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠️  Não foi possível ler o template '{path}': {e}")
        return None


def carregar_cenas_template(template: dict, linguas: list) -> dict:
    """
    Monta o dict de imagens com base no tipo do template.
    Chaves: "abertura_{lingua}", 1..N (int), "nome_secao" (str), "livre_N" (str),
            "fechamento_{lingua}".
    """
    imagens = {}
    tipo = template.get("tipo", "livre")
    exts = EXT_IMAGEM + EXT_VIDEO

    # ── Abertura ────────────────────────────────────────────────────────────
    if template.get("abertura"):
        for lingua in linguas:
            chave = f"abertura_{lingua}"
            img = (achar_arquivo(PASTA_IMAGENS, chave, exts) or
                   achar_arquivo(PASTA_IMAGENS, "abertura", exts))
            if img:
                imagens[chave] = img

    # ── Conteúdo principal ───────────────────────────────────────────────────
    if tipo == "numerado":
        n = template.get("n_itens", 10)
        for i in range(1, n + 1):
            img = achar_arquivo(PASTA_IMAGENS, str(i), exts)
            if img:
                imagens[i] = img

    elif tipo == "secoes":
        for s in template.get("secoes", []):
            nome_arq = s["label"].lower().replace(" ", "_")
            img = (achar_arquivo(PASTA_IMAGENS, nome_arq, exts) or
                   achar_arquivo(PASTA_IMAGENS, s.get("id", nome_arq), exts))
            if img:
                imagens[nome_arq] = img

    else:  # livre
        _excluir = {"abertura", "fechamento", "logo", "tema"}
        cenas_livres = sorted(
            f for f in PASTA_IMAGENS.iterdir()
            if f.is_file() and f.suffix.lower() in set(exts)
            and not any(ex in f.stem.lower() for ex in _excluir)
        )
        for idx, f in enumerate(cenas_livres, 1):
            imagens[f"livre_{idx}"] = f

    # ── Fechamento ──────────────────────────────────────────────────────────
    if template.get("fechamento"):
        for lingua in linguas:
            chave = f"fechamento_{lingua}"
            img = (achar_arquivo(PASTA_IMAGENS, chave, exts) or
                   achar_arquivo(PASTA_IMAGENS, "fechamento", exts))
            if img:
                imagens[chave] = img

    return imagens


def tokenizar_template(template: dict, linhas: list) -> tuple:
    """
    Tokenizador ciente de template.
    Retorna (tokens, linha_de, inicio_cenas) onde inicio_cenas mapeia
    chave-da-cena → índice-do-token-inicial.

    - numerado: reusa tokenizar() (marcadores N – no roteiro)
    - secoes:   procura marcadores [NOME_SECAO] no roteiro
    - livre:    retorna {} (sem cortes; tempo dividido igualmente)
    """
    tipo = template.get("tipo", "livre")

    if tipo == "numerado":
        return tokenizar(linhas)

    elif tipo == "secoes":
        tokens, linha_de = [], []
        inicio_cenas: dict = {}
        for i, linha in enumerate(linhas):
            m = re.match(r"^\[(.+?)\]$", linha.strip())
            if m:
                chave = m.group(1).strip().lower().replace(" ", "_")
                inicio_cenas[chave] = len(tokens)
                continue
            for t in linha.split():
                tokens.append(t)
                linha_de.append(i)
        return tokens, linha_de, inicio_cenas

    else:  # livre
        tokens, linha_de = [], []
        for i, linha in enumerate(linhas):
            for t in linha.split():
                tokens.append(t)
                linha_de.append(i)
        return tokens, linha_de, {}


def _cortes_de_template(template: dict, imagens: dict, inicio_cenas: dict,
                         tempos: list, duracao: float, lingua: str) -> list:
    """
    Constrói a lista de cortes no formato [(chave, t_inicio), ...] para
    ser usada em montar_video(). Inclui abertura e fechamento quando presentes.

    - numerado: baseado nos marcadores N– do roteiro (mesmo esquema atual)
    - secoes:   baseado nos marcadores [NOME_SECAO] do roteiro
    - livre:    divisão igual de tempo entre todas as cenas
    """
    tipo    = template.get("tipo", "livre")
    exts    = EXT_IMAGEM + EXT_VIDEO

    # Helper para converter índice de token → timestamp
    def _t(idx):
        if idx < len(tempos) and tempos[idx] is not None:
            return max(tempos[idx][0] - 0.15, 0.0)
        return 0.0

    cortes: list = []

    if tipo == "numerado":
        n     = template.get("n_itens", 10)
        ordem = template.get("ordem", "decrescente")
        seq   = list(range(n, 0, -1)) if ordem == "decrescente" else list(range(1, n + 1))

        # Abertura (antes do primeiro item)
        if template.get("abertura"):
            chave_ab = f"abertura_{lingua}"
            if chave_ab not in imagens:
                chave_ab = "abertura"
            if chave_ab in imagens:
                cortes.insert(0, (chave_ab, 0.0))   # começa em t=0

        for num in seq:
            if num not in inicio_cenas:
                continue
            cortes.append((num, _t(inicio_cenas[num])))

        if "fim" in inicio_cenas:
            chave_fech = f"fechamento_{lingua}"
            if chave_fech not in imagens:
                chave_fech = "fechamento"
            if chave_fech in imagens:
                cortes.append((chave_fech, _t(inicio_cenas["fim"])))

    elif tipo == "secoes":
        if template.get("abertura"):
            chave_ab = f"abertura_{lingua}"
            if chave_ab not in imagens:
                chave_ab = "abertura"
            if chave_ab in imagens:
                cortes.append((chave_ab, 0.0))

        for s in template.get("secoes", []):
            nome = s["label"].lower().replace(" ", "_")
            if nome not in inicio_cenas or nome not in imagens:
                continue
            cortes.append((nome, _t(inicio_cenas[nome])))

        if "fim" in inicio_cenas:
            chave_fech = f"fechamento_{lingua}"
            if chave_fech not in imagens:
                chave_fech = "fechamento"
            if chave_fech in imagens:
                cortes.append((chave_fech, _t(inicio_cenas["fim"])))

    else:  # livre — divide o áudio igualmente
        todas: list = []
        if template.get("abertura"):
            chave_ab = f"abertura_{lingua}"
            if chave_ab not in imagens:
                chave_ab = "abertura"
            if chave_ab in imagens:
                todas.append(chave_ab)

        # Cenas livres ordenadas por nome
        todas += sorted(
            (k for k in imagens if isinstance(k, str) and k.startswith("livre_")),
            key=lambda k: int(k.split("_")[1]))

        if template.get("fechamento"):
            chave_fech = f"fechamento_{lingua}"
            if chave_fech not in imagens:
                chave_fech = "fechamento"
            if chave_fech in imagens:
                todas.append(chave_fech)

        if todas:
            t_por = duracao / len(todas)
            cortes = [(chave, i * t_por) for i, chave in enumerate(todas)]

    return cortes


def _verificar_cenas_template(template: dict, imagens: dict, lingua: str) -> list:
    """Retorna lista de problemas encontrados nas cenas do template."""
    problemas = []
    tipo = template.get("tipo", "livre")

    if tipo == "numerado":
        n = template.get("n_itens", 10)
        for i in range(1, n + 1):
            if i not in imagens:
                problemas.append(f"Falta imagem {i}.png em cenas/")

    elif tipo == "secoes":
        for s in template.get("secoes", []):
            nome_arq = s["label"].lower().replace(" ", "_")
            if nome_arq not in imagens and s.get("obrigatorio", True):
                problemas.append(f"Falta imagem {nome_arq}.png em cenas/")

    elif tipo == "livre":
        cenas_livres = [k for k in imagens if isinstance(k, str) and k.startswith("livre_")]
        if not cenas_livres:
            problemas.append("Nenhuma imagem/vídeo encontrada em cenas/")

    if template.get("abertura"):
        chave = f"abertura_{lingua}"
        if chave not in imagens and "abertura" not in imagens:
            problemas.append(f"Falta abertura.png em cenas/ (template tem abertura ativada)")

    if template.get("fechamento"):
        chave = f"fechamento_{lingua}"
        if chave not in imagens and "fechamento" not in imagens:
            problemas.append(f"Falta fechamento.png em cenas/ (template tem fechamento ativado)")

    return problemas

# ===================================================================


# ------------------------- principal -------------------------

def processar(lingua, imagens, logo_path=None, logo_sombra=None, obter_palavras=transcrever,
              duracao_max=None, top_n=10, template=None):
    global ALTURA, MARCA_X, MARCA_Y, LOGO_X, LOGO_Y
    nomes = {"pt": "PORTUGUÊS", "en": "INGLÊS"}
    arq_eleven, arq_leg = achar_roteiro(lingua)
    audio = achar_audio(PASTA_AUDIO, lingua)

    if not (arq_eleven and audio):
        print(f"⏭️  {nomes[lingua]}: faltando roteiro ou áudio, pulando.")
        return None

    bandeiras = {"pt": "🇧🇷", "en": "🇺🇸"}
    secao(f"{bandeiras.get(lingua, '')} {nomes[lingua]}")

    dur_seg = duracao_audio(audio)
    dur_str = fmt_duracao(dur_seg)
    print(f"  Roteiro  : {arq_eleven.name}")
    print(f"  Áudio    : {audio.name}  ({dur_str})")
    if duracao_max:
        print(f"  ▶ Preview: primeiros {duracao_max}s")

    if dur_seg > AVISO_LIMITE_SEGUNDOS and not duracao_max:
        print(f"\n  ⚠️  Áudio com {dur_str} — passa do limite de 3 min do YouTube Shorts!")
        resp = _input_gui("  Continuar mesmo assim? [S/N]: ", "s")
        if resp != "s":
            return None

    linhas_eleven = limpar_roteiro(ler_texto(arq_eleven))
    if not linhas_eleven:
        erro(f"Roteiro '{arq_eleven.name}' está vazio após limpeza.\n"
             f"   Verifique se o arquivo contém a narração.")

    if arq_leg != arq_eleven:
        linhas_leg = limpar_roteiro(ler_texto(arq_leg))
        print(f"  Legendas : {arq_leg.name}  (arquivo separado)")
    else:
        linhas_leg = linhas_eleven

    # Tokenização ciente de template
    _tipo_tmpl = template.get("tipo", "livre") if template else "numerado"
    if template and _tipo_tmpl != "numerado":
        tokens, _, inicio_item = tokenizar_template(template, linhas_eleven)
    else:
        tokens, _, inicio_item = tokenizar(linhas_eleven)
        # Valida presença de todos os itens N..1 (só para tipo numerado)
        _top = (template.get("n_itens", top_n) if template else top_n)
        faltando = [n for n in range(1, _top + 1) if n not in inicio_item]
        if faltando:
            encontrados_int = sorted(n for n in inicio_item if isinstance(n, int))
            erro(f"Roteiro incompleto — esperado: itens 1 a {_top}, encontrado: {encontrados_int}\n"
                 f"   Faltando: {', '.join(map(str, faltando))}\n"
                 f"   Certifique-se de que cada item começa com o número seguido de '–' ou '-'\n"
                 f"   Exemplo: '{faltando[0]} – Título do item {faltando[0]}'")

    # Verificar se duração do áudio condiz com o tamanho do roteiro
    n_palavras_rot = sum(1 for t in tokens if eh_palavra(t))
    if n_palavras_rot > 0:
        dur_est_min = n_palavras_rot / 3.5   # narrador rápido: ~3.5 palavras/s
        dur_est_max = n_palavras_rot / 1.8   # narrador lento: ~1.8 palavras/s
        if dur_seg < dur_est_min * 0.65 or dur_seg > dur_est_max * 1.5:
            direcao = "curto" if dur_seg < dur_est_min * 0.65 else "longo"
            print(f"\n  ⚠️  Áudio ({fmt_duracao(dur_seg)}) parece muito {direcao} para "
                  f"{n_palavras_rot} palavras no roteiro")
            print(f"     Esperado: {fmt_duracao(dur_est_min)}–{fmt_duracao(dur_est_max)}")
            print(f"     Verifique se o áudio e o roteiro são do mesmo vídeo.")
    print()

    duracao = dur_seg
    palavras = obter_palavras(audio, lingua)
    tempos = alinhar(tokens, palavras, lingua, duracao)

    tok_leg, linha_leg = tokens_legenda(tokens, linhas_leg, lingua)
    tempos_leg = mapear_tempos_legenda(tokens, tempos, tok_leg, lingua)
    blocos = montar_blocos(tok_leg, linha_leg, tempos_leg, inicio_item)

    agora = datetime.datetime.now()
    pasta_dia = PASTA_SAIDA / f"doramas-{agora.strftime('%d-%m-%y')}"
    _nomes_lingua = {"pt": "portugues", "en": "ingles"}
    pasta_lingua = pasta_dia / _nomes_lingua.get(lingua, lingua)
    pasta_shorts = pasta_lingua / "shorts"
    pasta_shorts.mkdir(parents=True, exist_ok=True)
    horario = agora.strftime("%H.%M.%S")
    sufixo = "-preview" if duracao_max else ""
    nome = f"{lingua}-{horario}{sufixo}"
    # Para templates não-numerados, pré-computa os cortes
    _cortes_tmpl = None
    if template and _tipo_tmpl != "numerado":
        _top = len([k for k in imagens if isinstance(k, str) and k.startswith("livre_")])
        _duracao_audio = duracao_audio(audio)
        _cortes_tmpl = _cortes_de_template(
            template, imagens, inicio_item, tempos,
            min(_duracao_audio, duracao_max) if duracao_max else _duracao_audio,
            lingua
        )

    _top_n_real = (template.get("n_itens", top_n) if template and _tipo_tmpl == "numerado"
                   else top_n)

    destino, dur = montar_video(lingua, imagens, audio, tempos, inicio_item, blocos, nome,
                                logo_path, logo_sombra, duracao_max=duracao_max,
                                top_n=_top_n_real,
                                pasta_saida=pasta_shorts, tokens=tokens,
                                cortes_prebuilt=_cortes_tmpl)

    if not duracao_max and GERAR_SRT:
        srt_path = pasta_shorts / f"{nome}.srt"
        salvar_srt(blocos, srt_path)

    if not duracao_max:
        _gerar_timestamps(lingua, tempos, inicio_item, top_n, pasta_shorts)

    tamanho_mb = destino.stat().st_size / (1024 * 1024)
    bitrate_kbps = int(destino.stat().st_size * 8 / dur / 1000) if dur else 0
    print(f"\n  ✅ {destino.name}")
    print(f"     Duração   : {fmt_duracao(dur)}")
    print(f"     Tamanho   : {tamanho_mb:.0f} MB  ({bitrate_kbps} kbps)")
    print(f"     Resolução : {LARGURA}×{ALTURA} @ {FPS}fps  |  Layout: {LAYOUT}  |  Top {top_n}")
    print(f"     Legenda   : {len(blocos)} blocos  {f'· alinhamento: {_ultimo_alinhamento_pct}%' if not duracao_max else ''}  {'· .srt salvo' if not duracao_max and GERAR_SRT else ''}")

    if not duracao_max:
        _salvar_historico({
            "data": datetime.datetime.now().isoformat(timespec="seconds"),
            "lingua": lingua,
            "arquivo": destino.name,
            "duracao_s": round(dur, 1),
            "tamanho_mb": round(tamanho_mb, 1),
            "bitrate_kbps": bitrate_kbps,
            "top_n": top_n,
            "alinhamento_pct": _ultimo_alinhamento_pct,
            "layout": LAYOUT,
        })

    if GERAR_INSTA and not duracao_max and lingua in GERAR_INSTA_LINGUAS:
        secao("📱 Versão Instagram (4:5 · 1080×1350)")
        _alt_orig = ALTURA
        _mx_orig  = MARCA_X
        _my_orig  = MARCA_Y
        _lx_orig  = LOGO_X
        _ly_orig  = LOGO_Y
        ALTURA = ALTURA_INSTA

        # Calcula posição da marca relativa à área real da imagem no frame
        imagem_ref = (imagens.get(f"abertura_{lingua}")
                      or imagens.get("abertura_pt")
                      or imagens.get(1))
        marca_x, marca_y, img_w, img_h = _calcular_posicao_marca_insta(imagem_ref)
        MARCA_X = marca_x
        MARCA_Y = marca_y
        LOGO_X  = marca_x
        LOGO_Y  = marca_y

        # Logo redimensionado para caber na área do selo (~22% da largura da imagem)
        logo_i, sombra_i = (_preparar_logo_insta(img_w) if logo_path else (None, None))

        pasta_insta = pasta_lingua / "instagram"
        pasta_insta.mkdir(parents=True, exist_ok=True)
        try:
            nome_insta = f"{lingua}-insta-{horario}"
            dest_insta, _ = montar_video(lingua, imagens, audio, tempos, inicio_item, blocos,
                                          nome_insta,
                                          logo_i or logo_path,
                                          sombra_i or logo_sombra,
                                          duracao_max=None, top_n=top_n,
                                          pasta_saida=pasta_insta, tokens=tokens)
            t_insta = dest_insta.stat().st_size / (1024 * 1024)
            print(f"\n  ✅ {dest_insta.name}")
            print(f"     Resolução : {LARGURA}×{ALTURA_INSTA} @ {FPS}fps  (Instagram 4:5)")
            print(f"     Tamanho   : {t_insta:.0f} MB")
            print(f"     Imagem    : {img_w}×{img_h}px  offset ({marca_x - round(0.015*img_w)}, "
                  f"{marca_y - round(0.010*img_h)})")
            print(f"     Marca     : x={marca_x}px  y={marca_y}px  "
                  f"(1.5% × 1% da imagem)")
        finally:
            ALTURA  = _alt_orig
            MARCA_X = _mx_orig
            MARCA_Y = _my_orig
            LOGO_X  = _lx_orig
            LOGO_Y  = _ly_orig
            for arq in filter(None, [logo_i]):
                try:
                    Path(arq).unlink()
                except Exception:
                    pass

    return destino


def gerar_videos(linguas, duracao_max=None, top_n=10, template=None):
    """Gera vídeos para as línguas especificadas. duracao_max em segundos = modo preview."""
    # Detecta FFmpeg em pastas locais se não estiver no PATH
    if not shutil.which("ffmpeg"):
        locais_ffmpeg = [
            Path("C:/ffmpeg/bin"),
            Path("C:/ffmpeg"),
            Path("C:/Program Files/ffmpeg/bin"),
            PASTA / "ffmpeg" / "bin",
            PASTA / "ffmpeg",
        ]
        for loc in locais_ffmpeg:
            if (loc / "ffmpeg.exe").exists():
                os.environ["PATH"] = str(loc) + os.pathsep + os.environ.get("PATH", "")
                print(f"  🔧 FFmpeg encontrado em: {loc}")
                break
    if not shutil.which("ffmpeg"):
        erro("FFmpeg não encontrado. Instale com:  winget install Gyan.FFmpeg\n"
             "   ou baixe de https://ffmpeg.org/download.html e coloque em C:\\ffmpeg\\bin\\")

    for p in (PASTA_IMAGENS, PASTA_ROTEIRO, PASTA_AUDIO, PASTA_MUSICA, PASTA_SAIDA):
        p.mkdir(exist_ok=True)

    if not duracao_max and not _verificar_espaco_disco():
        return

    # ── Carregamento de cenas: via template ou modo legado (Top N) ──────────
    _top_n_eff = (template.get("n_itens", top_n)
                  if template and template.get("tipo") == "numerado" else top_n)

    # Verifica problemas antes de começar
    problemas = []
    if template:
        _imgs_check = carregar_cenas_template(template, linguas)
        for lingua in linguas:
            problemas += _verificar_cenas_template(template, _imgs_check, lingua)
    else:
        for n in range(1, _top_n_eff + 1):
            if not achar_arquivo(PASTA_IMAGENS, str(n), EXT_IMAGEM + EXT_VIDEO):
                problemas.append(f"Falta imagem {n}.png em cenas/")
    for lingua in linguas:
        arq_eleven, _ = achar_roteiro(lingua)
        if not arq_eleven:
            problemas.append(f"Falta roteiro em roteiro/  (roteiro_{lingua}.txt)")
        if not achar_audio(PASTA_AUDIO, lingua):
            problemas.append(f"Falta áudio com '{lingua}' no nome em audio/")
    if problemas:
        print(f"\n  ❌ Encontrei {len(problemas)} problema(s) antes de começar:\n")
        for p in problemas:
            print(f"     • {p}")
        _input_gui("\n  Corrija os arquivos e tente novamente. Enter para voltar...")
        return

    # Sorteia tema e logo uma única vez — todas as línguas usam o mesmo par
    n_tema = _resolver_tema()
    n_logo = _resolver_logo()
    if n_tema is not None:
        import engine as _gv_t
        modos = {"padrao": "padrão", "aleatorio": "aleatório", "selecionar": "selecionado"}
        print(f"\n  🎨 Tema {n_tema}  ({modos.get(_gv_t.MODO_TEMA, _gv_t.MODO_TEMA)})")

    # Carrega imagens baseado no template ou modo legado
    if template:
        imagens = carregar_cenas_template(template, linguas)
        if n_tema is not None:
            for lingua in linguas:
                for tipo in ("abertura", "fechamento"):
                    img_tema = achar_arquivo(
                        PASTA_TEMAS, f"{tipo}_{lingua}_{n_tema}", EXT_IMAGEM + EXT_VIDEO)
                    if img_tema:
                        imagens[f"{tipo}_{lingua}"] = img_tema
    else:
        imagens = {}
        for n in range(1, _top_n_eff + 1):
            imagens[n] = achar_arquivo(PASTA_IMAGENS, str(n), EXT_IMAGEM + EXT_VIDEO)
        for lingua in ("pt", "en"):
            for tipo in ("abertura", "fechamento"):
                chave = f"{tipo}_{lingua}"
                img = None
                if n_tema is not None:
                    img = achar_arquivo(PASTA_TEMAS, f"{tipo}_{lingua}_{n_tema}", EXT_IMAGEM + EXT_VIDEO)
                if not img:
                    img = (achar_arquivo(PASTA_IMAGENS, chave, EXT_IMAGEM + EXT_VIDEO) or
                           achar_arquivo(PASTA_IMAGENS, tipo, EXT_IMAGEM + EXT_VIDEO))
                if img:
                    imagens[chave] = img

    if not duracao_max and not template:
        _verificar_duplicatas_roteiro(_top_n_eff)

    logo_path, logo_sombra = preparar_logo(n_logo=n_logo)

    feitos = []
    _nome_lingua = {"pt": "PORTUGUÊS", "en": "INGLÊS"}
    for lingua in linguas:
        _nome_exib = _nome_lingua.get(lingua, lingua.upper())
        arq_eleven, _ = achar_roteiro(lingua)
        audio = achar_audio(PASTA_AUDIO, lingua)
        if not arq_eleven:
            print(f"\n  ⚠️  {_nome_exib}: nenhum roteiro encontrado — pulando.")
            continue
        if not audio:
            print(f"\n  ⚠️  {_nome_exib}: nenhum áudio com '{lingua}' no nome — pulando.")
            continue
        validar_audio(audio)
        resultado = processar(lingua, imagens, logo_path, logo_sombra,
                              duracao_max=duracao_max, top_n=_top_n_eff,
                              template=template)
        if resultado:
            feitos.append(resultado)

    for arq in filter(None, [logo_path, logo_sombra]):
        try:
            Path(arq).unlink()
        except Exception:
            pass

    print(f"\n{'━' * 42}")
    if not feitos:
        print("  ❌ Nenhum vídeo gerado.")
        print("     Verifique se os roteiros e áudios estão nas pastas corretas.")
    else:
        print(f"  ✅ {len(feitos)} vídeo(s) gerado(s) com sucesso!")
    print(f"{'━' * 42}")

    # Histórico: lista vídeos da pasta do dia atual
    pasta_hoje = PASTA_SAIDA / f"doramas-{datetime.datetime.now().strftime('%d-%m-%y')}"
    pasta_exibir = pasta_hoje if pasta_hoje.exists() else PASTA_SAIDA
    if pasta_exibir.exists():
        videos = sorted(
            [p for p in pasta_exibir.rglob("*.mp4")],
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if videos:
            print(f"\n  📁 {pasta_exibir.relative_to(PASTA_SAIDA.parent)}  ({len(videos)} arquivo(s))")
            print(f"  {'─' * 38}")
            for p in videos[:10]:
                data = time.strftime("%d/%m  %H:%M", time.localtime(p.stat().st_mtime))
                tamanho = p.stat().st_size / (1024 * 1024)
                print(f"  {data}  {p.name:<42}  {tamanho:.0f} MB")
            if len(videos) > 10:
                print(f"  ... e mais {len(videos) - 10} vídeo(s)")

    ultimo_video = feitos[-1] if feitos else None
    print(f"\n  A = abrir pasta  {'· B = reproduzir vídeo  ' if ultimo_video else ''}· Enter = voltar")
    resp = _input_gui("  → ").strip().lower()
    if resp == "a":
        pasta_hoje.mkdir(parents=True, exist_ok=True)
        os.startfile(str(pasta_hoje))
    elif resp == "b" and ultimo_video:
        os.startfile(str(ultimo_video))


def status_pastas():
    """Exibe bloco de status colorido e compacto dos arquivos de entrada."""
    import engine as _gv_s

    # ── cenas ────────────────────────────────────────────────────────────────
    n_seq = 0
    for n in range(1, 11):
        if achar_arquivo(PASTA_IMAGENS, str(n), EXT_IMAGEM + EXT_VIDEO):
            n_seq += 1
        else:
            break
    imgs_ok = n_seq >= 1

    n_doramas = 0
    if PASTA_DORAMAS.exists():
        exts_d = set(EXT_IMAGEM + EXT_VIDEO)
        n_doramas = sum(1 for p in PASTA_DORAMAS.iterdir() if p.suffix.lower() in exts_d)

    temas = _listar_temas()
    logos = _listar_logos()

    # ── roteiro ──────────────────────────────────────────────────────────────
    rot_pt, _ = achar_roteiro("pt")
    rot_en, _ = achar_roteiro("en")

    # ── áudio ────────────────────────────────────────────────────────────────
    arq_aud_pt = achar_audio(PASTA_AUDIO, "pt") if PASTA_AUDIO.exists() else None
    arq_aud_en = achar_audio(PASTA_AUDIO, "en") if PASTA_AUDIO.exists() else None
    aud_pt = bool(arq_aud_pt)
    aud_en = bool(arq_aud_en)

    def _dur_audio_seguro(arq):
        """Retorna duração formatada ou None sem travar em caso de erro."""
        if not arq:
            return None
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(arq)],
                capture_output=True, text=True, encoding="utf-8", errors="ignore",
                creationflags=_NO_WINDOW
            )
            dur = float(json.loads(r.stdout)["format"]["duration"])
            return fmt_duracao(dur)
        except Exception:
            return None

    dur_pt = _dur_audio_seguro(arq_aud_pt) if aud_pt else None
    dur_en = _dur_audio_seguro(arq_aud_en) if aud_en else None

    # ── música ───────────────────────────────────────────────────────────────
    musicas = []
    if PASTA_MUSICA.exists():
        musicas = [p for p in PASTA_MUSICA.iterdir() if p.suffix.lower() in EXT_AUDIO]

    # ── top N detectado ──────────────────────────────────────────────────────
    top_n_det = _detectar_top_n()

    # ── último gerado ────────────────────────────────────────────────────────
    ultimo = _ultimo_historico()

    # ── banner principal ─────────────────────────────────────────────────────
    faltando = []
    if not imgs_ok:
        faltando.append("cenas (1.png…)")
    if not rot_pt:
        faltando.append("roteiro PT")
    if not rot_en:
        faltando.append("roteiro EN")
    if not aud_pt:
        faltando.append("áudio PT")
    if not aud_en:
        faltando.append("áudio EN")

    tudo_ok = len(faltando) == 0

    if tudo_ok:
        top_label = f"Top {top_n_det}" if top_n_det else "Top ?"
        n_ling = 2  # PT + EN
        est = _estimar_tempo_geracao(top_n_det or 10, n_ling) if top_n_det else ""
        est_str = f"  ·  {est}" if est else ""
        print(f"\n  {_verde('✅ PRONTO PARA GERAR')}  ·  {top_label}{est_str}")
    else:
        print(f"\n  {_vermelho('❌ FALTANDO')}")

    print()

    # ── linha: Cenas ─────────────────────────────────────────────────────────
    cenas_icon = "✅" if imgs_ok else "❌"
    cenas_range = f"1–{n_seq}" if n_seq > 0 else "nenhuma"
    doramas_str = f"   📚 {n_doramas} doramas" if n_doramas else ""
    temas_str = ""
    if temas or logos:
        parts = []
        if temas:
            parts.append(f"{len(temas)} tema(s)")
        if logos:
            parts.append(f"{len(logos)} logo(s)")
        temas_str = f"   🎨 {' · '.join(parts)}"
    print(f"  🖼  Cenas   {cenas_icon} {cenas_range}{doramas_str}{temas_str}")

    # ── linha: Roteiro ───────────────────────────────────────────────────────
    rot_pt_icon = "✅" if rot_pt else "❌"
    rot_en_icon = "✅" if rot_en else "❌"
    print(f"  📝  Roteiro {rot_pt_icon} PT  {rot_en_icon} EN")

    # ── linha: Áudio ─────────────────────────────────────────────────────────
    def _audio_str(ok, dur):
        if ok:
            return (_verde("✅") if _ansi_ok else "✅") + (f" {dur}" if dur else "")
        return (_vermelho("❌") if _ansi_ok else "❌")

    print(f"  🎧  Áudio   PT {_audio_str(aud_pt, dur_pt)}   EN {_audio_str(aud_en, dur_en)}")

    # ── linha: Música ────────────────────────────────────────────────────────
    if musicas:
        if _gv_s.MUSICA_MODO == "selecionar" and _gv_s.MUSICA_ATIVA:
            mus_str = f"🎵 {_gv_s.MUSICA_ATIVA}"
        else:
            mus_str = f"🎲 aleatório  ({len(musicas)} arquivo(s))"
        print(f"  🎵  Música  {mus_str}")

    # ── linha: Último gerado ─────────────────────────────────────────────────
    if ultimo:
        try:
            dt_ult = datetime.datetime.fromisoformat(ultimo["data"])
            hoje = datetime.datetime.now().date()
            if dt_ult.date() == hoje:
                hora_str = f"hoje {dt_ult.strftime('%H:%M')}"
            else:
                hora_str = dt_ult.strftime("%d/%m %H:%M")
            ling_ult = ultimo.get("lingua", "").upper()
            alin_ult = ultimo.get("alinhamento_pct")
            alin_str = f"  · alinhamento {alin_ult}%" if alin_ult is not None else ""
            print(f"  ⏱  Último  {hora_str} · {ling_ult}{alin_str}")
        except Exception:
            pass

    # ── linha: Faltando ──────────────────────────────────────────────────────
    if faltando:
        print(f"\n  {_vermelho('❌ Faltando:')} {' · '.join(faltando)}")


def menu_configuracoes():
    import engine as gv_mod

    # (nome, variável, tipo, descrição)
    opcoes = [
        ("Layout do vídeo",            "LAYOUT",                   "layout",
         "como as imagens aparecem: padrão · tela cheia · card · número · dividido"),
        ("Fundo atrás das imagens",    "FUNDO",                    ["preto", "desfocado"],
         "preto sólido  ou  imagem original esticada e desfocada atrás"),
        ("Zoom nas imagens",           "ZOOM_MAXIMO",              "float",
         "0 = imagens paradas  |  0.06 = zoom lento de 6%  |  0.12 = zoom forte"),
        ("Zoom na abertura/fechamento","ZOOM_ABERTURA_FECHAMENTO",  ["Sim", "Não"],
         "aplicar o mesmo zoom na imagem de abertura e no fechamento"),
        ("Fade entre imagens",         "DURACAO_FADE",             "float",
         "0 = corte direto  |  0.2 = transição suave de 0.2s entre imagens"),
        ("Versão Instagram 4:5",       "GERAR_INSTA",              ["Sim", "Não"],
         "Sim = gera também o vídeo 1080×1350 para Instagram  |  Não = só o 9:16"),
        ("Palavras por legenda",       "PALAVRAS_POR_LEGENDA",     "int",
         "quantas palavras aparecem por vez na legenda do vídeo"),
        ("Posição da legenda",         "POSICAO_LEGENDA",          "int",
         "distância em pixels do fundo da tela  ex: 300 = legenda mais alta"),
        ("Cor da legenda",             "COR_LEGENDA",              list(_CORES_LEGENDA.keys()),
         "cor do texto de legenda queimado dentro do vídeo"),
        ("Bounce da legenda",          "BOUNCE_LEGENDA",           ["Sim", "Não"],
         "Sim = cada palavra aparece com animação de pop  |  Não = aparece direto"),
        ("Modelo Whisper",             "MODELO_WHISPER",           ["base", "small", "medium"],
         "base = mais rápido  |  small = bom equilíbrio  |  medium = mais preciso"),
        ("Velocidade de compressão",   "FFMPEG_PRESET_FINAL",      ["ultrafast", "fast", "medium", "slow"],
         "ultrafast = gera rápido/arquivo grande  |  slow = demora/arquivo menor"),
        ("Qualidade do vídeo final",   "FFMPEG_CRF_FINAL",         "int",
         "18 = alta qualidade  |  20 = padrão  |  28 = arquivo bem menor"),
        ("Duração do preview",         "PREVIEW_DURACAO",          "int",
         "quantos segundos são gerados no modo preview (opção 6 do menu)"),
        ("Gerar arquivo .srt",         "GERAR_SRT",                ["Sim", "Não"],
         "Sim = salva legendas em .srt junto com o vídeo  |  Não = só o .mp4"),
        ("Salvar frames dos itens",    "SALVAR_FRAMES",            ["Sim", "Não"],
         "Sim = salva frame PNG de cada item em videos/frames/  |  Não = desativado"),
        ("Volume da música",           "VOLUME_MUSICA",            "float",
         "0 = mudo  |  0.10 = bem baixinho  |  1.0 = volume total"),
        ("Cor do menu",                "TEMA_MENU",                list(_TEMAS_MENU.keys()),
         "tema de cor das barras e títulos do menu no terminal"),
        ("Cor de fundo (card)",        "COR_FUNDO_CARD",           "str",
         "cor hex do fundo nos layouts Card e Dividido  ex: 1a1a2e = azul escuro"),
        ("Logo — posição X",           "LOGO_X",                   "int",
         "distância em px da borda esquerda  ex: 20 = bem à esquerda"),
        ("Logo — posição Y",           "LOGO_Y",                   "int",
         "distância em px do topo  ex: 248 = abaixo da borda superior"),
        ("Logo — largura",             "LARGURA_LOGO",             "int",
         "largura do logo em px no vídeo (altura é proporcional)  ex: 340"),
    ]

    # grupos: (emoji, título, índices baseados em 0 na lista opcoes)
    _GRUPOS = [
        ("🎬", "VÍDEO",      [0, 1, 2, 3, 4, 5]),
        ("🔤", "LEGENDA",    [6, 7, 8, 9]),
        ("⚙️ ", "GERAÇÃO",   [10, 11, 12, 13, 14, 15]),
        ("🎵", "MÚSICA",     [16]),
        ("🎨", "INTERFACE",  [17, 18]),
        ("📐", "POSIÇÕES",   [19, 20, 21]),
    ]

    bool_vars = {"ZOOM_ABERTURA_FECHAMENTO", "GERAR_INSTA", "GERAR_SRT", "BOUNCE_LEGENDA", "SALVAR_FRAMES"}

    while True:
        limpar()
        cor = _c()
        W = 50
        bar  = "━" * W
        thin = "─" * W
        print(f"{cor}{bar}{_r()}")
        print(f"{cor}  ⚙️   CONFIGURAÇÕES{_r()}")
        print(f"{cor}{bar}{_r()}")
        num = 1
        idx_map = {}   # número exibido → índice em opcoes
        for emoji, titulo, indices in _GRUPOS:
            print(f"\n  {emoji}  {titulo}")
            for i in indices:
                nome, var, _, _ = opcoes[i]
                valor = getattr(gv_mod, var)
                if var in bool_vars:
                    valor = "Sim" if valor else "Não"
                print(f"  [{num:>2}] {nome:<32} {valor}")
                idx_map[num] = i
                num += 1
        print(f"\n  [0]  Voltar")
        print(f"{cor}{bar}{_r()}")
        escolha = _input_gui("  → ").strip()
        if escolha == "0":
            return
        if not escolha.isdigit() or int(escolha) not in idx_map:
            continue

        idx = idx_map[int(escolha)]
        nome, var, tipo, desc = opcoes[idx]
        print(f"\n  {nome}")
        print(f"  {desc}\n")
        atual = getattr(gv_mod, var)

        if tipo == "layout":
            print()
            for i, (k, desc) in enumerate(LAYOUTS.items(), 1):
                marca = "◀" if k == atual else " "
                print(f"  [{i}] {desc} {marca}")
            esc2 = _input_gui("  → ").strip()
            if esc2.isdigit() and 1 <= int(esc2) <= len(LAYOUTS):
                novo = list(LAYOUTS.keys())[int(esc2) - 1]
                setattr(gv_mod, var, novo)
                print(f"  ✅ Layout → {LAYOUTS[novo].split('—')[0].strip()}")
        elif isinstance(tipo, list):
            opts = tipo
            print(f"  {' / '.join(f'[{i+1}] {v}' for i, v in enumerate(opts))}")
            esc2 = _input_gui("  → ").strip()
            if esc2.isdigit() and 1 <= int(esc2) <= len(opts):
                novo = opts[int(esc2) - 1]
                if var in bool_vars:
                    novo = (novo == "Sim")
                setattr(gv_mod, var, novo)
                print(f"  ✅ {nome} → {novo}")
        elif tipo == "int":
            val = _input_gui(f"  Valor atual: {atual}. Novo: ").strip()
            if val.lstrip("-").isdigit():
                _LIMITES_INT = {
                    "FFMPEG_CRF_FINAL":       (0,   51),
                    "PALAVRAS_POR_LEGENDA":   (1,   20),
                    "POSICAO_LEGENDA":        (50, 800),
                    "PREVIEW_DURACAO":        (5,  300),
                    "LARGURA_LOGO":           (50, 600),
                    "LOGO_X":                 (0, 1080),
                    "LOGO_Y":                 (0, 1920),
                }
                novo_int = int(val)
                if var in _LIMITES_INT:
                    _min, _max = _LIMITES_INT[var]
                    if not (_min <= novo_int <= _max):
                        print(f"  ❌ Valor fora do intervalo ({_min}–{_max})")
                    else:
                        setattr(gv_mod, var, novo_int)
                        print(f"  ✅ {nome} → {val}")
                else:
                    setattr(gv_mod, var, novo_int)
                    print(f"  ✅ {nome} → {val}")
        elif tipo in ("float", "str"):
            val = _input_gui(f"  Valor atual: {atual}. Novo: ").strip()
            if val:
                try:
                    novo = float(val) if tipo == "float" else val
                    if tipo == "float":
                        _LIMITES_FLOAT = {
                            "ZOOM_MAXIMO":    (0.0, 0.3),
                            "VOLUME_MUSICA":  (0.0, 1.0),
                        }
                        if var in _LIMITES_FLOAT:
                            _min, _max = _LIMITES_FLOAT[var]
                            if not (_min <= novo <= _max):
                                print(f"  ❌ Valor fora do intervalo ({_min}–{_max})")
                                salvar_config()
                                _input_gui("  Enter para continuar...")
                                continue
                    setattr(gv_mod, var, novo)
                    print(f"  ✅ {nome} → {novo}")
                except ValueError:
                    print("  ❌ Valor inválido.")

        salvar_config()
        _input_gui("  Enter para continuar...")


# ------------------------- biblioteca de doramas -------------------------

def _normalizar_busca(texto):
    """Minúsculo, sem acento, sem pontuação — para comparação fuzzy."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[_\-/:,\.!?]", " ", texto)
    return " ".join(texto.split())


def _extrair_nomes_roteiro(top_n):
    """Lê os roteiros PT e EN e extrai o nome do dorama de cada posição (1..top_n).
    Retorna dict {n: {"pt": "nome", "en": "nome"}} com None quando não encontrado."""
    resultado = {n: {"pt": None, "en": None} for n in range(1, top_n + 1)}
    padrao = re.compile(r'^\s*(\d+)\s*[–\-]\s*([^:\n]+?)(?:\s*:|$)', re.MULTILINE)
    for lingua in ("pt", "en"):
        arq, _ = achar_roteiro(lingua)
        if not arq:
            continue
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        for m in padrao.finditer(texto):
            n = int(m.group(1))
            nome = m.group(2).strip().strip("*").strip()
            if 1 <= n <= top_n and nome and len(nome) > 1:
                if resultado[n][lingua] is None:
                    resultado[n][lingua] = nome
    return resultado


def _detectar_top_n():
    """Lê os roteiros e retorna o maior número de item encontrado (ou None)."""
    for lingua in ("pt", "en"):
        arq, _ = achar_roteiro(lingua)
        if not arq:
            continue
        try:
            texto = arq.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        nums = set()
        for m in re.finditer(r'^\s*(\d{1,2})\s*[–\-]', texto, re.MULTILINE):
            n = int(m.group(1))
            if 1 <= n <= 10:
                nums.add(n)
        if nums:
            return max(nums)
    return None


def _verificar_duplicatas_roteiro(top_n):
    """Avisa se houver doramas com nomes iguais em posições diferentes."""
    nomes = _extrair_nomes_roteiro(top_n)
    alertas = []
    for lingua in ("pt", "en"):
        vistos = {}
        for n in range(1, top_n + 1):
            nome = nomes[n][lingua]
            if not nome:
                continue
            norm = _normalizar_busca(nome)
            if norm in vistos:
                alertas.append(
                    f"  ⚠️  {lingua.upper()}: '{nome}' (pos {n}) parece igual a "
                    f"'{nomes[vistos[norm]][lingua]}' (pos {vistos[norm]})"
                )
            else:
                vistos[norm] = n
    for a in alertas:
        print(a)
    if alertas:
        resp = _input_gui("  Continuar mesmo assim? [S/N]: ", "s")
        if resp != "s":
            return False
    return True


def _verificar_espaco_disco():
    """Avisa se houver menos de 2 GB livres em disco."""
    try:
        _, _, free = shutil.disk_usage(PASTA)
        free_gb = free / (1024 ** 3)
        if free_gb < 2.0:
            print(f"\n  ⚠️  Pouco espaço em disco: {free_gb:.1f} GB disponível")
            print(f"     Recomendado: pelo menos 2 GB para gerar vídeos")
            resp = _input_gui("  Continuar mesmo assim? [S/N]: ", "s")
            return resp == "s"
    except Exception:
        pass
    return True


def _salvar_historico(entrada):
    """Adiciona entrada ao log historico.json em videos/."""
    arq = PASTA_SAIDA / "historico.json"
    try:
        historico = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    except Exception:
        historico = []
    historico.append(entrada)
    historico = historico[-200:]   # mantém só os últimos 200 registros
    try:
        PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(historico, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _estimar_tempo_geracao(top_n, n_linguas):
    """Retorna string com estimativa de tempo de geração (ex: '~15 min')."""
    try:
        import torch
        gpu = torch.cuda.is_available()
    except Exception:
        gpu = False
    # minutos por idioma (Whisper + render)
    whisper_min = {"base": (1, 0.3), "small": (3, 0.8), "medium": (6, 1.5)}.get(MODELO_WHISPER, (3, 0.8))
    wmin = whisper_min[1] if gpu else whisper_min[0]
    render_min = top_n * 0.4   # ~24s por trecho
    total = round((wmin + render_min) * n_linguas)
    return f"~{total} min" + (" (GPU)" if gpu else "")


def preparar_cenas_roteiro(top_n=10):
    """Copia imagens de doramas/ para cenas/ na ordem do roteiro (top_n → 1)."""
    limpar()
    _b = "━" * 50
    print(_b)
    print(f"  🎬  PREPARAR CENAS — Top {top_n}")
    print(_b)

    if not PASTA_DORAMAS.exists():
        PASTA_DORAMAS.mkdir()
        print(f"\n  📁 Pasta doramas/ criada.")
        print("     Coloque as imagens nomeadas com o título do dorama e rode novamente.")
        _input_gui("\n  Enter para voltar...")
        return

    exts = set(EXT_IMAGEM + EXT_VIDEO)
    biblioteca = [p for p in sorted(PASTA_DORAMAS.iterdir()) if p.suffix.lower() in exts]
    if not biblioteca:
        print("\n  ❌ Nenhuma imagem encontrada em doramas/")
        print("     Nomeie cada arquivo com o título do dorama (ex.: Pousando no Amor.png)")
        _input_gui("\n  Enter para voltar...")
        return

    print(f"\n  📂 {len(biblioteca)} imagem(ns) na biblioteca doramas/")
    print("  🔍 Buscando correspondências no roteiro...\n")

    nomes = _extrair_nomes_roteiro(top_n)
    norm_bib = [(p, _normalizar_busca(p.stem)) for p in biblioteca]

    matches = {}    # {n: (arquivo, score, nome_roteiro)}
    sem_match = []

    for n in range(top_n, 0, -1):
        nome_pt = nomes[n]["pt"]
        nome_en = nomes[n]["en"]
        melhor_arq, melhor_score, melhor_nome = None, 0.0, None

        for nome_orig in filter(None, [nome_pt, nome_en]):
            norm = _normalizar_busca(nome_orig)
            for arq, norm_arq in norm_bib:
                score = difflib.SequenceMatcher(None, norm, norm_arq).ratio()
                if score > melhor_score:
                    melhor_score, melhor_arq, melhor_nome = score, arq, nome_orig

        if melhor_arq and melhor_score >= 0.55:
            matches[n] = (melhor_arq, melhor_score, melhor_nome)
        else:
            sem_match.append((n, nome_pt, nome_en))

    # Relatório
    print("  Pos  Roteiro                              Arquivo                    Conf")
    print("  " + "─" * 74)
    for n in range(top_n, 0, -1):
        if n in matches:
            arq, score, nome = matches[n]
            icone = "✅" if score >= 0.80 else "⚠️ "
            print(f"  {icone} {n:>2}  {nome:<36} {arq.name:<26} {score:.0%}")
        else:
            npt = nomes[n]["pt"] or "?"
            nen = nomes[n]["en"] or "?"
            label = npt if npt != "?" else nen
            print(f"  ❌ {n:>2}  {label:<36} {'SEM CORRESPONDÊNCIA'}")
    print("  " + "─" * 74)

    if sem_match:
        print(f"\n  ⚠️  {len(sem_match)} dorama(s) sem imagem correspondente em doramas/")
        print("     Nomeie o arquivo com o título exato do roteiro e rode novamente.")

    if not matches:
        _input_gui("\n  Nenhuma correspondência encontrada. Enter para voltar...")
        return

    n_existem = sum(1 for n in matches if achar_arquivo(PASTA_IMAGENS, str(n), EXT_IMAGEM + EXT_VIDEO))
    if n_existem > 0:
        print(f"\n  ⚠️  Arquivos que serão sobrescritos em cenas/:")
        for n in range(top_n, 0, -1):
            if n not in matches:
                continue
            destino_check = PASTA_IMAGENS / f"{n}{matches[n][0].suffix.lower()}"
            if destino_check.exists():
                arq, score, nome = matches[n]
                print(f"     {destino_check.name}  ←  {arq.name}  ({score:.0%})")
    aviso_sobresc = f"  ⚠️  {n_existem} imagem(ns) já existem em cenas/ e serão sobrescritas.\n" if n_existem else ""
    print(f"\n{aviso_sobresc}  Copiar {len(matches)} imagem(ns) para cenas/? [S/N]: ", end="")
    resp = _input_gui().strip().lower()
    if resp != "s":
        print("  Cancelado.")
        _input_gui("  Enter para voltar...")
        return

    PASTA_IMAGENS.mkdir(exist_ok=True)
    copiados = 0
    for n in range(top_n, 0, -1):
        if n not in matches:
            continue
        arq, _, nome = matches[n]
        destino = PASTA_IMAGENS / f"{n}{arq.suffix.lower()}"
        shutil.copy2(str(arq), str(destino))
        copiados += 1
        print(f"  ✅ {n:>2} → {destino.name}  ({nome})")

    print(f"\n  ✅ {copiados} imagem(ns) copiada(s) para cenas/")
    print("     Os originais em doramas/ não foram alterados.")
    resp = _input_gui("\n  Aperte A para abrir cenas/ ou Enter para continuar: ").strip()
    if resp.lower() == "a":
        os.startfile(str(PASTA_IMAGENS))


def menu_tema_logo():
    import engine as _gv
    while True:
        limpar()
        cor = _c()
        temas = _listar_temas()
        logos = _listar_logos()

        _W = "━" * 50
        print(f"{cor}{_W}{_r()}")
        print(f"{cor}  🎨  TEMA E LOGO{_r()}")
        print(f"{cor}{_W}{_r()}")

        if not temas and not logos:
            print("\n  ⚠️  Nenhum tema ou logo encontrado.")
            print("  Crie as pastas e adicione os arquivos:")
            print()
            print("  temas/")
            print("    abertura_pt_1.png  fechamento_pt_1.png")
            print("    abertura_en_1.png  fechamento_en_1.png")
            print("    abertura_pt_2.png  fechamento_pt_2.png  ...")
            print()
            print("  logos/")
            print("    logo_1.png  logo_2.png  ...")
            PASTA_TEMAS.mkdir(exist_ok=True)
            PASTA_LOGOS.mkdir(exist_ok=True)
            print("\n  📁 Pastas temas/ e logos/ criadas.")
            _input_gui("\n  Enter para voltar...")
            return

        if temas:
            print(f"\n  Temas disponíveis : {' · '.join(str(n) for n in temas)}")
        if logos:
            print(f"  Logos disponíveis : {' · '.join(str(n) for n in logos)}")

        modos_label = {"padrao": "🎨 padrão (sempre o 1)", "aleatorio": "🎲 aleatório", "selecionar": "🎯 selecionar"}
        print(f"\n  Modo atual : {modos_label.get(_gv.MODO_TEMA, _gv.MODO_TEMA)}")
        if _gv.MODO_TEMA == "selecionar":
            print(f"               tema {_gv.TEMA_ATIVO} · logo {_gv.LOGO_ATIVA}")

        print()
        print("  [1]  Padrão  (sempre tema 1 e logo 1)")
        print("  [2]  Aleatório  (sorteia a cada vídeo)")
        print("  [3]  Selecionar  (escolher qual usar)")
        print("  [0]  Voltar")
        print(f"{cor}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{_r()}")
        op = _input_gui("  → ").strip()

        if op == "1":
            _gv.MODO_TEMA = "padrao"
            salvar_config()
            print("\n  ✅ Modo: padrão (sempre usa tema 1 e logo 1)")
            _input_gui("  Enter para voltar...")
            return
        elif op == "2":
            _gv.MODO_TEMA = "aleatorio"
            salvar_config()
            print("\n  ✅ Modo: aleatório — tema e logo sorteados a cada vídeo")
            _input_gui("  Enter para voltar...")
            return
        elif op == "3":
            if temas:
                print(f"\n  Temas: {' · '.join(str(n) for n in temas)}")
                t = _input_gui(f"  Qual tema? [{_gv.TEMA_ATIVO}] → ").strip()
                if t.isdigit() and int(t) in temas:
                    _gv.TEMA_ATIVO = int(t)
            if logos:
                print(f"\n  Logos: {' · '.join(str(n) for n in logos)}")
                l = _input_gui(f"  Qual logo? [{_gv.LOGO_ATIVA}] → ").strip()
                if l.isdigit() and int(l) in logos:
                    _gv.LOGO_ATIVA = int(l)
            _gv.MODO_TEMA = "selecionar"
            salvar_config()
            print(f"\n  ✅ Modo: selecionado — tema {_gv.TEMA_ATIVO} · logo {_gv.LOGO_ATIVA}")
            _input_gui("  Enter para voltar...")
            return
        elif op == "0":
            return


def testar_posicoes():
    """Gera um PNG de teste mostrando onde ficam logo e legenda no frame."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("\n  ❌ Pillow não instalado. Rode: pip install pillow")
        _input_gui("  Enter para voltar...")
        return

    limpar()
    cor = _c()
    W = 50
    bar = "━" * W
    print(f"{cor}{bar}{_r()}")
    print(f"{cor}  📐  TESTAR POSIÇÕES{_r()}")
    print(f"{cor}{bar}{_r()}")
    print(f"\n  Logo X={LOGO_X}  Y={LOGO_Y}  Largura={LARGURA_LOGO}px")
    print(f"  Legenda a {POSICAO_LEGENDA}px do fundo\n")

    # Cria frame base
    frame = Image.new("RGB", (LARGURA, ALTURA), (20, 20, 30))
    draw  = ImageDraw.Draw(frame)

    # Tenta usar a primeira imagem real de cenas/ como fundo
    img_teste = achar_arquivo(PASTA_IMAGENS, "1", EXT_IMAGEM)
    if img_teste:
        with Image.open(img_teste) as im:
            im = im.convert("RGB")
            # redimensiona para caber no layout padrão (78% da altura)
            caixa_h = int(ALTURA * 0.78)
            fator   = min(LARGURA / im.width, caixa_h / im.height)
            nw, nh  = int(im.width * fator), int(im.height * fator)
            im      = im.resize((nw, nh), Image.LANCZOS)
            ox = (LARGURA - nw) // 2
            oy = (ALTURA  - nh) // 2
            frame.paste(im, (ox, oy))
    else:
        # placeholder cinza com grade
        draw.rectangle([0, 0, LARGURA - 1, ALTURA - 1], outline=(80, 80, 80), width=2)
        for x in range(0, LARGURA, 108):
            draw.line([(x, 0), (x, ALTURA)], fill=(40, 40, 50), width=1)
        for y in range(0, ALTURA, 192):
            draw.line([(0, y), (LARGURA, y)], fill=(40, 40, 50), width=1)
        draw.text((LARGURA // 2 - 80, ALTURA // 2), "sem imagem em cenas/",
                  fill=(120, 120, 120))

    # Cola o logo real se existir
    logo_src, _ = preparar_logo()
    if logo_src and Path(logo_src).exists():
        with Image.open(logo_src).convert("RGBA") as logo_img:
            frame.paste(logo_img, (LOGO_X, LOGO_Y), logo_img)
        Path(logo_src).unlink(missing_ok=True)
    else:
        # Placeholder do logo
        draw.rectangle([LOGO_X, LOGO_Y, LOGO_X + LARGURA_LOGO, LOGO_Y + 60],
                       fill=(200, 50, 50), outline=(255, 100, 100), width=2)
        draw.text((LOGO_X + 8, LOGO_Y + 18), f"LOGO ({LARGURA_LOGO}px)", fill=(255, 255, 255))

    # Marcador da posição da legenda
    leg_y = ALTURA - POSICAO_LEGENDA
    draw.line([(0, leg_y), (LARGURA, leg_y)], fill=(255, 255, 0), width=2)
    draw.rectangle([LARGURA // 2 - 160, leg_y - 38, LARGURA // 2 + 160, leg_y - 4],
                   fill=(0, 0, 0, 180))
    draw.text((LARGURA // 2 - 140, leg_y - 34),
              f"LEGENDA  ({POSICAO_LEGENDA}px do fundo)", fill=(255, 255, 0))

    # Marcadores de borda e centro para referência
    draw.line([(LARGURA // 2, 0), (LARGURA // 2, ALTURA)], fill=(60, 60, 80), width=1)
    draw.text((4, 4), f"{LARGURA}×{ALTURA}  Layout: {LAYOUT}", fill=(150, 150, 180))

    # Salva PNG
    PASTA_SAIDA.mkdir(exist_ok=True)
    destino_png = PASTA_SAIDA / "teste_posicoes.png"
    frame.save(destino_png)

    # Gera MP4 de 5 segundos com logo e legenda de exemplo
    destino_mp4 = PASTA_SAIDA / "teste_posicoes.mp4"
    destino_mp4_ok = False
    try:
        if shutil.which("ffmpeg"):
            # Salva frame base como PNG temporário para o ffmpeg
            fd_bg, bg_path = tempfile.mkstemp(suffix=".png", prefix="rnk_test_bg_")
            os.close(fd_bg)
            frame.save(bg_path)

            # Escreve ASS temporário com uma legenda de exemplo
            ass_tmp = PASTA_SAIDA / "teste_posicoes_tmp.ass"
            cor = _CORES_LEGENDA.get(COR_LEGENDA, COR_TEXTO)
            bounce = "{\\fscx0\\fscy0\\t(0,120,\\fscx110\\fscy110)\\t(120,220,\\fscx100\\fscy100)}" if BOUNCE_LEGENDA else ""
            ass_conteudo = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {LARGURA}
PlayResY: {ALTURA}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Padrao,{FONTE},{TAMANHO_FONTE},{cor},{cor},{COR_CONTORNO},&H80000000,{-1 if NEGRITO else 0},0,0,0,100,100,0,0,1,{CONTORNO},{SOMBRA},2,60,60,{POSICAO_LEGENDA},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:04.50,Padrao,,0,0,0,,{bounce}Exemplo de legenda
"""
            ass_tmp.write_text(ass_conteudo, encoding="utf-8")

            logo_src2, _ = preparar_logo()
            if logo_src2 and Path(logo_src2).exists():
                cmd_mp4 = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-framerate", str(FPS), "-t", "5", "-i", bg_path,
                    "-i", str(logo_src2),
                    "-filter_complex",
                    f"[0:v]ass={ass_tmp}[va];[va][1:v]overlay={LOGO_X}:{LOGO_Y}[v_out]",
                    "-map", "[v_out]",
                    "-t", "5", "-r", str(FPS), "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p",
                    str(destino_mp4)
                ]
            else:
                cmd_mp4 = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-framerate", str(FPS), "-t", "5", "-i", bg_path,
                    "-vf", f"ass={ass_tmp}",
                    "-t", "5", "-r", str(FPS), "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p",
                    str(destino_mp4)
                ]
            r_mp4 = subprocess.run(cmd_mp4, capture_output=True, text=True,
                                   encoding="utf-8", errors="ignore",
                                   creationflags=_NO_WINDOW)
            destino_mp4_ok = r_mp4.returncode == 0 and destino_mp4.exists()
            try:
                Path(bg_path).unlink(missing_ok=True)
                ass_tmp.unlink(missing_ok=True)
                if logo_src2:
                    Path(logo_src2).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  Não foi possível gerar MP4 de teste: {e}")

    print(f"  ✅ [A] Frame PNG : {destino_png}")
    if destino_mp4_ok:
        print(f"  ✅ [B] Vídeo MP4 : {destino_mp4}  (5s com legenda animada)")
    print(f"\n  Ajuste as posições em  Configurações → POSIÇÕES")
    print(f"  e rode novamente para ver o resultado.\n")
    opcoes = "A (PNG)" + (" / B (MP4)" if destino_mp4_ok else "") + " / Enter (voltar)"
    resp = _input_gui(f"  Aperte {opcoes}: ").strip().lower()
    if resp == "a":
        os.startfile(str(destino_png))
    elif resp == "b" and destino_mp4_ok:
        os.startfile(str(destino_mp4))


def menu_musica():
    """Menu de seleção de música de fundo."""
    import engine as _gv
    while True:
        limpar()
        cor = _c()
        W = 50
        bar = "━" * W
        print(f"{cor}{bar}{_r()}")
        print(f"{cor}  🎵  MÚSICA DE FUNDO{_r()}")
        print(f"{cor}{bar}{_r()}")

        musicas = []
        if PASTA_MUSICA.exists():
            musicas = sorted([p for p in PASTA_MUSICA.iterdir() if p.suffix.lower() in EXT_AUDIO],
                             key=lambda p: p.name.lower())

        n_arq = len(musicas)
        print(f"\n  Pasta: projeto/musica/  ({n_arq} arquivo(s))\n")

        if not musicas:
            print("  Nenhuma música encontrada em projeto/musica/")
            print("  Coloque arquivos .mp3 ou .wav nessa pasta.")
        else:
            for i, m in enumerate(musicas, 1):
                marca = "  ◀ atual" if (_gv.MUSICA_MODO == "selecionar" and _gv.MUSICA_ATIVA == m.name) else ""
                print(f"  [{i}]  {m.name}{marca}")

        print()
        aleatorio_marca = "  ◀ atual" if _gv.MUSICA_MODO == "aleatorio" else ""
        print(f"  [A]  Aleatório  (sorteia a cada vídeo){aleatorio_marca}")
        print(f"  [0]  Voltar")
        print(f"{cor}{bar}{_r()}")
        op = _input_gui("  → ").strip()

        if op == "0":
            return
        elif op.lower() == "a":
            _gv.MUSICA_MODO = "aleatorio"
            _gv.MUSICA_ATIVA = ""
            salvar_config()
            print("\n  ✅ Modo: aleatório — sorteia a cada vídeo")
            _input_gui("  Enter para continuar...")
        elif op.isdigit():
            idx = int(op) - 1
            if 0 <= idx < len(musicas):
                _gv.MUSICA_MODO = "selecionar"
                _gv.MUSICA_ATIVA = musicas[idx].name
                salvar_config()
                print(f"\n  ✅ Música selecionada: {_gv.MUSICA_ATIVA}")
                _input_gui("  Enter para continuar...")


def main():
    _habilitar_ansi()
    carregar_config()

    # ── Modo GUI: chamado com argumentos pelo GeradorBB.exe ───────────────────
    import argparse as _ap
    _parser = _ap.ArgumentParser(add_help=False)
    _parser.add_argument("--projeto-dir",   default=None)
    _parser.add_argument("--preview",       action="store_true")
    _parser.add_argument("--linguas",       nargs="+", default=["pt"])
    _parser.add_argument("--template-file", default=None)
    _args, _ = _parser.parse_known_args()

    if _args.projeto_dir:
        # Atualiza os caminhos globais para o projeto selecionado no GUI
        global PASTA, PASTA_PROJETO, PASTA_IMAGENS, PASTA_ROTEIRO, PASTA_AUDIO
        global PASTA_MUSICA, PASTA_DORAMAS, PASTA_TEMAS, PASTA_LOGOS, PASTA_BORDAS
        global PASTA_SAIDA
        PASTA               = Path(_args.projeto_dir)
        PASTA_PROJETO       = PASTA / "projeto"
        PASTA_IMAGENS       = PASTA_PROJETO / "cenas"
        PASTA_ROTEIRO       = PASTA_PROJETO / "roteiro"
        PASTA_AUDIO         = PASTA_PROJETO / "audio"
        PASTA_MUSICA        = PASTA_PROJETO / "musica"
        PASTA_DORAMAS       = PASTA_PROJETO / "doramas"
        PASTA_TEMAS         = PASTA_PROJETO / "temas"
        PASTA_LOGOS         = PASTA_PROJETO / "logos"
        PASTA_BORDAS        = PASTA_PROJETO / "bordas"
        PASTA_SAIDA         = PASTA / "videos"

        # ── Carrega posições salvas no Preview/Layout (config_video.json) ────────
        global LOGO_X, LOGO_Y, LARGURA_LOGO, POSICAO_LEGENDA, TAMANHO_FONTE, MARCA_X, MARCA_Y
        global BORDA_ARQUIVO, BORDA_ATIVA
        _cv_path = PASTA / "config_video.json"
        if _cv_path.exists():
            try:
                import json as _json_cv
                _cv = _json_cv.loads(_cv_path.read_text(encoding="utf-8"))
                if "logo_x"          in _cv: LOGO_X          = int(_cv["logo_x"])
                if "logo_y"          in _cv: LOGO_Y          = int(_cv["logo_y"])
                if "logo_largura"    in _cv: LARGURA_LOGO    = int(_cv["logo_largura"])
                if "posicao_legenda" in _cv: POSICAO_LEGENDA = int(_cv["posicao_legenda"])
                if "tamanho_fonte"   in _cv: TAMANHO_FONTE   = int(_cv["tamanho_fonte"])
                if "marca_x"         in _cv: MARCA_X         = int(_cv["marca_x"])
                if "marca_y"         in _cv: MARCA_Y         = int(_cv["marca_y"])
                if "borda_arquivo"   in _cv: BORDA_ARQUIVO   = str(_cv["borda_arquivo"])
                if "borda_ativa"     in _cv: BORDA_ATIVA     = bool(_cv["borda_ativa"])
            except Exception as _e_cv:
                print(f"  ⚠️  config_video.json: {_e_cv}")

        # ── Informa ao personagem.py qual é o projeto ativo ──────────────────────
        # personagem.py lê o personagem_config.json com base nessa variável
        import os as _os_env
        _os_env.environ["GERADORBB_PROJETO_DIR"] = str(PASTA)

        # Carrega template se fornecido
        _tmpl = None
        if _args.template_file:
            _tmpl = _carregar_template_arquivo(_args.template_file)
            if _tmpl:
                print(f"  📋 Template: {_tmpl.get('icone','')} {_tmpl.get('nome','')}"
                      f"  [{_tmpl.get('tipo','livre')}]")

        duracao = PREVIEW_DURACAO if _args.preview else None
        resultado = gerar_videos(_args.linguas, duracao_max=duracao, template=_tmpl)
        sys.exit(0 if resultado is not False else 1)
    # ─────────────────────────────────────────────────────────────────────────

    import engine as _gv_ref
    while True:
        limpar()
        cor = _c()
        W = 50
        bar  = "━" * W
        thin = _cinza("─" * W)
        print(f"{cor}{bar}{_r()}")
        print(f"{cor}  🎬  R A N K A D O R A M A{_r()}")
        print(f"{cor}{bar}{_r()}")
        status_pastas()
        print()
        print(thin)
        print(f"  {_cinza('GERAR')}")
        print(f"  [1]  PT + EN      [2]  Só PT      [3]  Só EN")
        print(thin)
        print(f"  {_cinza('FERRAMENTAS')}")
        print(f"  [4]  Preparar cenas do roteiro")
        print(f"  [5]  Tema / Logo")
        print(f"  [6]  Preview rápido  ({_gv_ref.PREVIEW_DURACAO}s)")
        print(f"  [9]  Testar posições")
        print(f"  [10] Música de fundo")
        print(thin)
        print(f"  [8]  Configurações       [0]  Sair")
        print(f"{cor}{bar}{_r()}")
        print(_cinza("  Enter=PT+EN · P=PT · E=EN"))
        opcao = _input_gui("  → ").strip()

        # Atalhos de teclado
        if opcao == "":
            opcao = "1"
        elif opcao.lower() == "p":
            opcao = "2"
        elif opcao.lower() == "e":
            opcao = "3"
        elif opcao.lower() == "a":
            opcao = "1"

        if opcao in ("1", "2", "3", "4", "6"):
            # Tenta detectar Top N automaticamente
            _det = _detectar_top_n()
            if _det is not None:
                top_n = _det
                n_ling = 2 if opcao == "1" else 1
                print(f"\n  📋 Top {top_n} detectado no roteiro")
            else:
                # Exibe submenu somente quando não foi possível detectar
                limpar()
                print(f"{cor}{bar}{_r()}")
                print(f"{cor}  ▶  QUANTOS ITENS NO RANKING?{_r()}")
                print(f"{cor}{bar}{_r()}")
                n_ling = 2 if opcao == "1" else 1
                est10 = _estimar_tempo_geracao(10, n_ling)
                est5  = _estimar_tempo_geracao(5,  n_ling)
                print(f"\n  [1]  Top 10   {est10}   (padrão)")
                print(f"  [2]  Top 5    {est5}")
                print(f"  [0]  Voltar")
                print(f"\n{cor}{bar}{_r()}")
                t = _input_gui("  → ").strip()
                if t == "0":
                    continue
                top_n = 5 if t == "2" else 10

        if opcao == "1":
            linguas_label = "PT + EN"
            linguas = ["pt", "en"]
        elif opcao == "2":
            linguas_label = "PT"
            linguas = ["pt"]
        elif opcao == "3":
            linguas_label = "EN"
            linguas = ["en"]

        if opcao in ("1", "2", "3"):
            n_ling = len(linguas)
            est = _estimar_tempo_geracao(top_n, n_ling)
            limpar()
            print(f"{cor}{bar}{_r()}")
            print(f"{cor}  🎬  GERANDO  {linguas_label}  ·  Top {top_n}{_r()}")
            print(f"{cor}{bar}{_r()}")
            print(f"  Layout: {_gv_ref.LAYOUT}  ·  Whisper: {_gv_ref.MODELO_WHISPER}  ·  Est. {est}")
            print(f"{cor}{bar}{_r()}")
            gerar_videos(linguas, top_n=top_n)
        elif opcao == "4":
            preparar_cenas_roteiro(top_n)
        elif opcao == "5":
            menu_tema_logo()
        elif opcao == "6":
            limpar()
            n_ling_prev = 2  # preview sempre oferece PT+EN
            est_prev = _estimar_tempo_geracao(top_n, 1)
            print(f"{cor}{bar}{_r()}")
            print(f"{cor}  ▶  PREVIEW RÁPIDO  ·  Top {top_n}  ·  {_gv_ref.PREVIEW_DURACAO}s{_r()}")
            print(f"{cor}     ultrafast · qualidade reduzida · sem .srt{_r()}")
            print(f"{cor}{bar}{_r()}")
            print(f"\n  [1] PT + EN   [2] Só PT   [3] Só EN   [0] Voltar\n")
            sub = _input_gui("  → ").strip()
            if sub == "1":
                gerar_videos(["pt", "en"], duracao_max=_gv_ref.PREVIEW_DURACAO, top_n=top_n)
            elif sub == "2":
                gerar_videos(["pt"], duracao_max=_gv_ref.PREVIEW_DURACAO, top_n=top_n)
            elif sub == "3":
                gerar_videos(["en"], duracao_max=_gv_ref.PREVIEW_DURACAO, top_n=top_n)
        elif opcao == "8":
            menu_configuracoes()
        elif opcao == "9":
            testar_posicoes()
        elif opcao == "10":
            menu_musica()
        elif opcao == "0":
            sys.exit(0)
        else:
            print("  Opção inválida.")
            _input_gui("  Enter para continuar...")


if __name__ == "__main__":
    main()
