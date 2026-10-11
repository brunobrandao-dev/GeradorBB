# Rankadorama — contexto do projeto

## O que é
Ferramenta de linha de comando que gera automaticamente vídeos verticais "Top 10" no estilo YouTube Shorts/Reels. Produz dois vídeos por rodada: um em português e um em inglês.

Canal: @RankaDorama (dramas coreanos/asiáticos).

## Como funciona
1. O usuário coloca as imagens em `imagens/`, os roteiros em `roteiro/`, os áudios em `audio/` e opcionalmente música em `musica/`.
2. Roda `GERAR.bat` (que chama `python gerar_video.py`).
3. Um menu interativo é exibido com as opções disponíveis.
4. Os vídeos finais aparecem em `saida/` com nome `rankadorama_pt_YYYY-MM-DD_HHMM.mp4` e `rankadorama_en_...mp4`.

## Menu interativo

O programa exibe um menu ao iniciar:

```
🎬 RANKADORAMA
━━━━━━━━━━━━━━━━━━━━━━━
[1] Gerar vídeos PT + EN
[2] Gerar só PT
[3] Gerar só EN
[4] Ajustar imagens
[0] Sair
━━━━━━━━━━━━━━━━━━━━━━━
```

- Opções 1-3 chamam `gerar_videos(linguas)` com a lista correspondente
- Opção 4 chama `menu_ajustar_imagens()` de `imagens.py`
- Opção 0 encerra com `sys.exit(0)`
- Após cada operação, volta ao menu (loop `while True`)
- Após gerar vídeos, pergunta se o usuário quer abrir a pasta `saida/`

## Estrutura das pastas

```
rankadorama/
  gerar_video.py        ← script principal + menu
  imagens.py            ← módulo de ajuste de imagens
  GERAR.bat             ← atalho para rodar no Windows
  LEIA-ME.txt           ← instruções para o usuário final
  requirements.txt      ← faster-whisper, pillow + opcionais
  imagens/              ← abertura_pt, abertura_en, 1..10, fechamento_pt, fechamento_en
  roteiro/              ← elevenlabs_pt.txt, legendas_pt.txt, elevenlabs_en.txt, legendas_en.txt
  audio/                ← pt.mp3, en.mp3 (ou qualquer nome; o programa detecta o idioma)
  musica/               ← (opcional) uma música de fundo
  saida/                ← vídeos gerados
  ajusteimagens/        ← imagens brutas para ajuste (entrada do imagens.py)
  imagemajustada/       ← imagens processadas pelo imagens.py (saída)
```

## Regras de nomenclatura dos arquivos de entrada

### Imagens (`imagens/`)
- Abertura: `abertura_pt.png` e `abertura_en.png` (ou `abertura.png` se for igual para os dois)
- Itens: `1.png` a `10.png` (pode ter prefixo/sufixo qualquer, desde que tenha o número)
- Fechamento: `fechamento_pt.png` e `fechamento_en.png` (ou `fechamento.png`)
- Logo: `logo.png` — PNG com fundo transparente; substitui o texto `MARCA_DAGUA`; o programa recorta bordas transparentes, redimensiona para `LARGURA_LOGO` px e cria sombra escura automática se `SOMBRA_LOGO = True`
- Formatos aceitos: `.png`, `.jpg`, `.jpeg`, `.webp`, `.mp4`, `.mov`, `.webm`, `.mkv`

### Roteiros (`roteiro/`)
- `elevenlabs_pt.txt` — texto enviado ao ElevenLabs para gerar o áudio PT
- `legendas_pt.txt`   — texto que aparece na legenda do vídeo PT (pode ser diferente, ex.: sem "(pause)")
- Idem para `_en`
- Se `legendas_*.txt` não existir, usa o próprio `elevenlabs_*.txt`

### Áudios (`audio/`)
- `pt.mp3` e `en.mp3` — ou qualquer nome com o código do idioma dentro

## Fluxo interno do script

1. `main()` exibe o menu e aguarda input do usuário
2. `gerar_videos(linguas)` orquestra a geração:
   - Verifica FFmpeg
   - Cria pastas necessárias
   - Carrega imagens para um dict keyed por `1..10`, `"abertura_pt"`, `"abertura_en"`, `"fechamento_pt"`, `"fechamento_en"`
   - Chama `preparar_logo()`
   - Para cada língua solicitada, verifica disponibilidade de roteiro e áudio antes de chamar `processar()`
3. Para cada idioma (`pt`, `en`) via `processar()`:
   - Lê o roteiro ElevenLabs e tokeniza
   - Roda o Whisper (`faster-whisper`, modelo `small` por padrão) no áudio → timestamps por palavra
   - Alinha tokens do roteiro com as palavras do Whisper via `difflib.SequenceMatcher`
   - Monta blocos de legenda (5 palavras por bloco, por padrão)
   - Renderiza cada imagem como trecho de vídeo com zoom lento (FFmpeg)
   - Concatena trechos, adiciona áudio + música de fundo + legenda ASS queimada
   - Salva `.mp4` e `.srt` em `saida/`

