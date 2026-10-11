"""
gerar_borda.py — Gera a borda decorativa para os vídeos do GeradorBB.

Uso:
    python gerar_borda.py                    # gera borda_video.png (1080x1920)
    python gerar_borda.py --preview          # abre preview imediatamente

A imagem gerada é um PNG com fundo TRANSPARENTE no centro.
Coloque o arquivo gerado na pasta do projeto; o engine aplica automaticamente.
"""

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# ── Configurações ─────────────────────────────────────────────────────────────
LARGURA        = 1080
ALTURA         = 1920
ESPESSURA      = 14        # px — largura da borda principal
GLOW_BLUR      = 18        # raio do brilho externo
COR_PRIMARIA   = (80, 160, 255)    # azul sci-fi
COR_SECUNDARIA = (160, 80, 240)    # roxo
COR_SAKURA     = (255, 160, 200)   # rosa claro das pétalas
ALPHA_BORDA    = 230       # 0-255 — opacidade da linha principal
ALPHA_GLOW     = 80        # opacidade do brilho
N_PETALAS      = 22        # quantidade de pétalas nas bordas
SEMENTE        = 42        # seed para posições das pétalas (reproduzível)
SAIDA          = Path(__file__).parent / "borda_video.png"
# ──────────────────────────────────────────────────────────────────────────────


