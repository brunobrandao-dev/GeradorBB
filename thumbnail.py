# thumbnail.py — Gera thumbnail 1280×720 para YouTube após geração de vídeo
#
# Usa só Pillow — sem dependências extras.
# Chamado automaticamente por TelaGerarVideo após geração bem-sucedida.

from __future__ import annotations

from pathlib import Path
from typing import Optional


def gerar_thumbnail(
    proj_dir: Path,
    idioma: str,          # "pt" ou "en"
    titulo: str = "",
    saida: Optional[Path] = None,
) -> Optional[Path]:
    """
    Cria thumbnail 1280×720 a partir da primeira imagem de cena do projeto.

    Retorna o Path do arquivo gerado, ou None se Pillow não estiver disponível
    ou ocorrer qualquer erro.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        return None

    try:
        # ── Procura a imagem base ────────────────────────────────────────────
        cenas_dir = proj_dir / "projeto" / "cenas"
        img_base: Optional[Image.Image] = None

        if cenas_dir.exists():
            candidatos = []
            for nome in (f"abertura_{idioma}", "abertura", "1", "01", "10"):
                for ext in ("png", "jpg", "jpeg", "webp"):
                    p = cenas_dir / f"{nome}.{ext}"
                    if p.exists():
                        candidatos.append(p)
                        break
            if not candidatos:
                for ext in ("png", "jpg", "jpeg", "webp"):
                    candidatos.extend(sorted(cenas_dir.glob(f"*.{ext}")))

            for c in candidatos:
                try:
                    img_base = Image.open(c).convert("RGBA")
                    break
                except Exception:
                    continue

        # ── Canvas 1280×720 ──────────────────────────────────────────────────
        W, H = 1280, 720
        canvas = Image.new("RGBA", (W, H), (10, 10, 20, 255))

        if img_base:
            iw, ih = img_base.size
            scale = max(W / iw, H / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            img_r = img_base.resize((nw, nh), Image.LANCZOS)
            ox, oy = (nw - W) // 2, (nh - H) // 2
            img_crop = img_r.crop((ox, oy, ox + W, oy + H))
            # Suaviza levemente
            canvas = img_crop.filter(ImageFilter.GaussianBlur(radius=1)).convert("RGBA")

        # Gradient escuro no fundo para o texto ficar legível
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        for y in range(H):
            alpha = int(180 * (y / H) ** 0.5)
            draw_ov.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        canvas = Image.alpha_composite(canvas, overlay)

        # ── Texto do título ───────────────────────────────────────────────────
        if titulo:
            draw = ImageDraw.Draw(canvas)

            # Tenta carregar fonte bold; fallback para default
            font_titulo = font_sub = None
            for fname in (
                "arialbold.ttf", "arialbd.ttf", "Arial Bold.ttf",
                "DejaVuSans-Bold.ttf", "FreeSansBold.ttf",
            ):
                try:
                    font_titulo = ImageFont.truetype(fname, 68)
                    font_sub    = ImageFont.truetype(fname, 32)
                    break
                except Exception:
                    pass
            if font_titulo is None:
                try:
                    font_titulo = ImageFont.load_default(size=60)
                    font_sub    = ImageFont.load_default(size=28)
                except Exception:
                    font_titulo = ImageFont.load_default()
                    font_sub    = font_titulo

            # Quebra título em linhas de no máximo ~W-100px
            def _quebrar(texto: str, font, max_w: int) -> list[str]:
                palavras = texto.split()
                linhas, linha_atual = [], []
                for p in palavras:
                    teste = " ".join(linha_atual + [p])
                    try:
                        w = draw.textlength(teste, font=font)
                    except Exception:
                        w = len(teste) * 38
                    if w > max_w and linha_atual:
                        linhas.append(" ".join(linha_atual))
                        linha_atual = [p]
                    else:
                        linha_atual.append(p)
                if linha_atual:
                    linhas.append(" ".join(linha_atual))
                return linhas or [texto]

            linhas = _quebrar(titulo, font_titulo, W - 100)
            line_h = 78
            total_h = len(linhas) * line_h
            y0 = H - total_h - 70

            for i, ln in enumerate(linhas):
                y = y0 + i * line_h
                # Sombra
                draw.text((42, y + 3), ln, font=font_titulo, fill=(0, 0, 0, 200))
                # Texto branco
                draw.text((40, y), ln, font=font_titulo, fill=(255, 255, 255, 255))

            # Badge de idioma (pequeno, canto superior direito)
            badge = idioma.upper()
            draw.rectangle([W - 70, 12, W - 12, 48], fill=(220, 30, 50, 230))
            try:
                draw.text((W - 42, 18), badge, font=font_sub,
                          fill=(255, 255, 255, 255), anchor="mm")
            except Exception:
                draw.text((W - 58, 18), badge, font=font_sub,
                          fill=(255, 255, 255, 255))

        # ── Salva como JPEG ───────────────────────────────────────────────────
        if saida is None:
            videos_dir = proj_dir / "videos"
            videos_dir.mkdir(parents=True, exist_ok=True)
            saida = videos_dir / f"thumbnail_{idioma}.jpg"

        canvas.convert("RGB").save(str(saida), "JPEG", quality=93, optimize=True)
        return saida

    except Exception:
        return None


def gerar_thumbnails_pos_geracao(proj_dir: Path, modo: str, titulo: str = "") -> list[Path]:
    """
    Gera thumbnails para todos os idiomas do modo ("pt+en", "pt", "en").
    Retorna lista dos paths gerados (pode ser vazia se Pillow não disponível).
    """
    linguas = []
    if "pt" in modo:
        linguas.append("pt")
    if "en" in modo:
        linguas.append("en")

    gerados = []
    for lang in linguas:
        p = gerar_thumbnail(proj_dir, lang, titulo=titulo)
        if p:
            gerados.append(p)
    return gerados
