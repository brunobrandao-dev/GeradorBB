"""
Personagem apresentador (clipes de vídeo com chromakey) para o Rankadorama.
Gera um overlay WebM com canal alpha do personagem animado.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

import os as _os_pers
_PROJ_BASE = Path(_os_pers.environ["GERADORBB_PROJETO_DIR"]) if "GERADORBB_PROJETO_DIR" in _os_pers.environ else None
_CFG_PATH = (_PROJ_BASE / "projeto" / "personagem" / "personagem_config.json") if _PROJ_BASE else (Path(__file__).resolve().parent / "personagem_config.json")

POSES = ["acenando", "apontando", "comemorando", "tchau", "falando", "parado"]

_DEFAULTS = {
    "ativo": True,
    "largura_pct": 0.22,
    "lado": "esquerda",
    "margem_direita": 20,
    "margem_esquerda": 20,
    "margem_fundo": 50,
    "contorno_px": 3,
    "contorno_cor": [255, 255, 255],
    "sombra_ativa": True,
    "sombra_offset_x": 5,
    "sombra_offset_y": 8,
    "sombra_blur": 6,
    "sombra_alpha": 0.65,
    "bob_amplitude_px": 3,
    "bob_hz": 0.5,
    "chromakey_cor": "0x1AE811",
    "chromakey_similaridade": 0.12,
    "chromakey_suavizacao": 0.08,
    "despill_ativo": True,
    "despill_fator": 0.8,
    "crossfade_s": 0.15,
    "fade_saida_s": 0.20,
    # Sincronização boca: falando ↔ parado por volume
    "volume_limite_boca": 0.03,
    "pausa_min_s": 0.30,
}


# ── Configuração ──────────────────────────────────────────────────────────────

def cfg() -> dict:
    c = dict(_DEFAULTS)
    if _CFG_PATH.exists():
        try:
            c.update(json.loads(_CFG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return c


# ── Clipes de vídeo ───────────────────────────────────────────────────────────

def preparar_clipes(pasta: Path) -> dict:
    """Escaneia POSES na pasta, aceita .mp4/.MP4/.mov/.MOV/.webm.
    'falando' é opcional; os outros emitem aviso se ausentes.
    Retorna {nome: Path}."""
    # Nomes alternativos aceitos por pose (além do nome exato + capitalize + upper)
    _ALIASES: dict = {
        "falando":    ["falando_aberta", "falando_loop", "idle", "neutro"],
        "apontando":  ["Apontando para a lengenda", "Apontando para a legenda",
                       "apontando_legenda", "pointing"],
        "parado":     ["falando", "idle", "neutro"],
    }
    resultado = {}
    exts = [".mp4", ".MP4", ".mov", ".MOV", ".webm"]
    for pose in POSES:
        candidatos = [pose, pose.capitalize(), pose.upper()]
        for alias in _ALIASES.get(pose, []):
            candidatos += [alias, alias.capitalize(), alias.upper()]
        for variante in candidatos:
            for ext in exts:
                p = pasta / f"{variante}{ext}"
                if p.exists():
                    resultado[pose] = p
                    break
            if pose in resultado:
                break
        if pose not in resultado and pose not in ("falando", "parado", "acenando",
                                                   "comemorando", "tchau"):
            print(f"  ⚠️  Personagem: clipe '{pose}.mp4' não encontrado em {pasta}")

    # Se "parado" não foi encontrado, reutiliza "falando" (evita KeyError na renderização)
    if "parado" not in resultado and "falando" in resultado:
        resultado["parado"] = resultado["falando"]

    return resultado


# ── Remoção de fundo por flood-fill ──────────────────────────────────────────

def _remover_fundo_frames(frames_rgb: "np.ndarray") -> "np.ndarray":
    """Remove fundo de N frames RGB usando flood-fill (connected components).
    Detecta a cor do fundo pelos cantos do primeiro frame.
    Funciona com qualquer cor de fundo (branco, cinza, verde, azul).
    Retorna array RGBA (N, H, W, 4)."""
    import numpy as np
    from scipy.ndimage import label, binary_dilation

    N, H, W, _ = frames_rgb.shape
    rgba = np.zeros((N, H, W, 4), dtype=np.uint8)
    rgba[:, :, :, :3] = frames_rgb

    # Detecta cor do fundo pelas bordas inteiras do primeiro frame
    # (não só cantos — captura gradientes de iluminação)
    f0 = frames_rgb[0].astype(np.float32)
    borda = max(8, min(H, W) // 12)
    borda_pixels = np.vstack([
        f0[:borda,   :].reshape(-1, 3),   # topo
        f0[-borda:,  :].reshape(-1, 3),   # base
        f0[:,  :borda].reshape(-1, 3),    # esquerda
        f0[:, -borda:].reshape(-1, 3),    # direita
    ])
    # Usa apenas os pixels próximos da mediana para estimar a cor real do fundo
    # (exclui pixels do personagem que estejam na borda)
    bg_raw = np.median(borda_pixels, axis=0)
    dists_borda = np.sqrt(((borda_pixels.astype(np.float32) - bg_raw) ** 2).sum(axis=1))
    bg = np.median(borda_pixels[dists_borda < 50], axis=0) if (dists_borda < 50).sum() > 10 else bg_raw

    THRESH  = 65.0   # fixo: suficiente para fundo levemente sombreado/comprimido
    FEATHER = 28.0

    from scipy.ndimage import binary_closing

    for i in range(N):
        f = frames_rgb[i].astype(np.float32)
        dist = np.sqrt(((f - bg) ** 2).sum(axis=2))
        bg_cand = dist < THRESH

        # ── Fecha buracos na silhueta antes do flood-fill ─────────────────────
        # Sem isso, o fundo "vaza" pelos fios de cabelo/roupas escuras.
        # binary_closing preenche gaps < ~20px na máscara do personagem.
        fg_solid = binary_closing(~bg_cand, structure=np.ones((25, 25)))
        bg_para_ff = ~fg_solid   # candidatos a fundo com silhueta fechada

        # Flood-fill na máscara fechada: só remove fundo conectado às bordas
        labeled, _ = label(bg_para_ff)
        border_labels = set()
        border_labels.update(labeled[0,  :].flat)
        border_labels.update(labeled[-1, :].flat)
        border_labels.update(labeled[:,  0].flat)
        border_labels.update(labeled[:, -1].flat)
        border_labels.discard(0)

        true_bg   = np.isin(labeled, list(border_labels))
        # Dilata levemente para cobrir a zona de transição (borda suave)
        true_bg_d = binary_dilation(true_bg, iterations=2)

        # Alpha final: usa distância da imagem ORIGINAL (não a fechada)
        # para bordas suaves reais do cabelo/roupa
        alpha = np.clip((dist - THRESH) / FEATHER * 255, 0, 255)
        alpha[true_bg]    = 0      # fundo confirmado → transparente
        alpha[~true_bg_d] = 255    # interior do personagem → opaco
        rgba[i, :, :, 3] = alpha.clip(0, 255).astype(np.uint8)

    return rgba


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path_npz(clip: Path, w: int, h: int, c: dict) -> Path:
    """Cache como numpy .npz — nome inclui hash dos parâmetros de chromakey
    para invalidar automaticamente quando as configurações mudarem."""
    import hashlib
    cor   = c.get("chromakey_cor", "0x00FF00")
    sim   = c.get("chromakey_similaridade", 0.12)
    suav  = c.get("chromakey_suavizacao", 0.08)
    desp  = c.get("despill_ativo", True)
    dfat  = c.get("despill_fator", 0.8)
    cfg_hash = hashlib.md5(
        f"{cor}{sim:.4f}{suav:.4f}{desp}{dfat:.4f}".encode()
    ).hexdigest()[:8]
    return clip.parent / "_transparente" / f"{clip.stem}_{w}x{h}_{cfg_hash}.npz"


def _carregar_clip_rgba(clip: Path, w: int, h: int, c: dict) -> "np.ndarray | None":
    """Extrai frames do clipe via chromakey FFmpeg e retorna RGBA (N, h, w, 4).
    Usa cache .npz (nome inclui hash de config) para evitar reprocessar."""
    import numpy as np

    cache = _cache_path_npz(clip, w, h, c)
    if cache.exists() and clip.stat().st_mtime <= cache.stat().st_mtime:
        try:
            return np.load(str(cache))["frames"]
        except Exception:
            pass

    cache.parent.mkdir(parents=True, exist_ok=True)

    # Parâmetros do chromakey — remove prefixo "0x" ou "#"
    cor_raw = c.get("chromakey_cor", "0x00FF00")
    cor     = cor_raw.removeprefix("0x").removeprefix("#")
    sim     = c.get("chromakey_similaridade", 0.12)
    suav    = c.get("chromakey_suavizacao",   0.08)
    despill       = c.get("despill_ativo", True)
    despill_fator = c.get("despill_fator",  0.8)

    # Monta filtro: scale → chromakey
    filtro = f"scale={w}:{h},chromakey=color=0x{cor}:similarity={sim:.3f}:blend={suav:.3f}"

    # Despill: testa se o filtro existe no FFmpeg antes de usar
    if despill:
        test = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "color=black:s=2x2:d=0.1",
             "-vf", f"despill=type=green:mix={despill_fator:.2f}",
             "-f", "null", "-"],
            capture_output=True, creationflags=_NO_WIN
        )
        if test.returncode == 0:
            filtro += f",despill=type=green:mix={despill_fator:.2f}"
        else:
            print("  ℹ️  Personagem: filtro despill não disponível neste FFmpeg — pulando.")

    cmd = [
        "ffmpeg", "-y", "-i", str(clip),
        "-vf", filtro,
        "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1",
    ]
    print(f"  🎭 Chromakey: {clip.name}  (sim={sim:.3f})...", flush=True)
    r = subprocess.run(cmd, capture_output=True, creationflags=_NO_WIN)
    raw = r.stdout

    if not raw:
        stderr_txt = r.stderr.decode("utf-8", errors="ignore")[-300:]
        print(f"  ⚠️  Personagem: falha ao extrair frames de {clip.name}\n{stderr_txt}")
        return None

    frame_bytes = w * h * 4
    n = len(raw) // frame_bytes
    if n == 0:
        print(f"  ⚠️  Personagem: sem frames em {clip.name}")
        return None

    frames = np.frombuffer(raw[:n * frame_bytes], dtype=np.uint8).reshape(n, h, w, 4).copy()
    try:
        np.savez_compressed(str(cache), frames=frames)
    except Exception:
        pass  # falha no cache não é fatal
    return frames


# ── Efeitos visuais ───────────────────────────────────────────────────────────

def _efeito_frame(img_pil, contorno_px, sombra_ativa, sombra_offset,
                  sombra_blur, sombra_alpha_f, cor_contorno):
    """Aplica sombra projetada + contorno a uma PIL RGBA. Retorna PIL RGBA."""
    from PIL import Image, ImageFilter
    import numpy as np

    arr = np.array(img_pil, dtype=np.uint8)
    alpha = arr[:, :, 3]
    w, h = img_pil.size
    resultado = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Sombra projetada
    if sombra_ativa:
        shadow_alpha = np.clip(
            alpha.astype(np.float32) * sombra_alpha_f, 0, 255
        ).astype(np.uint8)
        shadow_arr = np.zeros_like(arr)
        shadow_arr[:, :, 3] = shadow_alpha
        shadow_pil = Image.fromarray(shadow_arr, "RGBA")
        dx, dy = int(sombra_offset[0]), int(sombra_offset[1])
        deslocado = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        region = shadow_pil.crop((0, 0, max(1, w - dx), max(1, h - dy)))
        deslocado.paste(region, (dx, dy))
        if sombra_blur > 0:
            deslocado = deslocado.filter(ImageFilter.GaussianBlur(sombra_blur))
        resultado.alpha_composite(deslocado)

    # Contorno
    if contorno_px > 0:
        alpha_pil = Image.fromarray(alpha, "L")
        dilated = alpha_pil
        for _ in range(max(1, contorno_px)):
            dilated = dilated.filter(ImageFilter.MaxFilter(3))
        dilated_arr = np.array(dilated)
        borda = (dilated_arr > 64) & (alpha <= 64)
        cr, cg, cb = cor_contorno
        contorno_arr = np.zeros_like(arr)
        contorno_arr[:, :, 0] = cr
        contorno_arr[:, :, 1] = cg
        contorno_arr[:, :, 2] = cb
        contorno_arr[:, :, 3] = np.where(borda, 220, 0).astype(np.uint8)
        resultado.alpha_composite(Image.fromarray(contorno_arr, "RGBA"))

    resultado.alpha_composite(img_pil)
    return resultado


def _aplicar_efeitos_lote(frames: "np.ndarray", c: dict) -> "np.ndarray":
    """Aplica _efeito_frame a cada frame de (N, H, W, 4). Retorna mesmo shape."""
    from PIL import Image
    import numpy as np

    contorno_px   = c.get("contorno_px", 3)
    sombra_ativa  = c.get("sombra_ativa", True)
    sombra_offset = (c.get("sombra_offset_x", 5), c.get("sombra_offset_y", 8))
    sombra_blur   = c.get("sombra_blur", 6)
    sombra_alpha_f = c.get("sombra_alpha", 0.65)
    cor_contorno  = tuple(c.get("contorno_cor", [255, 255, 255]))

    N, H, W, _ = frames.shape
    resultado = np.empty_like(frames)
    for i in range(N):
        pil = Image.fromarray(frames[i], "RGBA")
        out = _efeito_frame(
            pil, contorno_px, sombra_ativa, sombra_offset,
            sombra_blur, sombra_alpha_f, cor_contorno,
        )
        resultado[i] = np.array(out, dtype=np.uint8)
    return resultado


# ── Volume e sincronização boca ──────────────────────────────────────────────

def _volume_por_frame(audio_path: Path, n_frames: int, fps: float) -> list:
    """RMS de áudio por frame. Retorna lista de floats [0..1]."""
    import numpy as np
    r = subprocess.run(
        ["ffmpeg", "-i", str(audio_path),
         "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"],
        capture_output=True, creationflags=_NO_WIN,
    )
    amostras = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    spp = max(1.0, len(amostras) / n_frames)
    resultado = []
    for i in range(n_frames):
        chunk = amostras[int(i * spp):int((i + 1) * spp)]
        rms = float(((chunk ** 2).mean() ** 0.5)) if len(chunk) else 0.0
        resultado.append(rms)
    return resultado


def _calcular_silencio(volume: list, fps: float,
                        pausa_min_s: float, limite: float) -> "np.ndarray":
    """True se o frame está em pausa contínua >= pausa_min_s."""
    import numpy as np
    pausa_min_f = max(1, int(pausa_min_s * fps))
    silencio = np.zeros(len(volume), dtype=bool)
    consec = 0
    for f, v in enumerate(volume):
        if v < limite:
            consec += 1
            if consec >= pausa_min_f:
                silencio[f] = True
        else:
            consec = 0
    return silencio


def _calcular_estado_loop(silencio: "np.ndarray", seg_map: "np.ndarray",
                           agenda: list, n_frames: int,
                           crossfade_frames: int) -> list:
    """
    Pré-computa por frame (só em segmentos "loop"):
      (clip_atual, clip_anterior_ou_None, alpha_blend)
    Retorna lista de tamanho n_frames; None fora de segmentos loop.
    """
    state = [None] * n_frames
    current_clip = "falando"
    prev_clip    = "falando"
    trans_frame  = -crossfade_frames - 1

    for f in range(n_frames):
        si = int(seg_map[f])
        if si >= len(agenda) or agenda[si]["mode"] != "loop":
            current_clip = "falando"
            prev_clip    = "falando"
            trans_frame  = -crossfade_frames - 1
            continue

        desired = "parado" if silencio[f] else "falando"

        if desired != current_clip:
            prev_clip   = current_clip
            current_clip = desired
            trans_frame  = f

        frames_in_trans = f - trans_frame
        if frames_in_trans < crossfade_frames:
            alpha = frames_in_trans / crossfade_frames
            state[f] = (current_clip, prev_clip, alpha)
        else:
            state[f] = (current_clip, None, 1.0)

    return state


# ── Agenda de clipes ──────────────────────────────────────────────────────────

def _calcular_agenda(tempos, inicio_item, top_n, duracao,
                     clips_disponiveis, clips_dur, c) -> list:
    """Retorna lista de segmentos: {t_start, t_end, clip, mode, fade_out}."""

    # 1. Coletar eventos
    eventos = []

    if "acenando" in clips_disponiveis and c.get("acenando_inicial", True):
        eventos.append((0.0, "acenando"))

    if c.get("apontando_ativo", True):
        for n in range(top_n, 1, -1):
            if "apontando" in clips_disponiveis:
                if (n in inicio_item and
                        inicio_item[n] < len(tempos) and
                        tempos[inicio_item[n]]):
                    t = tempos[inicio_item[n]][0]
                    eventos.append((t, "apontando"))

    if "comemorando" in clips_disponiveis:
        if (1 in inicio_item and
                inicio_item[1] < len(tempos) and
                tempos[inicio_item[1]]):
            t = tempos[inicio_item[1]][0]
            eventos.append((t, "comemorando"))

    if "tchau" in clips_disponiveis:
        if ("fim" in inicio_item and
                inicio_item["fim"] < len(tempos) and
                tempos[inicio_item["fim"]]):
            t = tempos[inicio_item["fim"]][0]
            eventos.append((t, "tchau"))

    # 2. Ordenar e deduplicar
    eventos.sort(key=lambda x: x[0])
    dedup = []
    for ev in eventos:
        if dedup and abs(ev[0] - dedup[-1][0]) < 0.05:
            continue
        dedup.append(ev)
    eventos = dedup

    # 3. Modo de preenchimento entre eventos
    if "falando" in clips_disponiveis:
        mode_entre = "loop"
        clip_entre = "falando"
    else:
        mode_entre = "freeze"
        clip_entre = None

    segments = []

    def _add_fill(t0, t1):
        if t1 <= t0:
            return
        segments.append({
            "t_start": t0, "t_end": t1,
            "clip": clip_entre, "mode": mode_entre, "fade_out": False,
        })

    cursor = 0.0
    for idx, (t_ev, clip) in enumerate(eventos):
        # Preenche gap até o evento
        _add_fill(cursor, t_ev)

        dur_clip = clips_dur.get(clip, 2.0)
        t_fim_clip = t_ev + dur_clip
        if idx + 1 < len(eventos):
            t_next = eventos[idx + 1][0]
        else:
            t_next = duracao

        vai_estourar = t_fim_clip > t_next + 0.01
        t_end_ev = t_next if vai_estourar else t_fim_clip

        if t_end_ev > t_ev:
            segments.append({
                "t_start": t_ev, "t_end": t_end_ev,
                "clip": clip, "mode": "once", "fade_out": vai_estourar,
            })
        cursor = t_end_ev

    # Preenche do cursor até o fim
    _add_fill(cursor, duracao)

    # Remove segmentos vazios
    segments = [s for s in segments if s["t_end"] > s["t_start"]]
    return segments


# ── Obter frame de clipe ──────────────────────────────────────────────────────

def _get_clip_frame(clip_name, t_in_seg, fps, clip_arrays, mode) -> "np.ndarray | None":
    """Retorna um frame (H, W, 4) como view do array. Sem cópia."""
    frames = clip_arrays.get(clip_name)
    if frames is None:
        return None
    N = len(frames)
    if N == 0:
        return None

    if mode == "once":
        idx = min(int(t_in_seg * fps), N - 1)
    elif mode == "loop":
        cycle = max(1, (N - 1) * 2)
        pos = int(t_in_seg * fps) % cycle
        idx = pos if pos < N else cycle - pos
        idx = max(0, min(N - 1, idx))
    else:  # freeze
        idx = N - 1

    return frames[idx]


# ── Posição do overlay ────────────────────────────────────────────────────────

def _salvar_posicao(webm_path: Path, x: int, y: int):
    Path(str(webm_path) + ".pos").write_text(f"{x},{y}", encoding="utf-8")


def ler_posicao(webm_path: Path) -> tuple:
    pos_file = Path(str(webm_path) + ".pos")
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
                  posicao_legenda, saida_path, pasta_personagem,
                  capa_rect=None) -> bool:
    """Gera overlay do personagem como MKV com alpha (png codec).
    capa_rect = (x, y, w, h) da capa dentro do frame — se fornecido, posiciona
    o personagem DENTRO da capa (canto inferior esquerdo, 30% da altura da capa).
    Retorna True se gerou com sucesso."""

    c = cfg()
    if not c.get("ativo", True):
        return False

    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        print("  ⚠️  Personagem: Pillow/NumPy não instalados — pulando.")
        return False

    pasta = Path(pasta_personagem)
    if not pasta.exists():
        print(f"  ⚠️  Personagem: pasta não encontrada ({pasta}) — pulando.")
        return False

    # 1. Varrer clipes disponíveis
    clipes = preparar_clipes(pasta)
    if not clipes:
        print("  ⚠️  Personagem: nenhum clipe disponível — pulando.")
        return False

    # 2. ffprobe no clipe de referência para obter proporção original
    ref_ordem = ["acenando", "apontando", "comemorando", "tchau", "falando"]
    ref_nome = next((n for n in ref_ordem if n in clipes), next(iter(clipes)))
    ref_clip = clipes[ref_nome]
    orig_w, orig_h = 0, 0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_streams",
             "-select_streams", "v:0",
             "-print_format", "ini", str(ref_clip)],
            capture_output=True, creationflags=_NO_WIN,
        )
        for line in r.stdout.decode("utf-8", errors="ignore").splitlines():
            if line.startswith("width="):
                orig_w = int(line.split("=", 1)[1])
            elif line.startswith("height="):
                orig_h = int(line.split("=", 1)[1])
    except Exception:
        pass

    # 3. Dimensões do personagem
    if capa_rect is not None:
        # Posicionar DENTRO da capa: altura = 30% da capa, largura preserva proporção do clipe
        cap_x, cap_y, cap_w, cap_h = capa_rect
        char_h = (int(cap_h * 0.30) // 2) * 2   # múltiplo de 2
        if orig_w > 0 and orig_h > 0:
            char_w = (int(orig_w * char_h / orig_h) // 2) * 2
        else:
            char_w = (char_h // 2 // 2) * 2
    else:
        char_w = int(largura_video * c["largura_pct"])
        char_h = int(orig_h * char_w / orig_w) if orig_w > 0 and orig_h > 0 else char_w * 2

    # 3. Chromakey + decodificar → RGBA numpy (cache em .npz para reutilizar)
    raw_arrays = {}
    for nome, path in clipes.items():
        arr = _carregar_clip_rgba(path, char_w, char_h, c)
        if arr is not None:
            raw_arrays[nome] = arr
        else:
            print(f"  ⚠️  Personagem: sem frames em '{nome}' — ignorando.")

    if not raw_arrays:
        print("  ⚠️  Personagem: nenhum frame carregado — pulando.")
        return False

    # 5. Duração dos clipes pelo número de frames decodificados
    clips_dur = {nome: len(arr) / fps for nome, arr in raw_arrays.items()}

    # 6. Aplicar efeitos visuais em lote
    print("  🎭 Aplicando efeitos visuais...")
    clip_arrays = {}
    for nome, arr in raw_arrays.items():
        clip_arrays[nome] = _aplicar_efeitos_lote(arr, c)
        print(f"     ✓ {nome}: {len(arr)} frames")

    # 7. Freeze frame: preferir parado (boca fechada), senão falando, senão primeiro
    if "parado" in clip_arrays:
        freeze_frame = clip_arrays["parado"][-1].copy()
    elif "falando" in clip_arrays:
        freeze_frame = clip_arrays["falando"][-1].copy()
    else:
        freeze_frame = next(iter(clip_arrays.values()))[-1].copy()

    # 8. Layout
    sombra_offset_x = c.get("sombra_offset_x", 5)
    sombra_offset_y = c.get("sombra_offset_y", 8)
    sombra_blur     = c.get("sombra_blur", 6)
    bob_amp         = c["bob_amplitude_px"]
    bob_hz          = c["bob_hz"]

    shadow_pad_x = sombra_offset_x + sombra_blur + 2
    shadow_pad_y = sombra_offset_y + sombra_blur + 2
    frame_h_extra = bob_amp + shadow_pad_y
    FRAME_W = char_w + shadow_pad_x * 2
    FRAME_H = char_h + frame_h_extra * 2
    char_off_x = shadow_pad_x
    char_off_y = frame_h_extra

    if capa_rect is not None:
        # ── Posicionar dentro da capa ──────────────────────────────────
        # Base do personagem encosta na borda inferior da capa.
        # Margem esquerda = 1.5% da largura da capa.
        cap_x, cap_y, cap_w, cap_h = capa_rect
        px = cap_x + int(cap_w * 0.015)
        py = cap_y + cap_h - char_h          # topo do corpo = bottom capa - altura
        # Garante que não sai pelos lados nem pelo topo
        px = max(0, min(px, largura_video - char_w))
        py = max(0, py)
    else:
        lado = c.get("lado", "direita")
        if lado == "esquerda":
            px = c.get("margem_esquerda", 20)
        else:
            px = largura_video - char_w - c["margem_direita"]
        margem = max(0, c["margem_fundo"])
        py = max(0, altura_video - char_h - margem)

    overlay_x = max(0, px - shadow_pad_x)
    overlay_y = max(0, py - frame_h_extra)
    # Clamp: o canvas inteiro deve caber dentro do frame (com 1px de segurança)
    overlay_x = min(overlay_x, largura_video  - FRAME_W - 1)
    overlay_y = min(overlay_y, altura_video - FRAME_H - 1)

    # 9. Agenda de segmentos
    agenda = _calcular_agenda(
        tempos, inicio_item, top_n, duracao,
        clip_arrays, clips_dur, c,
    )

    # 10. Mapa frame → índice de segmento
    n_frames = int(math.ceil(duracao * fps))
    seg_map = _build_seg_map(agenda, n_frames, fps)

    crossfade_frames  = max(1, int(c["crossfade_s"] * fps))
    fade_saida_frames = max(1, int(c["fade_saida_s"] * fps))

    # Estado de loop falando↔parado por volume (só se ambos disponíveis)
    loop_estado = None
    if "falando" in clip_arrays and "parado" in clip_arrays:
        volume_limite = c.get("volume_limite_boca", 0.03)
        pausa_min_s   = c.get("pausa_min_s", 0.30)
        print("  🎭 Analisando volume para sincronização de boca...", flush=True)
        vol      = _volume_por_frame(Path(audio_path), n_frames, fps)
        silencio = _calcular_silencio(vol, fps, pausa_min_s, volume_limite)
        loop_estado = _calcular_estado_loop(
            silencio, seg_map, agenda, n_frames, crossfade_frames
        )

    print(f"  🎭 Gerando overlay ({n_frames} frames, {char_w}×{char_h}px)...")

    # 11. Iniciar pipe FFmpeg — codec png em MKV preserva alpha no filtro overlay
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

    import numpy as np

    last_real_frame = freeze_frame.copy()

    try:
        for f in range(n_frames):
            t = f / fps
            si = int(seg_map[f])
            seg = agenda[si] if si < len(agenda) else None

            if seg is None:
                base = last_real_frame.copy()
                mode = "freeze"
            else:
                clip_name = seg["clip"]
                mode = seg["mode"]
                t_in_seg = t - seg["t_start"]

                if mode == "freeze" or clip_name is None or clip_name not in clip_arrays:
                    base = last_real_frame.copy()
                elif mode == "loop" and loop_estado is not None and loop_estado[f] is not None:
                    # Volume-based switching: falando ↔ parado com crossfade
                    cur_clip, blnd_clip, alpha = loop_estado[f]
                    use_cur  = cur_clip  if cur_clip  in clip_arrays else clip_name
                    raw = _get_clip_frame(use_cur, t_in_seg, fps, clip_arrays, "loop")
                    base = raw.copy() if raw is not None else last_real_frame.copy()
                    if blnd_clip is not None and alpha < 1.0:
                        use_blnd = blnd_clip if blnd_clip in clip_arrays else use_cur
                        prev_raw = _get_clip_frame(
                            use_blnd, t_in_seg, fps, clip_arrays, "loop"
                        )
                        if prev_raw is not None:
                            base = (
                                base.astype(np.float32) * alpha +
                                prev_raw.astype(np.float32) * (1.0 - alpha)
                            ).astype(np.uint8)
                    last_real_frame = base
                else:
                    raw = _get_clip_frame(clip_name, t_in_seg, fps, clip_arrays, mode)
                    base = raw.copy() if raw is not None else last_real_frame.copy()
                    last_real_frame = base

                # Fade de saída quando o clipe é cortado
                if seg.get("fade_out", False):
                    frames_remaining = int((seg["t_end"] - t) * fps)
                    if 0 <= frames_remaining <= fade_saida_frames:
                        factor = frames_remaining / fade_saida_frames
                        base[:, :, 3] = (
                            base[:, :, 3].astype(np.float32) * factor
                        ).astype(np.uint8)

                # Crossfade na entrada do segmento
                frames_in_seg = int(t_in_seg * fps)
                if frames_in_seg < crossfade_frames and si > 0:
                    seg_prev = agenda[si - 1]
                    t_in_prev = t - seg_prev["t_start"]
                    prev_clip = seg_prev["clip"]
                    if prev_clip is not None and prev_clip in clip_arrays:
                        prev_raw = _get_clip_frame(
                            prev_clip, t_in_prev, fps, clip_arrays, seg_prev["mode"]
                        )
                    else:
                        prev_raw = last_real_frame
                    if prev_raw is not None:
                        alpha_in = frames_in_seg / crossfade_frames
                        base = (
                            base.astype(np.float32) * alpha_in +
                            prev_raw.astype(np.float32) * (1.0 - alpha_in)
                        ).astype(np.uint8)

            # Bob (só no modo freeze)
            dy = int(bob_amp * math.sin(2 * math.pi * bob_hz * t)) if mode == "freeze" else 0

            # Compor no canvas
            canvas = np.zeros((FRAME_H, FRAME_W, 4), dtype=np.uint8)
            oy = max(0, min(FRAME_H - base.shape[0], char_off_y + dy))
            ox = char_off_x
            h_p = min(base.shape[0], FRAME_H - oy)
            w_p = min(base.shape[1], FRAME_W - ox)
            if h_p > 0 and w_p > 0:
                canvas[oy:oy + h_p, ox:ox + w_p] = base[:h_p, :w_p]

            proc.stdin.write(canvas.tobytes())

            if f % 300 == 0 and f > 0:
                print(f"     personagem: {f}/{n_frames} frames...", flush=True)

        proc.stdin.close()
        _, stderr = proc.communicate(timeout=300)

        if proc.returncode != 0:
            errtxt = stderr.decode("utf-8", errors="ignore")[-500:]
            print(f"  ⚠️  Personagem FFmpeg erro:\n{errtxt}")
            return False

        _salvar_posicao(saida_path, overlay_x, overlay_y)
        print(f"  ✅ Personagem overlay: {Path(saida_path).name}")
        return True

    except Exception as e:
        try:
            proc.stdin.close()
            proc.wait(3)
        except Exception:
            pass
        print(f"  ⚠️  Personagem: {e}")
        return False


def _build_seg_map(agenda: list, n_frames: int, fps: float):
    """Constrói array seg_map[f] = índice do segmento via numpy."""
    import numpy as np
    seg_map = np.zeros(n_frames, dtype=np.int32)
    for i, seg in enumerate(agenda):
        f0 = int(seg["t_start"] * fps)
        f1 = min(int(seg["t_end"] * fps), n_frames)
        if f1 > f0:
            seg_map[f0:f1] = i
    return seg_map
