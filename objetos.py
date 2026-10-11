"""
Banco de objetos animados para o Rankadorama.
Exibe imagens PNG com animação pop quando palavras-chave são faladas.
"""

import json
import math
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

import os as _os_obj
_PROJ_BASE_OBJ = Path(_os_obj.environ["GERADORBB_PROJETO_DIR"]) if "GERADORBB_PROJETO_DIR" in _os_obj.environ else None
_CFG_PATH = (_PROJ_BASE_OBJ / "projeto" / "personagem" / "personagem_config.json") if _PROJ_BASE_OBJ else (Path(__file__).resolve().parent / "personagem_config.json")
_DEFAULTS_OBJ = {
    "objetos_ativo": True,
    "objetos_duracao_s": 1.5,
    "objetos_intervalo_min_s": 4.0,
    "objetos_largura_px": 200,
    "objetos_posicao_x": 40,
    "objetos_posicao_y_pct": 0.45,
}


def cfg():
    c = dict(_DEFAULTS_OBJ)
    if _CFG_PATH.exists():
        try:
            c.update({k: v for k, v in
                      json.loads(_CFG_PATH.read_text(encoding="utf-8")).items()
                      if k in _DEFAULTS_OBJ})
        except Exception:
            pass
    return c


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", t).strip()


def carregar_config(json_path: Path) -> dict:
    if not json_path.exists():
        return {}
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        # Remove chaves internas que começam com _
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        print(f"  ⚠️  Objetos: erro ao ler {json_path.name} — {e}")
        return {}


def calcular_exibicoes(tempos: list, tokens: list, lingua: str,
                       config: dict, inicio_item: dict,
                       top_n: int, duracao: float) -> list:
    """
    Retorna lista de (t_inicio, img_nome, item_n).
    Aplica: intervalo mínimo e máximo 1 objeto por item.
    """
    c = cfg()
    if not c.get("objetos_ativo", True) or not config or not tokens:
        return []

    intervalo_min = c["objetos_intervalo_min_s"]
    dur_obj = c["objetos_duracao_s"]

    # Mapa token_idx → item_n
    token_item = {}
    item_ns = sorted([n for n in inicio_item if isinstance(n, int)], reverse=True)
    for i, n in enumerate(item_ns):
        nxt = item_ns[i + 1] if i + 1 < len(item_ns) else None
        ini_t = inicio_item[n]
        fim_t = inicio_item[nxt] if nxt and nxt in inicio_item else len(tokens)
        for ti in range(ini_t, fim_t):
            token_item[ti] = n
    if "fim" in inicio_item:
        for ti in range(inicio_item["fim"], len(tokens)):
            token_item[ti] = 0

    texto_norm = [_norm(tok) for tok in tokens]
    candidatos = []

    for img_nome, kws in config.items():
        keywords = kws.get(lingua, [])
        for kw in keywords:
            kw_parts = _norm(kw).split()
            n_kw = len(kw_parts)
            if n_kw == 0:
                continue
            for i in range(len(texto_norm) - n_kw + 1):
                if texto_norm[i:i + n_kw] == kw_parts:
                    if i >= len(tempos) or tempos[i] is None:
                        continue
                    t_ini = tempos[i][0]
                    if t_ini + dur_obj > duracao:
                        continue
                    item_n = token_item.get(i, -1)
                    candidatos.append((t_ini, img_nome, item_n))

    candidatos.sort(key=lambda x: x[0])
    resultado = []
    ultimo_t = -9999.0
    itens_usados = set()

    for t_ini, img_nome, item_n in candidatos:
        if t_ini - ultimo_t < intervalo_min:
            continue
        if item_n >= 1 and item_n in itens_usados:
            continue
        resultado.append((t_ini, img_nome, item_n))
        ultimo_t = t_ini
        if item_n >= 1:
            itens_usados.add(item_n)

    return resultado