## Módulo imagens.py

Arquivo `imagens.py` na raiz do projeto. Chamado pela opção 4 do menu.

### Funções

| Função | Descrição |
|--------|-----------|
| `menu_ajustar_imagens()` | Menu interativo: escolhe entre modo 1 (remover texto + tamanho) ou modo 2 (só tamanho) |
| `processar_imagem(caminho, modo)` | Processa uma imagem: remove texto (modo 1) e/ou padroniza tamanho |
| `detectar_e_remover_texto(img_pil)` | EasyOCR detecta texto + LaMa faz inpainting na máscara |
| `upscale_se_necessario(img_pil)` | Amplia com Real-ESRGAN (se disponível) ou LANCZOS |
| `padronizar_tamanho(img_pil)` | Crop centralizado se proporção próxima; fundo desfocado se muito diferente |

### Fluxo do modo 1 (remover texto + tamanho)
1. EasyOCR detecta bounding boxes de texto na imagem
2. Cria máscara branca nas regiões de texto (com margem `MARGEM_MASCARA`)
3. LaMa (SimpleLama) faz inpainting: reconstrói as regiões mascaradas
4. Salva versão `_original.png` (sem inpainting, mas com tamanho certo)
5. Faz upscale se necessário → padroniza tamanho → salva versão final

### Fluxo do modo 2 (só tamanho)
1. Upscale se necessário
2. Padroniza tamanho (crop centralizado ou fundo desfocado)
3. Salva resultado

### Dependências opcionais
- `easyocr` — detecção de texto (~1.5 GB de modelos no primeiro uso)
- `simple-lama-inpainting` — remoção de texto (~750 MB de modelos no primeiro uso)
- `opencv-python-headless` — processamento de imagem auxiliar
- `realesrgan-ncnn-vulkan` — upscale de alta qualidade (binário externo, não é pip)

O módulo funciona sem as bibliotecas opcionais: modo 2 não precisa de nenhuma delas; modo 1 detecta ausência em runtime e exibe aviso.

## Configurações ajustáveis (topo do gerar_video.py)

| Variável             | Default          | Descrição |
|----------------------|------------------|-----------|
| `LARGURA, ALTURA`    | 1080 × 1920      | Tamanho do vídeo |
| `FPS`                | 30               | |
| `MODELO_WHISPER`     | `"small"`        | `"base"` (rápido) / `"medium"` (preciso) |
| `FUNDO`              | `"preto"`        | `"preto"` ou `"desfocado"` |
| `MARCA_DAGUA`        | `"@RankaDorama"` | Deixar `""` para remover |
| `PALAVRAS_POR_LEGENDA` | 5              | Palavras por bloco de legenda |
| `FONTE`              | `"Arial"`        | |
| `TAMANHO_FONTE`      | 64               | |
| `POSICAO_LEGENDA`    | 300              | Distância do fundo (px) |
| `ZOOM_MAXIMO`        | 0.06             | 6% de zoom por imagem |
| `VOLUME_MUSICA`      | 0.10             | Volume da música de fundo |
| `TAMANHO_IMAGEM`     | `(1792, 2400)`   | Tamanho alvo para ajuste de imagens (3:4) |
| `MARGEM_MASCARA`     | 20               | Pixels extras ao redor de texto detectado |
| `LINGUAS_OCR`        | `["pt","en","ko"]` | Idiomas reconhecidos pelo EasyOCR |
| `USAR_REAL_ESRGAN`   | `True`           | Usa Real-ESRGAN se disponível; senão LANCZOS |

## Dependências externas

- **Python 3.10+** — deve estar no PATH
- **FFmpeg** — deve estar no PATH (`winget install Gyan.FFmpeg`)
- **faster-whisper** — `pip install -r requirements.txt`
- **Pillow** — incluída no requirements.txt
- **easyocr** *(opcional)* — remoção de texto em imagens
- **simple-lama-inpainting** *(opcional)* — inpainting para remoção de texto
- **opencv-python-headless** *(opcional)* — processamento de imagem auxiliar
- **realesrgan-ncnn-vulkan** *(opcional, binário externo)* — upscale de alta qualidade

## O que ainda pode ser feito / pontos de atenção

- Os nomes de arquivo que vêm do ElevenLabs e do Leonardo podem ser qualquer coisa; o programa já lida com isso
- O roteiro pode ser colado inteiro em um único `.txt`; a limpeza `limpar_roteiro()` ignora cabeçalhos (`**`, `---`, emojis, `#`)
- A música de fundo é loop infinito cortado no fim do áudio
- Se o áudio passar de 180 s, o programa avisa (limite do YouTube Shorts)
- O `imagens.py` usa import lazy (`_cfg()`) para evitar circular import com `gerar_video.py`