def _lerp_cor(c1, c2, t):
    """Interpola linearmente entre duas cores RGB."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _gradiente_pos(x, y, w, h):
    """Retorna t (0..1) baseado na posição na borda — azul no topo, roxo embaixo."""
    return y / h


def _desenhar_linha_gradiente(draw, pts, espessura, alpha):
    """Desenha uma polilinha com gradiente azul→roxo ponto a ponto."""
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        t = _gradiente_pos((x0 + x1) / 2, (y0 + y1) / 2, LARGURA, ALTURA)
        cor = _lerp_cor(COR_PRIMARIA, COR_SECUNDARIA, t) + (alpha,)
        draw.line([pts[i], pts[i + 1]], fill=cor, width=espessura)


def _pontos_borda(w, h, margin=0):
    """Retorna os pontos do retângulo da borda (sentido horário)."""
    m = margin
    r = 28 - margin // 2   # raio do canto arredondado
    pts = []
    # Topo
    pts += [(m + r, m), (w - m - r, m)]
    # Canto sup-dir
    for i in range(1, 9):
        a = math.radians(-90 + i * 10)
        pts.append((w - m - r + math.cos(a) * r, m + r + math.sin(a) * r))
    # Direita
    pts += [(w - m, m + r), (w - m, h - m - r)]
    # Canto inf-dir
    for i in range(1, 9):
        a = math.radians(0 + i * 10)
        pts.append((w - m - r + math.cos(a) * r, h - m - r + math.sin(a) * r))
    # Base
    pts += [(w - m - r, h - m), (m + r, h - m)]
    # Canto inf-esq
    for i in range(1, 9):
        a = math.radians(90 + i * 10)
        pts.append((m + r + math.cos(a) * r, h - m - r + math.sin(a) * r))
    # Esquerda
    pts += [(m, h - m - r), (m, m + r)]
    # Canto sup-esq
    for i in range(1, 9):
        a = math.radians(180 + i * 10)
        pts.append((m + r + math.cos(a) * r, m + r + math.sin(a) * r))
    pts.append(pts[0])  # fecha
    return pts


def _desenhar_petala(draw, cx, cy, raio, angulo, cor, alpha):
    """Desenha uma pétala simples (elipse rotacionada via polígono)."""
    pontos = []
    for i in range(12):
        a = math.radians(i * 30 + angulo)
        rx = raio * 1.0
        ry = raio * 0.55
        px = cx + math.cos(a) * rx - math.sin(a) * ry * 0.3
        py = cy + math.sin(a) * rx + math.cos(a) * ry * 0.3
        pontos.append((px, py))
    draw.polygon(pontos, fill=cor + (alpha,))


def _adicionar_acento_canto(layer, cx, cy, tamanho, invertido=False):
    """Linha diagonal decorativa nos cantos."""
    draw = ImageDraw.Draw(layer)
    d = tamanho
    sx = -1 if invertido else 1
    pts_diag = [(cx, cy), (cx + sx * d * 0.6, cy + d * 0.6)]
    t = _gradiente_pos(cx, cy, LARGURA, ALTURA)
    cor = _lerp_cor(COR_PRIMARIA, COR_SECUNDARIA, t)
    draw.line(pts_diag, fill=cor + (160,), width=2)

    # pequeno losango no final
    ex, ey = pts_diag[-1]
    s = 5
    draw.polygon([(ex, ey - s), (ex + s, ey), (ex, ey + s), (ex - s, ey)],
                 fill=cor + (180,))


def gerar_borda(saida: Path = SAIDA, preview: bool = False):
    w, h = LARGURA, ALTURA

    # ── Camada de glow (desfocada) ────────────────────────────────────────────
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    pts = _pontos_borda(w, h, margin=ESPESSURA // 2)
    for espessura_extra in (ESPESSURA + 20, ESPESSURA + 10, ESPESSURA + 4):
        _desenhar_linha_gradiente(gd, pts, espessura_extra, ALPHA_GLOW // 2)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(GLOW_BLUR))

    # ── Camada principal ──────────────────────────────────────────────────────
    main_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    md = ImageDraw.Draw(main_layer)
    _desenhar_linha_gradiente(md, pts, ESPESSURA, ALPHA_BORDA)

    # Linha interna fina (1px mais suave)
    pts_in = _pontos_borda(w, h, margin=ESPESSURA + 4)
    _desenhar_linha_gradiente(md, pts_in, 1, 100)

    # ── Cantos decorativos ────────────────────────────────────────────────────
    cantos = [
        (ESPESSURA + 30, ESPESSURA + 30, False),
        (w - ESPESSURA - 30, ESPESSURA + 30, True),
        (ESPESSURA + 30, h - ESPESSURA - 30, False),
        (w - ESPESSURA - 30, h - ESPESSURA - 30, True),
    ]
    for cx, cy, inv in cantos:
        _adicionar_acento_canto(main_layer, cx, cy, 40, inv)

    # ── Pétalas de sakura ─────────────────────────────────────────────────────
    rng = random.Random(SEMENTE)
    petal_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(petal_layer)

    margem_interna = ESPESSURA * 3 + 10

    for _ in range(N_PETALAS):
        lado = rng.choice(["top", "bottom", "left", "right"])
        if lado == "top":
            cx = rng.randint(40, w - 40)
            cy = rng.randint(4, margem_interna)
        elif lado == "bottom":
            cx = rng.randint(40, w - 40)
            cy = rng.randint(h - margem_interna, h - 4)
        elif lado == "left":
            cx = rng.randint(4, margem_interna)
            cy = rng.randint(40, h - 40)
        else:
            cx = rng.randint(w - margem_interna, w - 4)
            cy = rng.randint(40, h - 40)

        raio  = rng.randint(6, 14)
        angulo = rng.uniform(0, 360)
        alpha  = rng.randint(120, 210)
        _desenhar_petala(pd, cx, cy, raio, angulo, COR_SAKURA, alpha)

    # ── Composição final ──────────────────────────────────────────────────────
    resultado = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    resultado = Image.alpha_composite(resultado, glow_layer)
    resultado = Image.alpha_composite(resultado, petal_layer)
    resultado = Image.alpha_composite(resultado, main_layer)

    saida.parent.mkdir(parents=True, exist_ok=True)
    resultado.save(saida, "PNG")
    print(f"[OK] Borda salva em: {saida}")

    if preview:
        # Coloca sobre fundo escuro para visualizar melhor
        fundo = Image.new("RGB", (w, h), (11, 11, 20))
        fundo.paste(resultado, mask=resultado.split()[3])
        fundo.show()

    return saida


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera borda decorativa PNG")
    parser.add_argument("--saida", default=str(SAIDA), help="Caminho de saída")
    parser.add_argument("--preview", action="store_true", help="Abre preview após gerar")
    parser.add_argument("--largura", type=int, default=LARGURA)
    parser.add_argument("--altura", type=int, default=ALTURA)
    parser.add_argument("--espessura", type=int, default=ESPESSURA,
                        help="Espessura da linha principal em px (padrão: 14)")
    args = parser.parse_args()

    LARGURA   = args.largura
    ALTURA    = args.altura
    ESPESSURA = args.espessura

    gerar_borda(Path(args.saida), preview=args.preview)