def gerar_overlay(exibicoes: list, pasta_objetos: Path,
                  duracao: float, fps: int,
                  largura_video: int, altura_video: int,
                  posicao_legenda: int,
                  saida_path: Path) -> bool:
    """
    Gera overlay de objetos como WebM com alpha.
    Retorna True se gerado com sucesso.
    """
    c = cfg()
    if not c.get("objetos_ativo", True) or not exibicoes:
        return False

    try:
        from PIL import Image
    except ImportError:
        print("  ⚠️  Objetos: Pillow não instalado — pulando.")
        return False

    obj_w = c["objetos_largura_px"]
    obj_x = c["objetos_posicao_x"]
    obj_y_center = int(altura_video * c["objetos_posicao_y_pct"])

    # Pré-carrega imagens
    imgs = {}
    for _, img_nome, _ in exibicoes:
        if img_nome in imgs:
            continue
        ip = pasta_objetos / img_nome
        if ip.exists():
            img = Image.open(ip).convert("RGBA")
            w, h = img.size
            nh = max(1, int(h * obj_w / w))
            imgs[img_nome] = img.resize((obj_w, nh), Image.LANCZOS)
        else:
            print(f"  ⚠️  Objetos: {img_nome} não encontrado")

    if not imgs:
        print("  ⚠️  Objetos: nenhuma imagem encontrada — pulando.")
        return False

    dur_obj_f = int(c["objetos_duracao_s"] * fps)
    n_frames = int(math.ceil(duracao * fps))

    # Agenda: lista de (frame_ini, frame_fim, img_nome)
    agenda = []
    for t_ini, img_nome, _ in exibicoes:
        if img_nome not in imgs:
            continue
        fi = int(t_ini * fps)
        ff = min(n_frames, fi + dur_obj_f)
        agenda.append((fi, ff, img_nome))

    # Área do frame = área do objeto (não o frame completo)
    max_obj_w = max(imgs[g].width  for _, _, g in agenda if g in imgs)
    max_obj_h = max(imgs[g].height for _, _, g in agenda if g in imgs)
    FRAME_W = max_obj_w + 20
    FRAME_H = max_obj_h + 20
    overlay_x = obj_x
    overlay_y = obj_y_center - FRAME_H // 2

    print(f"  🎁 Gerando overlay de objetos ({len(exibicoes)} evento(s))...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{FRAME_W}x{FRAME_H}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libvpx", "-b:v", "0", "-crf", "10",
        "-auto-alt-ref", "0", "-pix_fmt", "yuva420p",
        str(saida_path)
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=_NO_WIN
    )

    try:
        for f in range(n_frames):
            frame = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
            for fi, ff, img_nome in agenda:
                if not (fi <= f < ff):
                    continue
                img = imgs[img_nome]
                frames_in  = f - fi
                frames_out = ff - f - 1
                # Animação pop: 10 frames entrada, 5 frames saída
                if frames_in < 10:
                    p = frames_in / 10.0
                    escala = p * 1.15 if p < 0.7 else 1.15 - (p - 0.7) / 0.3 * 0.15
                elif frames_out < 5:
                    escala = max(0.01, frames_out / 5.0)
                else:
                    escala = 1.0

                cw = max(1, int(img.width * escala))
                ch = max(1, int(img.height * escala))
                img_esc = img.resize((cw, ch), Image.LANCZOS)
                ox = (FRAME_W - cw) // 2
                oy = (FRAME_H - ch) // 2
                frame.alpha_composite(img_esc, (max(0, ox), max(0, oy)))

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        _, stderr = proc.communicate(timeout=180)

        if proc.returncode != 0:
            errtxt = stderr.decode("utf-8", errors="ignore")[-400:]
            print(f"  ⚠️  Objetos FFmpeg erro:\n{errtxt}")
            return False

        # Salva posição
        Path(str(saida_path) + ".pos").write_text(
            f"{overlay_x},{overlay_y}", encoding="utf-8"
        )
        print(f"  ✅ Objetos overlay: {Path(saida_path).name}")
        return True

    except Exception as e:
        try:
            proc.stdin.close()
            proc.wait(3)
        except Exception:
            pass
        print(f"  ⚠️  Objetos: {e}")
        return False
