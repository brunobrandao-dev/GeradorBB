"""
Mascote Ranka — PNGtuber animado para o Rankadorama.
Usa pares de PNG (boca aberta / fechada) por pose.
Interface pública idêntica a personagem.py.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_CFG_PATH = Path(__file__).resolve().parent / "mascote_config.json"

# Incrementar para invalidar cache quando o algoritmo de processamento mudar
_CACHE_VERSION = "v3"

_DEFAULTS = {
    "ativo":            True,
    "largura_pct":      0.22,
    "lado":             "esquerda",
    "margem_esquerda":  20,
    "margem_direita":   20,
    "margem_fundo":     0,
    "volume_limite":    0.03,
    "pausa_min_s":      0.09,   # debounce ~90 ms
    "bob_amplitude_px": 4,
    "bob_hz":           0.7,
    "pulo_amplitude_px": 18,
    "pulo_duracao_s":   0.30,
    # Efeitos visuais
    "outline_px":       3,      # espessura do contorno escuro (0 = desativado)
    "sombra_ativa":     True,   # sombra projetada para profundidade
}

# Mapeamento nome_pose → (arquivo_boca_fechada, arquivo_boca_aberta)
# Sem extensão; aceita .png .jpg .jpeg .webp
_MAPA_POSES = {
    "falando":            ("ranka_falando_boca_fechada",           "ranka_falando_boca_aberta"),
    "apontando_esquerda": ("ranka_apontando_esquerda_boca_fechada","ranka_apontando_esquerda_boca_aberta"),
    "apontando_direita":  ("ranka_apontando_direita_boca_fechada", "ranka_apontando_direita_boca_aberta"),
}
# Nomes alternativos aceitos (aliases → nome_canônico)
_ALIASES = {
    "ranka_apontando_esquerda_boca_fechada": ["ranka_base"],
}
_EXTS = [".png", ".jpg", ".jpeg", ".webp"]


# ── Config ─────────────────────────────────────────────────────────────────────

def cfg() -> dict:
    c = dict(_DEFAULTS)
    if _CFG_PATH.exists():
        try:
            c.update(json.loads(_CFG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return c


# ── Remoção de fundo ──────────────────────────────────────────────────────────

def _remover_fundo_branco(img_pil):
    """Remove apenas o fundo conectado às bordas da imagem.
    Usa flood-fill (connected components) para não remover partes internas
    do personagem que tenham cor semelhante ao fundo (ex.: headphones azuis).
    Se a imagem já tiver canal alpha com transparência real, retorna sem processar.
    Retorna PIL RGBA com bordas suaves."""
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy.ndimage import label, binary_dilation

    rgba = img_pil.convert("RGBA")

    # PNG já com fundo transparente — pula a remoção de fundo
    arr_check = np.array(rgba)
    if arr_check[:, :, 3].min() < 200:
        return rgba
    data = np.array(rgba, dtype=np.float32)
    h, w = data.shape[:2]

    # Detecta cor real do fundo pelos cantos
    sz = max(8, min(h, w) // 12)
    corners = np.vstack([
        data[:sz,  :sz,  :3].reshape(-1, 3),
        data[:sz,  -sz:, :3].reshape(-1, 3),
        data[-sz:, :sz,  :3].reshape(-1, 3),
        data[-sz:, -sz:, :3].reshape(-1, 3),
    ])
    bg = np.median(corners, axis=0)

    r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]
    dist = np.sqrt((r - bg[0])**2 + (g - bg[1])**2 + (b - bg[2])**2)

    # Limiar generoso para capturar fundo com gradiente/compressão JPEG
    THRESH = 38.0

    # Máscara binária: candidatos a fundo
    bg_cand = dist < THRESH

    # ── Flood-fill: manter só componentes conectadas às bordas ────────────────
    labeled, _ = label(bg_cand)

    # Labels que tocam qualquer borda da imagem
    border_labels = set()
    border_labels.update(labeled[0,  :].flat)
    border_labels.update(labeled[-1, :].flat)
    border_labels.update(labeled[:,  0].flat)
    border_labels.update(labeled[:, -1].flat)
    border_labels.discard(0)  # 0 = não é fundo

    true_bg = np.isin(labeled, list(border_labels))

    # ── Suaviza a máscara nas bordas ──────────────────────────────────────────
    # Dilata ligeiramente para capturar pixels de transição (antialiasing JPEG)
    true_bg_d = binary_dilation(true_bg, iterations=2)

    # Mapa de distância suave: pixels na zona de transição recebem alpha parcial
    FEATHER = 20.0
    alpha_raw = np.clip((dist - THRESH) / FEATHER * 255, 0, 255)
    # Pixels inequivocamente fundo: forçar transparente
    alpha_raw[true_bg]   = 0
    # Pixels de transição (dilatados mas não fundo puro): manter gradiente
    alpha_raw[~true_bg_d] = 255  # interior do personagem → totalmente opaco

    alpha_u8 = alpha_raw.clip(0, 255).astype(np.uint8)

    # Suaviza somente as bordas (não afeta interior)
    alpha_img = Image.fromarray(alpha_u8, "L")
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(1.2))

    data[:, :, 3] = np.array(alpha_img, dtype=np.uint8)
    return Image.fromarray(data.astype(np.uint8), "RGBA")


# ── Efeitos visuais (outline + sombra) ───────────────────────────────────────

def _adicionar_efeitos(img_rgba, outline_px: int = 3, sombra: bool = True):
    """Adiciona contorno escuro e sombra projetada para melhor presença visual.
    Retorna PIL RGBA com canvas ligeiramente maior (inclui sombra)."""
    import numpy as np
    from PIL import Image, ImageFilter

    OUTLINE_COR = (15, 15, 15)   # quase preto
    OUTLINE_A   = 210            # opacidade do contorno
    SOMBRA_DX   = 4
    SOMBRA_DY   = 7
    SOMBRA_BLUR = 6
    SOMBRA_A    = 130            # opacidade da sombra

    PAD = outline_px + SOMBRA_BLUR + max(abs(SOMBRA_DX), abs(SOMBRA_DY)) + 3
    w, h = img_rgba.size
    W, H = w + PAD * 2, h + PAD * 2

    alpha_orig = img_rgba.split()[3]

    # ── Sombra ─────────────────────────────────────────────────────────────────
    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if sombra:
        sombra_alpha = Image.new("L", (W, H), 0)
        sombra_alpha.paste(alpha_orig, (PAD + SOMBRA_DX, PAD + SOMBRA_DY))
        sombra_alpha = sombra_alpha.filter(ImageFilter.GaussianBlur(SOMBRA_BLUR))
        sombra_arr = (np.array(sombra_alpha) * SOMBRA_A / 255).astype(np.uint8)
        sombra_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sombra_img.putalpha(Image.fromarray(sombra_arr))
        result = Image.alpha_composite(result, sombra_img)

    # ── Contorno ───────────────────────────────────────────────────────────────
    if outline_px > 0:
        alpha_canvas = Image.new("L", (W, H), 0)
        alpha_canvas.paste(alpha_orig, (PAD, PAD))
        dilated = alpha_canvas.filter(ImageFilter.MaxFilter(outline_px * 2 + 1))
        ring_arr = np.clip(
            np.array(dilated).astype(np.int16) - np.array(alpha_canvas).astype(np.int16),
            0, 255
        ).astype(np.uint8)
        ring_alpha = (ring_arr.astype(np.float32) * OUTLINE_A / 255).astype(np.uint8)
        outline_img = Image.new("RGBA", (W, H), (*OUTLINE_COR, 0))
        outline_img.putalpha(Image.fromarray(ring_alpha))
        result = Image.alpha_composite(result, outline_img)

    # ── Personagem ─────────────────────────────────────────────────────────────
    char_canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    char_canvas.paste(img_rgba, (PAD, PAD), img_rgba)
    result = Image.alpha_composite(result, char_canvas)
    return result


# ── Alinhamento do par boca ────────────────────────────────────────────────────

def _alinhar_par(img_fechada, img_aberta):
    """Alinha os dois PNGs pelo centro de massa dos pixels não-transparentes.
    Retorna (img_fechada_alinhada, img_aberta_alinhada) no mesmo tamanho de canvas."""
    import numpy as np
    from PIL import Image

    def _cm(img):
        arr = np.array(img, dtype=np.float32)
        a = arr[:, :, 3]
        total = a.sum()
        if total < 1:
            return img.height / 2.0, img.width / 2.0
        cy = (a * np.arange(img.height)[:, None]).sum() / total
        cx = (a * np.arange(img.width)[None, :]).sum() / total
        return cy, cx

    cy_f, cx_f = _cm(img_fechada)
    cy_a, cx_a = _cm(img_aberta)
    dy = int(round(cy_f - cy_a))
    dx = int(round(cx_f - cx_a))

    # Canvas grande o suficiente para ambos após deslocamento
    W = max(img_fechada.width,  img_aberta.width  + abs(dx)) + abs(dx) + 4
    H = max(img_fechada.height, img_aberta.height + abs(dy)) + abs(dy) + 4

    def _colocar(img, ox, oy):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c.paste(img, (max(0, ox), max(0, oy)), img)
        return c

    # Posição base para "fechada" (centrada)
    ox_f = (W - img_fechada.width)  // 2
    oy_f = (H - img_fechada.height) // 2
    # Posição "aberta" deslocada para alinhar centros
    ox_a = ox_f + dx
    oy_a = oy_f + dy

    return _colocar(img_fechada, ox_f, oy_f), _colocar(img_aberta, ox_a, oy_a)


# ── Carregamento e cache de imagens ───────────────────────────────────────────

def _buscar_arquivo(pasta: Path, nome_base: str):
    """Procura arquivo por nome_base (+ aliases) em vários formatos."""
    candidatos = [nome_base] + _ALIASES.get(nome_base, [])
    for nome in candidatos:
        for ext in _EXTS:
            p = pasta / f"{nome}{ext}"
            if p.exists():
                return p
    return None


def _mtime(path):
    try:
        return path.stat().st_mtime if path else 0.0
    except Exception:
        return 0.0


def preparar_imagens(pasta: Path) -> dict:
    """Carrega, remove fundo, alinha pares e aplica efeitos visuais.
    Retorna {pose: (arr_fechada, arr_aberta)} — arrays uint8 RGBA (H, W, 4).
    Usa cache .npz (versionado) para acelerar rodadas seguintes."""
    import numpy as np
    from PIL import Image

    c = cfg()
    outline_px = int(c.get("outline_px", 3))
    sombra     = bool(c.get("sombra_ativa", True))

    cache_dir = pasta / "_cache_mascote"
    cache_dir.mkdir(parents=True, exist_ok=True)

    resultado = {}

    for pose, (nome_f, nome_a) in _MAPA_POSES.items():
        path_f = _buscar_arquivo(pasta, nome_f)
        path_a = _buscar_arquivo(pasta, nome_a)

        if path_f is None:
            continue  # pose indisponível sem boca fechada

        # Cache versionado (nome inclui _CACHE_VERSION para invalidar ao atualizar)
        cache_npz = cache_dir / f"{pose}_{_CACHE_VERSION}.npz"
        mtime_src = max(_mtime(path_f), _mtime(path_a))
        if cache_npz.exists() and cache_npz.stat().st_mtime >= mtime_src:
            try:
                npz = np.load(str(cache_npz))
                resultado[pose] = (npz["fechada"], npz["aberta"])
                continue
            except Exception:
                pass

        # ── Remove fundo ───────────────────────────────────────────────────────
        img_f = _remover_fundo_branco(Image.open(path_f))

        if path_a is not None:
            img_a = _remover_fundo_branco(Image.open(path_a))
            try:
                img_f_ok, img_a_ok = _alinhar_par(img_f, img_a)
            except Exception:
                W = max(img_f.width, img_a.width)
                H = max(img_f.height, img_a.height)
                def _pad(im):
                    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    c.paste(im, (0, 0), im)
                    return c
                img_f_ok, img_a_ok = _pad(img_f), _pad(img_a)
        else:
            # Avisa que a pose não terá animação de boca
            try:
                print(f"  ⚠️  Mascote: '{nome_a}' não encontrado — pose '{pose}' sem animação de boca")
            except UnicodeEncodeError:
                print(f"  [mascote] '{nome_a}' nao encontrado -- pose '{pose}' sem animacao de boca")
            img_f_ok = img_f
            img_a_ok = img_f.copy()

        # ── Efeitos visuais (outline + sombra) ────────────────────────────────
        # Aplicar em cada imagem do par mantém alinhamento (mesmo canvas expandido)
        img_f_ok = _adicionar_efeitos(img_f_ok, outline_px=outline_px, sombra=sombra)
        img_a_ok = _adicionar_efeitos(img_a_ok, outline_px=outline_px, sombra=sombra)

        arr_f = np.array(img_f_ok, dtype=np.uint8)
        arr_a = np.array(img_a_ok, dtype=np.uint8)

        try:
            np.savez_compressed(str(cache_npz), fechada=arr_f, aberta=arr_a)
        except Exception:
            pass

        resultado[pose] = (arr_f, arr_a)
        try:
            print(f"  🎭 Mascote: {pose} ({arr_f.shape[1]}×{arr_f.shape[0]}px) → cache")
        except UnicodeEncodeError:
            print(f"  [mascote] {pose} ({arr_f.shape[1]}x{arr_f.shape[0]}px) -> cache")

    return resultado


# ── Sincronização de boca ─────────────────────────────────────────────────────

def _calcular_boca_por_timestamps(tempos: list, n_frames: int, fps: float) -> list:
    """Abre boca durante cada palavra usando timestamps do Whisper.
    Muito mais preciso que análise de volume: garante abertura/fechamento
    palavra por palavra, com fechamento natural entre palavras."""
    boca = [False] * n_frames
    for item in tempos:
        if item is None:
            continue
        t_ini, t_fim = item
        # Fecha levemente antes do fim da palavra (gap natural entre palavras)
        duracao_palavra = t_fim - t_ini
        t_fim_efetivo = t_ini + duracao_palavra * 0.85
        f_ini = max(0, int(t_ini * fps))
        f_fim = min(n_frames, int(t_fim_efetivo * fps) + 1)
        for f in range(f_ini, f_fim):
            boca[f] = True
    return boca


def _calcular_boca_por_volume(audio_path: Path, n_frames: int, fps: float,
                               limite: float, pausa_min_s: float) -> list:
    """Fallback: abre boca por análise de amplitude do áudio."""
    import numpy as np
    r = subprocess.run(
        ["ffmpeg", "-i", str(audio_path),
         "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"],
        capture_output=True, creationflags=_NO_WIN,
    )
    amostras = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    spp = max(1.0, len(amostras) / n_frames)
    vol = [
        float(((amostras[int(i * spp):int((i + 1) * spp)] ** 2).mean() ** 0.5))
        if int((i + 1) * spp) > int(i * spp) else 0.0
        for i in range(n_frames)
    ]
    pausa_f = max(1, int(pausa_min_s * fps))
    raw = [v >= limite for v in vol]
    resultado, estado, pendente, cont = [], raw[0], raw[0], 0
    for v in raw:
        if v == pendente:
            cont += 1
        else:
            pendente, cont = v, 1
        if pendente != estado and cont >= pausa_f:
            estado, cont = pendente, 0
        resultado.append(estado)
    return resultado


# ── Posição do overlay ────────────────────────────────────────────────────────

def _salvar_posicao(path: Path, x: int, y: int):
    Path(str(path) + ".pos").write_text(f"{x},{y}", encoding="utf-8")


def ler_posicao(path: Path) -> tuple:
    pos_file = Path(str(path) + ".pos")
    if pos_file.exists():
        try:
            x, y = pos_file.read_text().split(",")
            return int(x), int(y)
        except Exception:
            pass
    return 0, 0


# ── Função principal ──────────────────────────────────────────────────────────

def gerar_overlay(audio_path, tempos, inicio_item, top_n,
                  duracao, fps, largura_video, altura_video,
                  posicao_legenda, saida_path, pasta_mascote) -> bool:
    """Gera overlay do mascote como MKV (PNG codec, canal alpha).
    Interface idêntica a personagem.gerar_overlay()."""
    import numpy as np
    from PIL import Image

    c = cfg()
    if not c.get("ativo", True):
        return False

    pasta = Path(pasta_mascote)
    if not pasta.exists():
        print(f"  ⚠️  Mascote: pasta não encontrada ({pasta}) — pulando.")
        return False

    # 1. Carregar imagens
    poses_raw = preparar_imagens(pasta)
    if not poses_raw:
        print("  ⚠️  Mascote: nenhuma imagem encontrada — pulando.")
        return False

    # 2. Dimensões: escalar para largura_pct do vídeo
    char_w = int(largura_video * c["largura_pct"])

    # Referência de proporção: pose "falando" ou a primeira disponível
    ref_arr = poses_raw.get("falando", next(iter(poses_raw.values())))[0]
    orig_h, orig_w = ref_arr.shape[:2]
    char_h = int(orig_h * char_w / orig_w)

    # Redimensionar todas as poses para char_w × char_h
    poses = {}
    for nome, (arr_f, arr_a) in poses_raw.items():
        img_f = Image.fromarray(arr_f, "RGBA").resize((char_w, char_h), Image.LANCZOS)
        img_a = Image.fromarray(arr_a, "RGBA").resize((char_w, char_h), Image.LANCZOS)
        poses[nome] = (np.array(img_f, dtype=np.uint8), np.array(img_a, dtype=np.uint8))

    # 3. Posição na tela
    lado = c.get("lado", "direita")
    if lado == "esquerda":
        px = c.get("margem_esquerda", 20)
    else:
        px = largura_video - char_w - c["margem_direita"]

    bob_amp  = c["bob_amplitude_px"]
    bob_hz   = c["bob_hz"]
    pulo_amp = c["pulo_amplitude_px"]
    pulo_dur = c["pulo_duracao_s"]

    # Canvas tem espaço extra acima para bob e pulo
    extra_topo = pulo_amp + bob_amp + 2
    FRAME_W = char_w
    FRAME_H = char_h + extra_topo

    py = max(0, altura_video - posicao_legenda - char_h - c["margem_fundo"])
    overlay_x = px
    overlay_y = py - extra_topo

    # 4. Timestamps → boca (mais preciso que volume: uma abertura por palavra)
    n_frames = int(math.ceil(duracao * fps))
    if tempos and any(t is not None for t in tempos):
        boca = _calcular_boca_por_timestamps(tempos, n_frames, fps)
    else:
        # Fallback: análise de volume quando não há timestamps
        print("  🎭 Analisando volume para sincronização de boca...", flush=True)
        boca = _calcular_boca_por_volume(
            Path(audio_path), n_frames, fps,
            c["volume_limite"], c["pausa_min_s"]
        )

    # 5. Pose por frame
    # Pose "apontando": para o lado contrário à posição do mascote
    pose_apontando = "apontando_direita" if lado == "esquerda" else "apontando_esquerda"
    if pose_apontando not in poses:
        # Tenta o outro lado, ou cai no falando
        outro = "apontando_esquerda" if pose_apontando == "apontando_direita" else "apontando_direita"
        pose_apontando = outro if outro in poses else None

    pose_falando = "falando" if "falando" in poses else next(iter(poses))

    # Mapeia cada segundo para item ou "falando"
    # Constrói segmentos: lista de (t_start, t_end, pose)
    segmentos = []
    for n in range(top_n, 0, -1):
        if n not in inicio_item:
            continue
        idx = inicio_item[n]
        if idx >= len(tempos) or not tempos[idx]:
            continue
        t_ini = tempos[idx][0]
        # Fim: próximo item ou seção "fim"
        t_fim = duracao
        if "fim" in inicio_item:
            idx_fim = inicio_item["fim"]
            if idx_fim < len(tempos) and tempos[idx_fim]:
                t_fim = min(t_fim, tempos[idx_fim][0])
        for m in range(n - 1, 0, -1):
            if m not in inicio_item:
                continue
            idx_m = inicio_item[m]
            if idx_m < len(tempos) and tempos[idx_m]:
                t_fim = min(t_fim, tempos[idx_m][0])
                break
        segmentos.append((t_ini, t_fim, pose_apontando or pose_falando))

    def _pose_em(t):
        for t_ini, t_fim, p in segmentos:
            if t_ini <= t < t_fim:
                return p
        return pose_falando

    poses_frame = [_pose_em(f / fps) for f in range(n_frames)]

    # 6. Pulos ao início de cada item
    pulo_dur_f = max(1, int(pulo_dur * fps))
    pulo_dy = [0] * n_frames
    for n in range(top_n, 0, -1):
        if n not in inicio_item:
            continue
        idx = inicio_item[n]
        if idx >= len(tempos) or not tempos[idx]:
            continue
        f0 = int(tempos[idx][0] * fps)
        for df in range(pulo_dur_f):
            f = f0 + df
            if f >= n_frames:
                break
            prog = df / pulo_dur_f
            dy = -int(pulo_amp * math.sin(math.pi * prog))   # arco para cima
            if abs(dy) > abs(pulo_dy[f]):
                pulo_dy[f] = dy

    # 7. Pipe FFmpeg → MKV PNG alpha
    print(f"  🎭 Gerando overlay mascote ({n_frames} frames, {char_w}×{char_h}px)...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{FRAME_W}x{FRAME_H}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "png", "-pix_fmt", "rgba",
        str(saida_path),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=_NO_WIN,
    )

    try:
        for f in range(n_frames):
            t = f / fps
            pose = poses_frame[f]
            arr_f, arr_a = poses.get(pose, next(iter(poses.values())))
            frame = arr_a if boca[f] else arr_f

            dy_bob  = int(bob_amp * math.sin(2 * math.pi * bob_hz * t))
            dy_pulo = pulo_dy[f]
            dy      = dy_bob + dy_pulo

            canvas = np.zeros((FRAME_H, FRAME_W, 4), dtype=np.uint8)
            oy = extra_topo + dy
            oy = max(0, min(oy, FRAME_H - char_h))
            h_p = min(char_h, FRAME_H - oy)
            w_p = min(char_w, FRAME_W)
            if h_p > 0 and w_p > 0:
                canvas[oy:oy + h_p, 0:w_p] = frame[:h_p, :w_p]

            proc.stdin.write(canvas.tobytes())

            if f % 300 == 0 and f > 0:
                print(f"     mascote: {f}/{n_frames} frames...", flush=True)

        proc.stdin.close()
        _, stderr = proc.communicate(timeout=300)

        if proc.returncode != 0:
            errtxt = stderr.decode("utf-8", errors="ignore")[-500:]
            print(f"  ⚠️  Mascote FFmpeg erro:\n{errtxt}")
            return False

        _salvar_posicao(saida_path, overlay_x, overlay_y)
        print(f"  ✅ Mascote overlay: {Path(saida_path).name}")
        return True

    except Exception as e:
        try:
            proc.stdin.close()
            proc.wait(3)
        except Exception:
            pass
        print(f"  ⚠️  Mascote: {e}")
        return False
