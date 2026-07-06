#!/usr/bin/env python3
"""
Banner Processor - StudioDelta.pl
Automatyzacja przygotowania bannerów wielkoformatowych.

Wymagane: pip install Pillow pypdfium2
"""

import sys
import os
import json
import argparse
from PIL import Image, ImageDraw

# ─── Domyślne parametry (cm) ────────────────────────────────────────────
DEFAULT_MARKER_SIZE_CM = 1.0     # Rozmiar celownika (10x10mm)
DEFAULT_MARGIN_CM = 2.0          # Odległość osi celownika od krawędzi
DEFAULT_TARGET_SPACING_CM = 50.0
DEFAULT_BORDER_CM = 3.6          # Biała ramka na zgrzew
DEFAULT_BORDER_ENABLED = True

# Linia wewnętrzna – w osi krawędzi obrazu (może lekko wciąć się w grafikę)
DEFAULT_INNER_LINE_ENABLED = True
DEFAULT_INNER_LINE_WIDTH_CM = 0.05   # ~0.5 mm
DEFAULT_INNER_LINE_OPACITY = 100     # 0-100%

# Linia zewnętrzna – na krawędzi białej ramki (na zgrzew)
DEFAULT_OUTER_LINE_ENABLED = True
DEFAULT_OUTER_LINE_WIDTH_CM = 0.03   # ~0.3 mm
DEFAULT_OUTER_LINE_OPACITY = 70      # 0-100%

DEFAULT_JPEG_QUALITY = 100
DEFAULT_PDF_DPI = 150            # rozdzielczość rasteryzacji plików PDF

CONFIG_FILENAME = "banner_processor_config.json"


def get_config_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, CONFIG_FILENAME)


def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(settings):
    path = get_config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    return path


def cm_to_px(cm, dpi):
    return round(cm / 2.54 * dpi)


def px_to_cm(px, dpi):
    return px * 2.54 / dpi


def calculate_positions(length_cm, edge_offset_cm, target_spacing_cm, forced_marks=None):
    """
    Zwraca pozycje osi celowników wzdłuż jednego boku (w cm, od krawędzi).
    Punkty skrajne leżą w odległości edge_offset_cm od krawędzi (do osi).
    Środkowe rozłożone są równo tak, aby odstęp między kolejnymi punktami
    przebicia był jak najbliższy docelowemu. Wszystkie odstępy są równe.

    forced_marks – jeśli podane, wymusza tę liczbę celowników na boku
    (ręczna korekta +/-); rozstaw wyliczany jest wtedy z tej liczby.
    """
    first_pos = edge_offset_cm
    last_pos = length_cm - edge_offset_cm
    span = last_pos - first_pos

    if span <= 0:
        return [length_cm / 2.0]

    if forced_marks is not None:
        n = max(1, int(forced_marks) - 1)
        spacing = span / n
        return [first_pos + i * spacing for i in range(n + 1)]

    if target_spacing_cm <= 0:
        return [first_pos, last_pos]

    # Liczba odstępów tak dobrana, by odstęp był najbliższy docelowemu.
    n = max(1, round(span / target_spacing_cm))
    spacing = span / n
    return [first_pos + i * spacing for i in range(n + 1)]


def get_white_color(mode):
    if mode == 'CMYK':
        return (0, 0, 0, 0)
    elif mode == 'RGB':
        return (255, 255, 255)
    return (0, 0, 0, 0)


def get_black_color(mode, opacity_pct=100):
    """Czarny z regulowanym nasyceniem (0-100%). W CMYK to kanał K."""
    val = round(255 * opacity_pct / 100)
    if mode == 'CMYK':
        return (0, 0, 0, val)
    elif mode == 'RGB':
        gray = 255 - val
        return (gray, gray, gray)
    return (0, 0, 0, val)


def get_gray_color(mode, lightness_pct=50):
    """Szary kolor. lightness_pct: 0=czarny, 100=biały."""
    if mode == 'CMYK':
        k = round(255 * (100 - lightness_pct) / 100)
        return (0, 0, 0, k)
    elif mode == 'RGB':
        v = round(255 * lightness_pct / 100)
        return (v, v, v)
    return (0, 0, 0, round(255 * (100 - lightness_pct) / 100))


def draw_crosshair(draw, cx_px, cy_px, size_px, mode):
    """
    Rysuje celownik (krzyżyk z kółkami) w stylu paserki drukarskiej.
    Szaro-biały, widoczny na każdym tle.
    cx_px, cy_px = środek celownika w pikselach
    size_px = rozmiar celownika (szerokość/wysokość kwadratu)
    """
    half = size_px // 2
    line_thick = max(1, size_px // 12)    # grubość linii krzyżyka
    outer_r = half                         # promień zewnętrznego koła
    inner_r = half // 2                    # promień wewnętrznego koła
    dot_r = max(1, size_px // 10)          # promień centralnej kropki

    white = get_white_color(mode)
    dark_gray = get_gray_color(mode, 30)   # ciemny szary
    light_gray = get_gray_color(mode, 70)  # jasny szary

    # Białe tło koła (żeby celownik był widoczny na ciemnym tle)
    draw.ellipse([cx_px - outer_r, cy_px - outer_r,
                  cx_px + outer_r, cy_px + outer_r], fill=white)

    # Krzyżyk — 4 ramiona (ciemny szary)
    # Poziome
    draw.rectangle([cx_px - half, cy_px - line_thick,
                    cx_px + half, cy_px + line_thick], fill=dark_gray)
    # Pionowe
    draw.rectangle([cx_px - line_thick, cy_px - half,
                    cx_px + line_thick, cy_px + half], fill=dark_gray)

    # Zewnętrzny ring (jasny szary)
    ring_thick = max(1, line_thick * 2)
    draw.ellipse([cx_px - outer_r, cy_px - outer_r,
                  cx_px + outer_r, cy_px + outer_r], outline=light_gray, width=ring_thick)

    # Wewnętrzny ring (ciemny szary)
    draw.ellipse([cx_px - inner_r, cy_px - inner_r,
                  cx_px + inner_r, cy_px + inner_r], outline=dark_gray, width=ring_thick)

    # Centralna biała kropka
    draw.ellipse([cx_px - dot_r, cy_px - dot_r,
                  cx_px + dot_r, cy_px + dot_r], fill=white)


def draw_edge_frame(draw, left, top, right, bottom, thickness_px, color):
    """
    Rysuje ramkę-linię WYŚRODKOWANĄ na krawędziach prostokąta [left,top,right,bottom].
    Linia leży w osi krawędzi: połowa grubości na zewnątrz, połowa do środka.
    """
    t = max(1, thickness_px)
    h = t // 2
    draw.rectangle([left - h, top - h, right + h, top + h], fill=color)        # góra
    draw.rectangle([left - h, bottom - h, right + h, bottom + h], fill=color)  # dół
    draw.rectangle([left - h, top - h, left + h, bottom + h], fill=color)      # lewo
    draw.rectangle([right - h, top - h, right + h, bottom + h], fill=color)    # prawo


def draw_outer_frame(draw, width, height, thickness_px, color):
    """Rysuje linię przy samej zewnętrznej krawędzi płótna (do środka)."""
    t = max(1, thickness_px)
    draw.rectangle([0, 0, width - 1, t - 1], fill=color)                 # góra
    draw.rectangle([0, height - t, width - 1, height - 1], fill=color)   # dół
    draw.rectangle([0, 0, t - 1, height - 1], fill=color)                # lewo
    draw.rectangle([width - t, 0, width - 1, height - 1], fill=color)    # prawo


def load_source_image(input_path, pdf_dpi=DEFAULT_PDF_DPI):
    """
    Wczytuje plik wejściowy jako obraz PIL. Dla PDF rasteryzuje pierwszą stronę
    przy zadanym DPI (rozmiar fizyczny bierze się z wymiarów strony PDF).
    """
    Image.MAX_IMAGE_PIXELS = None  # wielkoformatowe pliki przekraczają domyślny limit Pillow
    ext = os.path.splitext(input_path)[1].lower()

    if ext == '.pdf':
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise RuntimeError(
                "Obsługa PDF wymaga biblioteki pypdfium2. Zainstaluj: pip install pypdfium2")
        pdf = pdfium.PdfDocument(input_path)
        try:
            page = pdf[0]
            bitmap = page.render(scale=pdf_dpi / 72.0)
            # .copy() materializuje piksele – to_pil() współdzieli bufor pdfium,
            # który znika po zamknięciu dokumentu.
            img = bitmap.to_pil().copy()
        finally:
            pdf.close()
        img = _normalize_mode(img)
        img.info['dpi'] = (float(pdf_dpi), float(pdf_dpi))
        return img

    return _normalize_mode(Image.open(input_path))


def _normalize_mode(img):
    """Sprowadza obraz do trybu obsługiwanego przez rysowanie (RGB lub CMYK).
    Skala szarości, paleta, RGBA itp. są konwertowane do RGB, żeby uniknąć
    błędów kolorów przy nakładaniu celowników i ramek."""
    if img.mode not in ('RGB', 'CMYK'):
        img = img.convert('RGB')
    return img


def resolve_dimensions(width_px, height_px, orig_dpi_x, orig_dpi_y,
                       target_width_cm=None, target_height_cm=None):
    """Ustala wymiary w cm i efektywne DPI na podstawie pikseli i ewentualnych
    wartości podanych ręcznie. Zwraca słownik z width_cm, height_cm, dpi_x,
    dpi_y, avg_dpi i opisem źródła."""
    if target_width_cm and target_height_cm:
        width_cm = target_width_cm
        height_cm = target_height_cm
        dpi_x = width_px / width_cm * 2.54
        dpi_y = height_px / height_cm * 2.54
        avg_dpi = (dpi_x + dpi_y) / 2.0
        source = "RĘCZNIE PODANE"
    elif target_width_cm:
        width_cm = target_width_cm
        dpi_x = width_px / width_cm * 2.54
        dpi_y = dpi_x
        avg_dpi = dpi_x
        height_cm = px_to_cm(height_px, avg_dpi)
        source = "RĘCZNIE (szer.) + proporcja"
    elif target_height_cm:
        height_cm = target_height_cm
        dpi_y = height_px / height_cm * 2.54
        dpi_x = dpi_y
        avg_dpi = dpi_y
        width_cm = px_to_cm(width_px, avg_dpi)
        source = "RĘCZNIE (wys.) + proporcja"
    else:
        dpi_x, dpi_y = orig_dpi_x, orig_dpi_y
        avg_dpi = (dpi_x + dpi_y) / 2.0
        width_cm = px_to_cm(width_px, avg_dpi)
        height_cm = px_to_cm(height_px, avg_dpi)
        source = "Z DPI PLIKU"

    return {
        'width_cm': width_cm, 'height_cm': height_cm,
        'dpi_x': dpi_x, 'dpi_y': dpi_y, 'avg_dpi': avg_dpi, 'source': source,
    }


def read_dpi(img):
    """Zwraca (dpi_x, dpi_y, znalezione?) z metadanych obrazu."""
    dpi = img.info.get('dpi')
    if dpi is None:
        return 150.0, 150.0, False
    if isinstance(dpi, tuple):
        return float(dpi[0]), float(dpi[1]), True
    return float(dpi), float(dpi), True


def render_banner(img, avg_dpi, width_cm, height_cm,
                  marker_size_cm=DEFAULT_MARKER_SIZE_CM,
                  margin_cm=DEFAULT_MARGIN_CM,
                  target_spacing_cm=DEFAULT_TARGET_SPACING_CM,
                  border_cm=DEFAULT_BORDER_CM,
                  border_enabled=DEFAULT_BORDER_ENABLED,
                  inner_line_enabled=DEFAULT_INNER_LINE_ENABLED,
                  inner_line_width_cm=DEFAULT_INNER_LINE_WIDTH_CM,
                  inner_line_opacity=DEFAULT_INNER_LINE_OPACITY,
                  outer_line_enabled=DEFAULT_OUTER_LINE_ENABLED,
                  outer_line_width_cm=DEFAULT_OUTER_LINE_WIDTH_CM,
                  outer_line_opacity=DEFAULT_OUTER_LINE_OPACITY,
                  h_marks=None, v_marks=None, verbose=True):
    """
    Rdzeń przetwarzania: nakłada celowniki, białą ramkę i linie na podany obraz.
    Rysuje bezpośrednio na 'img' (rogi/celowniki), więc podawaj kopię jeśli
    oryginał ma zostać nienaruszony. Zwraca słownik z gotowym obrazem oraz
    liczbą oczek i rozstawem na każdym boku (do podglądu i korekty +/-).
    """
    mode = img.mode
    width_px, height_px = img.size

    def log(msg):
        if verbose:
            print(msg)

    # ── KROK 1: Celowniki na oryginalnym obrazie ──
    log("\n[1/3] Nakładanie celowników...")
    draw = ImageDraw.Draw(img)
    marker_size_px = cm_to_px(marker_size_cm, avg_dpi)

    # Wymiarowanie do OSI celownika: margin_cm to odległość osi od krawędzi.
    edge_offset_cm = margin_cm

    corners = [
        (edge_offset_cm, edge_offset_cm),
        (width_cm - edge_offset_cm, edge_offset_cm),
        (edge_offset_cm, height_cm - edge_offset_cm),
        (width_cm - edge_offset_cm, height_cm - edge_offset_cm),
    ]

    h_positions = calculate_positions(width_cm, edge_offset_cm, target_spacing_cm, h_marks)
    v_positions = calculate_positions(height_cm, edge_offset_cm, target_spacing_cm, v_marks)

    h_inner = h_positions[1:-1] if len(h_positions) >= 2 else []
    v_inner = v_positions[1:-1] if len(v_positions) >= 2 else []

    all_markers = list(corners)
    for x_cm in h_inner:
        all_markers.append((x_cm, edge_offset_cm))
        all_markers.append((x_cm, height_cm - edge_offset_cm))
    for y_cm in v_inner:
        all_markers.append((edge_offset_cm, y_cm))
        all_markers.append((width_cm - edge_offset_cm, y_cm))

    for x_cm, y_cm in all_markers:
        draw_crosshair(draw, cm_to_px(x_cm, avg_dpi), cm_to_px(y_cm, avg_dpi),
                       marker_size_px, mode)

    h_spacing = (h_positions[1] - h_positions[0]) if len(h_positions) >= 2 else 0.0
    v_spacing = (v_positions[1] - v_positions[0]) if len(v_positions) >= 2 else 0.0
    log(f"  Nałożono {len(all_markers)} celowników ({marker_size_cm*10:.0f}x{marker_size_cm*10:.0f} mm)")
    log(f"  Poziomo: {len(h_positions)} oczek na bok, "
        f"rozstaw co {h_spacing:.1f} cm (docelowo {target_spacing_cm:.0f})")
    log(f"  Pionowo: {len(v_positions)} oczek na bok, "
        f"rozstaw co {v_spacing:.1f} cm (docelowo {target_spacing_cm:.0f})")

    # ── KROK 2: Biała ramka na zgrzew ──
    white = get_white_color(mode)
    if border_enabled and border_cm > 0:
        log("\n[2/3] Dodawanie białej ramki na zgrzew...")
        border_px = cm_to_px(border_cm, avg_dpi)
        new_width = width_px + 2 * border_px
        new_height = height_px + 2 * border_px
        new_img = Image.new(mode, (new_width, new_height), white)
        new_img.paste(img, (border_px, border_px))
        log(f"  Ramka: {border_cm} cm = {border_px} px")
    else:
        log("\n[2/3] Biała ramka: WYŁĄCZONA")
        new_img = img
        new_width, new_height = width_px, height_px
        border_px = 0

    img_left, img_top = border_px, border_px
    img_right = border_px + width_px - 1
    img_bottom = border_px + height_px - 1

    # ── KROK 3: Linie (w osi krawędzi obrazu + na krawędzi ramki) ──
    log("\n[3/3] Rysowanie linii...")
    draw2 = ImageDraw.Draw(new_img)
    any_line = False

    if inner_line_enabled and inner_line_opacity > 0 and inner_line_width_cm > 0:
        inner_color = get_black_color(mode, inner_line_opacity)
        inner_w = max(1, cm_to_px(inner_line_width_cm, avg_dpi))
        draw_edge_frame(draw2, img_left, img_top, img_right, img_bottom, inner_w, inner_color)
        log(f"  Wewnętrzna: {inner_line_width_cm*10:.1f} mm | "
            f"nasycenie {inner_line_opacity}% (w osi krawędzi obrazu)")
        any_line = True

    if outer_line_enabled and outer_line_opacity > 0 and outer_line_width_cm > 0:
        outer_color = get_black_color(mode, outer_line_opacity)
        outer_w = max(1, cm_to_px(outer_line_width_cm, avg_dpi))
        draw_outer_frame(draw2, new_width, new_height, outer_w, outer_color)
        log(f"  Zewnętrzna: {outer_line_width_cm*10:.1f} mm | "
            f"nasycenie {outer_line_opacity}% (na krawędzi ramki)")
        any_line = True

    if not any_line:
        log("  Linie: WYŁĄCZONE")

    return {
        'image': new_img,
        'h_marks': len(h_positions),
        'v_marks': len(v_positions),
        'h_spacing': h_spacing,
        'v_spacing': v_spacing,
        'marker_count': len(all_markers),
    }


def process_banner(
    input_path,
    output_path=None,
    marker_size_cm=DEFAULT_MARKER_SIZE_CM,
    margin_cm=DEFAULT_MARGIN_CM,
    target_spacing_cm=DEFAULT_TARGET_SPACING_CM,
    border_cm=DEFAULT_BORDER_CM,
    border_enabled=DEFAULT_BORDER_ENABLED,
    inner_line_enabled=DEFAULT_INNER_LINE_ENABLED,
    inner_line_width_cm=DEFAULT_INNER_LINE_WIDTH_CM,
    inner_line_opacity=DEFAULT_INNER_LINE_OPACITY,
    outer_line_enabled=DEFAULT_OUTER_LINE_ENABLED,
    outer_line_width_cm=DEFAULT_OUTER_LINE_WIDTH_CM,
    outer_line_opacity=DEFAULT_OUTER_LINE_OPACITY,
    target_width_cm=None,
    target_height_cm=None,
    h_marks=None,
    v_marks=None,
    jpeg_quality=DEFAULT_JPEG_QUALITY,
    pdf_render_dpi=DEFAULT_PDF_DPI,
    save=True,
):
    # ── Otwieranie i odczyt parametrów ──
    img = load_source_image(input_path, pdf_render_dpi)
    mode = img.mode
    orig_dpi_x, orig_dpi_y, dpi_found = read_dpi(img)
    if not dpi_found:
        print("  UWAGA: plik nie zawiera metadanych DPI — przyjęto 150 DPI. Podaj wymiary ręcznie.")

    icc_profile = img.info.get('icc_profile', None)
    width_px, height_px = img.size

    dims = resolve_dimensions(width_px, height_px, orig_dpi_x, orig_dpi_y,
                              target_width_cm, target_height_cm)
    width_cm = dims['width_cm']
    height_cm = dims['height_cm']
    dpi_x = dims['dpi_x']
    dpi_y = dims['dpi_y']
    avg_dpi = dims['avg_dpi']
    size_source = dims['source']

    print(f"{'='*60}")
    print(f"  BANNER PROCESSOR - StudioDelta.pl")
    print(f"{'='*60}")
    print(f"  Plik:          {os.path.basename(input_path)}")
    print(f"  Tryb kolorów:  {mode}")
    print(f"  DPI oryg.:     {orig_dpi_x:.0f} x {orig_dpi_y:.0f}")
    print(f"  DPI efektywne: {dpi_x:.1f} x {dpi_y:.1f}")
    print(f"  Rozmiar px:    {width_px} x {height_px}")
    print(f"  Rozmiar cm:    {width_cm:.1f} x {height_cm:.1f}  [{size_source}]")
    if icc_profile:
        print(f"  Profil ICC:    TAK (zachowany)")
    print(f"{'='*60}")

    render = render_banner(
        img, avg_dpi, width_cm, height_cm,
        marker_size_cm=marker_size_cm, margin_cm=margin_cm,
        target_spacing_cm=target_spacing_cm,
        border_cm=border_cm, border_enabled=border_enabled,
        inner_line_enabled=inner_line_enabled, inner_line_width_cm=inner_line_width_cm,
        inner_line_opacity=inner_line_opacity,
        outer_line_enabled=outer_line_enabled, outer_line_width_cm=outer_line_width_cm,
        outer_line_opacity=outer_line_opacity,
        h_marks=h_marks, v_marks=v_marks, verbose=True)

    new_img = render['image']

    # ── Zapis lub zwrot ──
    result_info = {
        'image': new_img,
        'mode': mode,
        'dpi_x': dpi_x,
        'dpi_y': dpi_y,
        'icc_profile': icc_profile,
        'jpeg_quality': jpeg_quality,
        'width_cm': width_cm,
        'height_cm': height_cm,
        'avg_dpi': avg_dpi,
        'h_marks': render['h_marks'],
        'v_marks': render['v_marks'],
        'h_spacing': render['h_spacing'],
        'v_spacing': render['v_spacing'],
        'marker_count': render['marker_count'],
    }

    if output_path is None and not save:
        print(f"\n  Podgląd gotowy")
        return result_info

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_processed.jpg"

    save_kwargs = {'dpi': (dpi_x, dpi_y)}
    if icc_profile:
        save_kwargs['icc_profile'] = icc_profile

    ext_lower = os.path.splitext(output_path)[1].lower()
    if ext_lower in ('.jpg', '.jpeg'):
        save_kwargs['quality'] = jpeg_quality
        save_kwargs['subsampling'] = 0  # najlepsza jakość chroma
    elif ext_lower in ('.tif', '.tiff'):
        save_kwargs['compression'] = 'tiff_lzw'
    elif ext_lower == '.pdf':
        # Pillow zapisuje PDF jako raster; nie osadza profilu ICC.
        save_kwargs.pop('icc_profile', None)

    new_img.save(output_path, **save_kwargs)

    print(f"\n{'='*60}")
    print(f"  GOTOWE!")
    print(f"  Zapisano: {output_path}")
    print(f"  Tryb: {mode} | DPI: {dpi_x:.1f}x{dpi_y:.1f} | ICC: {'TAK' if icc_profile else 'NIE'}")
    print(f"{'='*60}")

    result_info['output_path'] = output_path
    return result_info


def probe_size_cm(input_path, pdf_dpi=DEFAULT_PDF_DPI,
                  target_width_cm=None, target_height_cm=None):
    """Zwraca (szerokość_cm, wysokość_cm) pliku bez pełnego przetwarzania."""
    img = load_source_image(input_path, pdf_dpi)
    dx, dy, _ = read_dpi(img)
    dims = resolve_dimensions(img.size[0], img.size[1], dx, dy,
                              target_width_cm, target_height_cm)
    return round(dims['width_cm'], 1), round(dims['height_cm'], 1)


def process_batch(input_paths, output_dir=None, output_ext='.jpg',
                  params=None, pdf_dpi=DEFAULT_PDF_DPI, tolerance_cm=0.2,
                  progress=None):
    """
    Przetwarza kilka plików tymi samymi ustawieniami. Wszystkie muszą mieć
    jednakowe wymiary wydruku – jeśli któryś się różni, zgłasza błąd i nie
    przetwarza niczego.

    progress – opcjonalny callback(i, total, nazwa_pliku) wołany przed każdym
    plikiem (do paska postępu w GUI).
    """
    params = dict(params or {})
    target_w = params.get('target_width_cm')
    target_h = params.get('target_height_cm')

    sizes = {p: probe_size_cm(p, pdf_dpi, target_w, target_h) for p in input_paths}
    ref = sizes[input_paths[0]]

    def matches(s):
        return abs(s[0] - ref[0]) <= tolerance_cm and abs(s[1] - ref[1]) <= tolerance_cm

    if not all(matches(s) for s in sizes.values()):
        listing = "\n".join(
            f"    {'OK ' if matches(s) else '>>>'} {os.path.basename(p)}: {s[0]}x{s[1]} cm"
            for p, s in sizes.items())
        raise ValueError(
            "Pliki mają różne wymiary wydruku (wymagane jednakowe):\n" + listing)

    outputs = []
    total = len(input_paths)
    for i, p in enumerate(input_paths, 1):
        if progress:
            progress(i, total, os.path.basename(p))
        base = os.path.splitext(os.path.basename(p))[0]
        out_dir = output_dir or os.path.dirname(p)
        out = os.path.join(out_dir, f"{base}_processed{output_ext}")
        process_banner(input_path=p, output_path=out, pdf_render_dpi=pdf_dpi, **params)
        outputs.append(out)
    return outputs


# ─── GUI ─────────────────────────────────────────────────────────────────

def run_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        from PIL import ImageTk
    except ImportError:
        print("Brak modułu tkinter. Użyj wiersza poleceń.")
        sys.exit(1)

    # Drag & drop jest opcjonalny – jeśli biblioteki brak, program działa bez niego.
    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES
        DND_AVAILABLE = True
    except Exception:
        TkinterDnD = None
        DND_FILES = None
        DND_AVAILABLE = False

    WORK_MAX_PX = 1400   # maksymalny dłuższy bok kopii roboczej podglądu

    class CollapsibleFrame(ttk.Frame):
        def __init__(self, parent, text="", default_open=True, on_toggle=None, **kwargs):
            super().__init__(parent, **kwargs)
            self.is_open = default_open
            self.on_toggle = on_toggle
            self.label_text = text
            self.toggle_btn = ttk.Button(
                self, text=f"{'▼' if self.is_open else '▶'}  {text}",
                command=self.toggle, style='Toolbutton')
            self.toggle_btn.pack(fill='x')
            self.content = ttk.Frame(self)
            if self.is_open:
                self.content.pack(fill='x', padx=12, pady=(2, 6))

        def toggle(self):
            self.is_open = not self.is_open
            self.toggle_btn.config(text=f"{'▼' if self.is_open else '▶'}  {self.label_text}")
            if self.is_open:
                self.content.pack(fill='x', padx=12, pady=(2, 6))
            else:
                self.content.pack_forget()
            if self.on_toggle:
                self.on_toggle()

    class BannerApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Banner Processor - StudioDelta.pl")

            cfg = load_config()
            self.root.minsize(1040, 640)
            geom = cfg.get('window_geometry')
            if geom:
                self.root.geometry(geom)
            else:
                try:
                    self.root.state('zoomed')
                except tk.TclError:
                    self.root.geometry("1280x820")

            # ── stan ──
            self.last_dir = cfg.get('last_dir') or None
            self.last_out_dir = None
            self.files = []
            self.current_index = 0
            self.source_img = None
            self.work_img = None
            self.preview_pil = None
            self.tk_img = None
            self.orig_dpi = (150.0, 150.0)
            self.src_w_cm = self.src_h_cm = 0.0
            self._aspect = 1.0
            self.h_override = None
            self.v_override = None
            self._last_h = 2
            self._last_v = 2
            self._render_job = None
            self._loading = False
            self._need_fit = True

            # zoom / pan
            self.zoom = 1.0
            self.fit_zoom = 1.0
            self.offset = [0, 0]
            self._drag = None

            # pola numeryczne jako StringVar – akceptują przecinek
            self.marker_size = tk.StringVar(value=self._fmt(cfg.get('marker_size', DEFAULT_MARKER_SIZE_CM)))
            self.margin = tk.StringVar(value=self._fmt(cfg.get('margin', DEFAULT_MARGIN_CM)))
            self.target_spacing = tk.StringVar(value=self._fmt(cfg.get('target_spacing', DEFAULT_TARGET_SPACING_CM)))
            self.border_cm = tk.StringVar(value=self._fmt(cfg.get('border', DEFAULT_BORDER_CM)))
            self.border_enabled = tk.BooleanVar(value=cfg.get('border_enabled', DEFAULT_BORDER_ENABLED))

            self.inner_line_enabled = tk.BooleanVar(value=cfg.get('inner_line_enabled', DEFAULT_INNER_LINE_ENABLED))
            self.inner_line_width = tk.StringVar(value=self._fmt(cfg.get('inner_line_width', DEFAULT_INNER_LINE_WIDTH_CM)))
            self.inner_line_opacity = tk.IntVar(value=cfg.get('inner_line_opacity', DEFAULT_INNER_LINE_OPACITY))

            self.outer_line_enabled = tk.BooleanVar(
                value=cfg.get('outer_line_enabled', cfg.get('outline_enabled', DEFAULT_OUTER_LINE_ENABLED)))
            self.outer_line_width = tk.StringVar(
                value=self._fmt(cfg.get('outer_line_width', cfg.get('line_width', DEFAULT_OUTER_LINE_WIDTH_CM))))
            self.outer_line_opacity = tk.IntVar(
                value=cfg.get('outer_line_opacity', cfg.get('line_opacity', DEFAULT_OUTER_LINE_OPACITY)))

            self.target_width = tk.StringVar(value="")
            self.target_height = tk.StringVar(value="")
            self.lock_aspect = tk.BooleanVar(value=True)
            self.pdf_dpi = tk.StringVar(value=str(cfg.get('pdf_dpi', DEFAULT_PDF_DPI)))
            self.out_format = tk.StringVar(value=cfg.get('out_format', 'jpg'))

            # etykiety dynamiczne
            self.file_info = tk.StringVar(value="Nie wczytano pliku")
            self.warn = tk.StringVar(value="")
            self.h_count_lbl = tk.StringVar(value="—")
            self.v_count_lbl = tk.StringVar(value="—")
            self.zoom_lbl = tk.StringVar(value="100%")
            self.status = tk.StringVar(value="Wczytaj plik, aby zacząć. "
                                             + ("Możesz też przeciągnąć pliki do okna." if DND_AVAILABLE else ""))
            self._suppress_dim_trace = False

            self.build_ui()
            self._bind_live_updates()
            self._bind_shortcuts()
            self._enable_dnd()
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # ── pomocnicze ──
        @staticmethod
        def _fmt(value):
            f = float(value)
            return str(int(f)) if f == int(f) else str(f)

        @staticmethod
        def _pf(text, default=0.0):
            s = str(text).strip().replace(',', '.')
            if not s:
                return default
            try:
                return float(s)
            except ValueError:
                return default

        def get_current_settings(self):
            return {
                'marker_size': self._pf(self.marker_size.get(), DEFAULT_MARKER_SIZE_CM),
                'margin': self._pf(self.margin.get(), DEFAULT_MARGIN_CM),
                'target_spacing': self._pf(self.target_spacing.get(), DEFAULT_TARGET_SPACING_CM),
                'border': self._pf(self.border_cm.get(), DEFAULT_BORDER_CM),
                'border_enabled': self.border_enabled.get(),
                'inner_line_enabled': self.inner_line_enabled.get(),
                'inner_line_width': self._pf(self.inner_line_width.get(), DEFAULT_INNER_LINE_WIDTH_CM),
                'inner_line_opacity': self.inner_line_opacity.get(),
                'outer_line_enabled': self.outer_line_enabled.get(),
                'outer_line_width': self._pf(self.outer_line_width.get(), DEFAULT_OUTER_LINE_WIDTH_CM),
                'outer_line_opacity': self.outer_line_opacity.get(),
                'pdf_dpi': int(self._pf(self.pdf_dpi.get(), DEFAULT_PDF_DPI)),
            }

        def save_settings(self):
            try:
                cfg = load_config()
                cfg.update(self.get_current_settings())
                path = save_config(cfg)
                messagebox.showinfo("Zapisano", f"Ustawienia zapisane.\n{path}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się zapisać:\n{e}")

        def _bind_shortcuts(self):
            self.root.bind('<Control-o>', lambda e: self.browse_files())
            self.root.bind('<Control-O>', lambda e: self.browse_files())
            self.root.bind('<Control-s>', lambda e: self.save_single())
            self.root.bind('<Control-S>', lambda e: self.save_single())
            self.root.bind('<Control-0>', lambda e: self.fit_view())
            self.root.bind('<Control-equal>', lambda e: self.zoom_by(1.25))
            self.root.bind('<Control-plus>', lambda e: self.zoom_by(1.25))
            self.root.bind('<Control-minus>', lambda e: self.zoom_by(1 / 1.25))

        def _enable_dnd(self):
            if not DND_AVAILABLE:
                return
            try:
                for w in (self.canvas, self.root):
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind('<<Drop>>', self.on_drop)
            except Exception:
                pass

        def on_drop(self, event):
            self._load_paths(self._parse_drop(event.data))

        @staticmethod
        def _parse_drop(data):
            import re
            parts = re.findall(r'\{[^{}]*\}|\S+', data)
            return [p.strip('{}') for p in parts]

        def on_close(self):
            try:
                cfg = load_config()
                try:
                    zoomed = self.root.state() == 'zoomed'
                except tk.TclError:
                    zoomed = False
                if zoomed:
                    cfg.pop('window_geometry', None)
                else:
                    cfg['window_geometry'] = self.root.geometry()
                if self.last_dir:
                    cfg['last_dir'] = self.last_dir
                cfg['out_format'] = self.out_format.get()
                save_config(cfg)
            except Exception:
                pass
            self.root.destroy()

        def open_result_folder(self):
            folder = self.last_out_dir
            if folder and os.path.isdir(folder):
                try:
                    os.startfile(folder)
                except Exception as e:
                    messagebox.showerror("Błąd", f"Nie udało się otworzyć folderu:\n{e}")

        # ── budowa interfejsu ──
        def build_ui(self):
            # pasek górny
            top = ttk.Frame(self.root, padding=(8, 6))
            top.pack(side='top', fill='x')
            ttk.Button(top, text="📂  Wczytaj plik(i)…", command=self.browse_files).pack(side='left')
            self.file_combo = ttk.Combobox(top, state='readonly', width=32, values=[])
            self.file_combo.pack(side='left', padx=(8, 0))
            self.file_combo.bind('<<ComboboxSelected>>', self.on_file_selected)

            ttk.Label(top, text="Format:").pack(side='left', padx=(12, 2))
            ttk.Combobox(top, textvariable=self.out_format, state='readonly', width=6,
                         values=['jpg', 'tif', 'png', 'pdf']).pack(side='left')

            self.open_folder_btn = ttk.Button(top, text="Otwórz folder wyniku",
                                              command=self.open_result_folder, state='disabled')
            self.open_folder_btn.pack(side='right', padx=(8, 0))
            self.batch_btn = ttk.Button(top, text="Zapisz wszystkie (wsad)…",
                                        command=self.save_batch, state='disabled')
            self.batch_btn.pack(side='right')
            self.save_btn = ttk.Button(top, text="💾  Zapisz…", command=self.save_single, state='disabled')
            self.save_btn.pack(side='right', padx=(0, 8))

            ttk.Separator(self.root, orient='horizontal').pack(side='top', fill='x')

            # główny podział: lewy panel + podgląd
            body = ttk.Frame(self.root)
            body.pack(side='top', fill='both', expand=True)

            left_wrap = ttk.Frame(body, width=340)
            left_wrap.pack(side='left', fill='y')
            left_wrap.pack_propagate(False)
            self._build_left_panel(left_wrap)

            ttk.Separator(body, orient='vertical').pack(side='left', fill='y')

            right = ttk.Frame(body)
            right.pack(side='left', fill='both', expand=True)
            self._build_preview(right)

            # pasek statusu
            status = ttk.Frame(self.root, padding=(8, 3))
            status.pack(side='bottom', fill='x')
            ttk.Label(status, textvariable=self.status, font=('Segoe UI', 9)).pack(side='left')

        def _build_left_panel(self, parent):
            canvas = tk.Canvas(parent, highlightthickness=0, width=320)
            sb = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=sb.set)
            sb.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            inner = ttk.Frame(canvas)
            win = canvas.create_window((0, 0), window=inner, anchor='nw')
            canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))
            inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units'))
            self.left_scroll = canvas

            pad = {'padx': 10, 'pady': 2}

            ttk.Label(inner, textvariable=self.file_info, font=('Consolas', 8),
                      foreground='gray', wraplength=300, justify='left').pack(anchor='w', **pad)
            ttk.Label(inner, textvariable=self.warn, font=('Segoe UI', 8, 'bold'),
                      foreground='#c0392b', wraplength=300, justify='left').pack(anchor='w', **pad)

            # Wymiary
            fs = ttk.LabelFrame(inner, text="Wymiary wydruku (bez ramki)", padding=8)
            fs.pack(fill='x', **pad)
            row = ttk.Frame(fs); row.pack(fill='x', pady=2)
            ttk.Label(row, text="Szer. (cm):", width=11).pack(side='left')
            ttk.Entry(row, textvariable=self.target_width, width=8).pack(side='left')
            ttk.Label(row, text="Wys. (cm):", width=10).pack(side='left', padx=(8, 0))
            ttk.Entry(row, textvariable=self.target_height, width=8).pack(side='left')
            ttk.Checkbutton(fs, text="Zablokuj proporcje", variable=self.lock_aspect).pack(anchor='w', pady=(3, 0))
            self.target_width.trace_add('write', lambda *a: self._on_dim_change('w'))
            self.target_height.trace_add('write', lambda *a: self._on_dim_change('h'))

            # Celowniki
            fc = ttk.LabelFrame(inner, text="Celowniki (miejsca na oczka)", padding=8)
            fc.pack(fill='x', **pad)
            for label, var in [("Rozmiar celownika (cm):", self.marker_size),
                               ("Odległość osi od krawędzi (cm):", self.margin),
                               ("Docelowy rozstaw (cm):", self.target_spacing)]:
                r = ttk.Frame(fc); r.pack(fill='x', pady=1)
                ttk.Label(r, text=label, width=27).pack(side='left')
                ttk.Entry(r, textvariable=var, width=7).pack(side='left')

            ttk.Separator(fc, orient='horizontal').pack(fill='x', pady=6)

            # korekta liczby oczek +/-
            gh = ttk.Frame(fc); gh.pack(fill='x', pady=2)
            ttk.Label(gh, text="Poziom:", width=8).pack(side='left')
            ttk.Button(gh, text="−", width=3, command=self.h_minus).pack(side='left')
            ttk.Button(gh, text="+", width=3, command=self.h_plus).pack(side='left', padx=(2, 6))
            ttk.Label(gh, textvariable=self.h_count_lbl, font=('Segoe UI', 9, 'bold')).pack(side='left')

            gv = ttk.Frame(fc); gv.pack(fill='x', pady=2)
            ttk.Label(gv, text="Pion:", width=8).pack(side='left')
            ttk.Button(gv, text="−", width=3, command=self.v_minus).pack(side='left')
            ttk.Button(gv, text="+", width=3, command=self.v_plus).pack(side='left', padx=(2, 6))
            ttk.Label(gv, textvariable=self.v_count_lbl, font=('Segoe UI', 9, 'bold')).pack(side='left')

            # Ramka i linie
            fb = ttk.LabelFrame(inner, text="Ramka i linie", padding=8)
            fb.pack(fill='x', **pad)
            ttk.Checkbutton(fb, text="Biała ramka na zgrzew", variable=self.border_enabled).pack(anchor='w')
            r = ttk.Frame(fb); r.pack(fill='x', pady=(1, 4))
            ttk.Label(r, text="Szerokość ramki (cm):", width=27).pack(side='left')
            ttk.Entry(r, textvariable=self.border_cm, width=7).pack(side='left')

            ttk.Separator(fb, orient='horizontal').pack(fill='x', pady=5)
            ttk.Checkbutton(fb, text="Linia wewnętrzna (w osi krawędzi obrazu)",
                            variable=self.inner_line_enabled).pack(anchor='w')
            self._line_row(fb, "Grubość (cm):", self.inner_line_width)
            self._opacity_row(fb, "Nasycenie (%):", self.inner_line_opacity)

            ttk.Separator(fb, orient='horizontal').pack(fill='x', pady=5)
            ttk.Checkbutton(fb, text="Linia zewnętrzna (na krawędzi ramki)",
                            variable=self.outer_line_enabled).pack(anchor='w')
            self._line_row(fb, "Grubość (cm):", self.outer_line_width)
            self._opacity_row(fb, "Nasycenie (%):", self.outer_line_opacity)

            # PDF
            fp = ttk.LabelFrame(inner, text="PDF", padding=8)
            fp.pack(fill='x', **pad)
            r = ttk.Frame(fp); r.pack(fill='x')
            ttk.Label(r, text="Rozdzielczość rasteryzacji (DPI):", width=27).pack(side='left')
            ttk.Entry(r, textvariable=self.pdf_dpi, width=7).pack(side='left')

            ttk.Button(inner, text="Zapisz ustawienia jako domyślne",
                       command=self.save_settings).pack(anchor='e', padx=10, pady=(4, 12))

        def _line_row(self, parent, label, var):
            r = ttk.Frame(parent); r.pack(fill='x', pady=1)
            ttk.Label(r, text="   " + label, width=27).pack(side='left')
            ttk.Entry(r, textvariable=var, width=7).pack(side='left')

        def _opacity_row(self, parent, label, var):
            r = ttk.Frame(parent); r.pack(fill='x', pady=(0, 3))
            ttk.Label(r, text="   " + label, width=20).pack(side='left')
            ttk.Scale(r, from_=0, to=100, variable=var, orient='horizontal').pack(side='left', fill='x', expand=True)
            ttk.Label(r, textvariable=var, width=4).pack(side='left')

        def _build_preview(self, parent):
            bar = ttk.Frame(parent, padding=(6, 4))
            bar.pack(side='top', fill='x')
            ttk.Button(bar, text="Dopasuj", command=self.fit_view).pack(side='left')
            ttk.Button(bar, text="−", width=3, command=lambda: self.zoom_by(1 / 1.25)).pack(side='left', padx=(8, 2))
            ttk.Label(bar, textvariable=self.zoom_lbl, width=6, anchor='center').pack(side='left')
            ttk.Button(bar, text="+", width=3, command=lambda: self.zoom_by(1.25)).pack(side='left', padx=(2, 0))
            ttk.Label(bar, text="   kółko = zoom, przeciąganie = przesuwanie",
                      foreground='gray', font=('Segoe UI', 8)).pack(side='left', padx=8)

            self.canvas = tk.Canvas(parent, background='#2b2b2b', highlightthickness=0)
            self.canvas.pack(side='top', fill='both', expand=True)
            self.canvas.bind('<Configure>', self._on_canvas_configure)
            self.canvas.bind('<MouseWheel>', self.on_wheel)
            self.canvas.bind('<ButtonPress-1>', self.on_press)
            self.canvas.bind('<B1-Motion>', self.on_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_release)
            self.canvas.create_text(20, 20, anchor='nw', fill='#888',
                                    text="Wczytaj plik, aby zobaczyć podgląd.")

        # ── wczytywanie plików ──
        def browse_files(self):
            paths = filedialog.askopenfilenames(
                title="Wybierz plik(i) bannera",
                initialdir=self.last_dir or '',
                filetypes=[
                    ("Pliki graficzne", "*.tif *.tiff *.psd *.png *.jpg *.jpeg *.bmp *.pdf"),
                    ("PDF", "*.pdf"),
                    ("TIFF", "*.tif *.tiff"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Wszystkie", "*.*"),
                ])
            if paths:
                self._load_paths(paths)

        def _load_paths(self, paths):
            paths = [p for p in paths if os.path.isfile(p)]
            if not paths:
                return
            self.files = list(paths)
            self.current_index = 0
            self.file_combo['values'] = [os.path.basename(p) for p in self.files]
            self.file_combo.current(0)
            self.batch_btn.config(state='normal' if len(self.files) > 1 else 'disabled')
            self.last_dir = os.path.dirname(paths[0]) or self.last_dir
            self.load_current()

        def on_file_selected(self, event):
            idx = self.file_combo.current()
            if idx >= 0 and idx != self.current_index:
                self.current_index = idx
                self.load_current()

        def load_current(self):
            path = self.files[self.current_index]
            try:
                img = load_source_image(path, int(self._pf(self.pdf_dpi.get(), DEFAULT_PDF_DPI)))
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się wczytać pliku:\n{e}")
                return

            self._loading = True
            self.source_img = img
            self._src_px = img.size
            dx, dy, found = read_dpi(img)
            self._dpi_found = found
            self.orig_dpi = (dx, dy)
            avg = (dx + dy) / 2.0
            self.src_w_cm = px_to_cm(img.size[0], avg)
            self.src_h_cm = px_to_cm(img.size[1], avg)
            self._aspect = img.size[0] / img.size[1] if img.size[1] else 1.0

            self.target_width.set(self._fmt(round(self.src_w_cm, 1)))
            self.target_height.set(self._fmt(round(self.src_h_cm, 1)))

            # kopia robocza do szybkiego podglądu
            w, h = img.size
            scale = min(1.0, WORK_MAX_PX / max(w, h))
            self.work_img = img.resize((max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1.0 else img.copy()

            self.h_override = self.v_override = None
            self._need_fit = True
            icc = "TAK" if img.info.get('icc_profile') else "NIE"
            dpi_txt = f"{dx:.0f}x{dy:.0f} DPI" if found else "brak DPI (przyjęto 150)"
            self.file_info.set(
                f"{os.path.basename(path)}\n{img.mode} | {dpi_txt} | "
                f"{img.size[0]}x{img.size[1]} px | {self.src_w_cm:.1f}x{self.src_h_cm:.1f} cm | ICC: {icc}")
            self._loading = False
            self.render_now()

        # ── proporcje / live update ──
        def _on_dim_change(self, which):
            if not self._suppress_dim_trace and self.lock_aspect.get() and self._aspect:
                self._suppress_dim_trace = True
                try:
                    if which == 'w':
                        w = self._pf(self.target_width.get(), 0)
                        self.target_height.set(self._fmt(round(w / self._aspect, 1)) if w > 0 else "")
                    else:
                        h = self._pf(self.target_height.get(), 0)
                        self.target_width.set(self._fmt(round(h * self._aspect, 1)) if h > 0 else "")
                finally:
                    self._suppress_dim_trace = False
            self.schedule_render(reset=True)

        def _bind_live_updates(self):
            for v in [self.marker_size, self.margin, self.border_cm,
                      self.inner_line_width, self.inner_line_opacity,
                      self.outer_line_width, self.outer_line_opacity,
                      self.border_enabled, self.inner_line_enabled, self.outer_line_enabled]:
                v.trace_add('write', lambda *a: self.schedule_render())
            self.target_spacing.trace_add('write', lambda *a: self.schedule_render(reset=True))

        def schedule_render(self, reset=False):
            if self._loading:
                return
            if reset:
                self.h_override = self.v_override = None
            if self._render_job:
                self.root.after_cancel(self._render_job)
            self._render_job = self.root.after(250, self.render_now)

        def _target_dims(self):
            t_w = self._pf(self.target_width.get(), 0)
            t_h = self._pf(self.target_height.get(), 0)
            t_w = t_w if t_w > 0 else None
            t_h = t_h if t_h > 0 else None
            if t_w and t_h:
                return t_w, t_h
            if t_w:
                return t_w, t_w / self._aspect
            if t_h:
                return t_h * self._aspect, t_h
            return self.src_w_cm, self.src_h_cm

        def _core_params(self):
            t_w = self._pf(self.target_width.get(), 0)
            t_h = self._pf(self.target_height.get(), 0)
            return dict(
                marker_size_cm=self._pf(self.marker_size.get(), DEFAULT_MARKER_SIZE_CM),
                margin_cm=self._pf(self.margin.get(), DEFAULT_MARGIN_CM),
                target_spacing_cm=self._pf(self.target_spacing.get(), DEFAULT_TARGET_SPACING_CM),
                border_cm=self._pf(self.border_cm.get(), DEFAULT_BORDER_CM),
                border_enabled=self.border_enabled.get(),
                inner_line_enabled=self.inner_line_enabled.get(),
                inner_line_width_cm=self._pf(self.inner_line_width.get(), DEFAULT_INNER_LINE_WIDTH_CM),
                inner_line_opacity=self.inner_line_opacity.get(),
                outer_line_enabled=self.outer_line_enabled.get(),
                outer_line_width_cm=self._pf(self.outer_line_width.get(), DEFAULT_OUTER_LINE_WIDTH_CM),
                outer_line_opacity=self.outer_line_opacity.get(),
                target_width_cm=t_w if t_w > 0 else None,
                target_height_cm=t_h if t_h > 0 else None,
                h_marks=self.h_override, v_marks=self.v_override,
            )

        def _update_warnings(self, w_cm, h_cm):
            msgs = []
            m = self._pf(self.margin.get(), 0)
            ms = self._pf(self.marker_size.get(), 0)
            sp = self._pf(self.target_spacing.get(), 0)
            if getattr(self, '_src_px', None) and w_cm > 0 and h_cm > 0:
                eff = min(self._src_px[0] / w_cm, self._src_px[1] / h_cm) * 2.54
                if not getattr(self, '_dpi_found', True):
                    msgs.append("Plik bez DPI – sprawdź wymiary ręcznie.")
                if eff < 72:
                    msgs.append(f"Niska rozdzielczość wydruku (~{eff:.0f} DPI).")
            if ms <= 0 or sp <= 0 or m < 0:
                msgs.append("Rozmiary i rozstaw muszą być dodatnie.")
            if w_cm > 0 and h_cm > 0 and 2 * m >= min(w_cm, h_cm):
                msgs.append("Odległość osi od krawędzi za duża – celowniki się nakładają.")
            self.warn.set("   ".join("⚠ " + x for x in msgs))

        def render_now(self):
            self._render_job = None
            if self.work_img is None:
                return
            try:
                w_cm, h_cm = self._target_dims()
                if not w_cm or not h_cm or w_cm <= 0 or h_cm <= 0:
                    return
                ww, wh = self.work_img.size
                avg = ((ww / w_cm) + (wh / h_cm)) / 2.0 * 2.54
                params = self._core_params()
                params.pop('target_width_cm'); params.pop('target_height_cm')
                r = render_banner(self.work_img.copy(), avg, w_cm, h_cm, verbose=False, **params)
            except Exception as e:
                self.status.set(f"Błąd podglądu: {e}")
                return

            img = r['image']
            if img.mode != 'RGB':
                img = img.convert('RGB')
            self.preview_pil = img
            self._last_h = r['h_marks']
            self._last_v = r['v_marks']
            self.h_count_lbl.set(f"{r['h_marks']} oczek • co {r['h_spacing']:.1f} cm")
            self.v_count_lbl.set(f"{r['v_marks']} oczek • co {r['v_spacing']:.1f} cm")
            self.status.set(f"{r['marker_count']} celowników   |   wydruk {w_cm:.1f} × {h_cm:.1f} cm")
            self._update_warnings(w_cm, h_cm)
            self.save_btn.config(state='normal')

            if self._need_fit and self.canvas.winfo_width() > 10:
                self.fit_view()
                self._need_fit = False
            else:
                self.redraw()

        # ── zoom / pan ──
        def _on_canvas_configure(self, event):
            if self._need_fit and self.preview_pil is not None:
                self.fit_view()
                self._need_fit = False

        def fit_view(self):
            if self.preview_pil is None:
                return
            cw = max(self.canvas.winfo_width(), 10)
            ch = max(self.canvas.winfo_height(), 10)
            pw, ph = self.preview_pil.size
            self.fit_zoom = min(cw / pw, ch / ph)
            self.zoom = self.fit_zoom
            self.offset = [(cw - pw * self.zoom) / 2, (ch - ph * self.zoom) / 2]
            self.redraw()

        def zoom_by(self, factor):
            if self.preview_pil is None:
                return
            cw = self.canvas.winfo_width() / 2
            ch = self.canvas.winfo_height() / 2
            self._zoom_at(cw, ch, factor)

        def _zoom_at(self, sx, sy, factor):
            ix = (sx - self.offset[0]) / self.zoom
            iy = (sy - self.offset[1]) / self.zoom
            self.zoom = max(0.05, min(8.0, self.zoom * factor))
            self.offset[0] = sx - ix * self.zoom
            self.offset[1] = sy - iy * self.zoom
            self.redraw()

        def on_wheel(self, event):
            if self.preview_pil is None:
                return
            self._zoom_at(event.x, event.y, 1.15 if event.delta > 0 else 1 / 1.15)

        def on_press(self, event):
            self._drag = (event.x, event.y, self.offset[0], self.offset[1])

        def on_drag(self, event):
            if not self._drag:
                return
            ox, oy, offx, offy = self._drag
            self.offset = [offx + (event.x - ox), offy + (event.y - oy)]
            self.redraw()

        def on_release(self, event):
            self._drag = None

        def redraw(self):
            if self.preview_pil is None:
                return
            pw, ph = self.preview_pil.size
            zw, zh = max(1, int(pw * self.zoom)), max(1, int(ph * self.zoom))
            disp = self.preview_pil.resize((zw, zh))
            self.tk_img = ImageTk.PhotoImage(disp)
            self.canvas.delete('all')
            self.canvas.create_image(self.offset[0], self.offset[1], anchor='nw', image=self.tk_img)
            self.zoom_lbl.set(f"{int(round(self.zoom * 100))}%")

        # ── korekta liczby oczek ──
        def h_plus(self):
            self.h_override = self._last_h + 1
            self.render_now()

        def h_minus(self):
            self.h_override = max(2, self._last_h - 1)
            self.render_now()

        def v_plus(self):
            self.v_override = self._last_v + 1
            self.render_now()

        def v_minus(self):
            self.v_override = max(2, self._last_v - 1)
            self.render_now()

        # ── zapis ──
        def save_single(self):
            if not self.files:
                return
            path = self.files[self.current_index]
            base = os.path.splitext(os.path.basename(path))[0]
            fmt = self.out_format.get()
            out = filedialog.asksaveasfilename(
                title="Zapisz przetworzony banner",
                initialdir=self.last_out_dir or self.last_dir or '',
                initialfile=f"{base}_processed.{fmt}",
                defaultextension=f".{fmt}",
                filetypes=[("JPEG", "*.jpg *.jpeg"), ("TIFF", "*.tif *.tiff"),
                           ("PNG", "*.png"), ("PDF", "*.pdf"), ("Wszystkie", "*.*")])
            if not out:
                return
            try:
                self.status.set("Zapisywanie…")
                self.root.update_idletasks()
                self._run_full(path, out)
                self.last_out_dir = os.path.dirname(out)
                self.open_folder_btn.config(state='normal')
                self.status.set(f"Zapisano: {out}")
                messagebox.showinfo("Sukces", f"Banner zapisany:\n{out}")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))
                self.status.set("Błąd zapisu.")

        def save_batch(self):
            if len(self.files) < 2:
                return
            out_dir = filedialog.askdirectory(
                title="Wybierz katalog docelowy dla wsadu",
                initialdir=self.last_out_dir or self.last_dir or None)
            if not out_dir:
                return
            core = self._core_params()
            core.pop('h_marks'); core.pop('v_marks')  # wsad liczy oczka automatycznie
            # Wsad ma używać wymiarów każdego pliku z osobna, żeby wykryć plik
            # o innym rozmiarze; inaczej narzucony rozmiar rozciągnąłby go po cichu.
            core.pop('target_width_cm', None); core.pop('target_height_cm', None)

            def on_progress(i, total, name):
                self.status.set(f"Przetwarzanie wsadu… {i}/{total}: {name}")
                self.root.update()

            try:
                outputs = process_batch(
                    self.files, output_dir=out_dir, output_ext=f".{self.out_format.get()}",
                    params=core, pdf_dpi=int(self._pf(self.pdf_dpi.get(), DEFAULT_PDF_DPI)),
                    progress=on_progress)
                self.last_out_dir = out_dir
                self.open_folder_btn.config(state='normal')
                self.status.set(f"Wsad gotowy: {len(outputs)} plików w {out_dir}")
                messagebox.showinfo("Sukces", f"Zapisano {len(outputs)} plików do:\n{out_dir}")
            except ValueError as e:
                messagebox.showerror("Różne wymiary", str(e))
                self.status.set("Wsad przerwany: różne wymiary plików.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        def _run_full(self, in_path, out_path):
            import io
            buf, old = io.StringIO(), sys.stdout
            try:
                sys.stdout = buf
                process_banner(input_path=in_path, output_path=out_path,
                               pdf_render_dpi=int(self._pf(self.pdf_dpi.get(), DEFAULT_PDF_DPI)),
                               **self._core_params())
            finally:
                sys.stdout = old

    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    app = BannerApp(root)
    root.mainloop()


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Banner Processor - StudioDelta.pl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input', nargs='*', help='Plik(i) wejściowy(e). Kilka = tryb wsadowy.')
    parser.add_argument('-o', '--output', help='Plik wyjściowy (1 plik) lub katalog docelowy (wsad)')
    parser.add_argument('--format', default='jpg', choices=['jpg', 'jpeg', 'tif', 'tiff', 'png', 'pdf'],
                        help='Format wyjściowy gdy nie podano -o (domyślnie jpg)')
    parser.add_argument('--pdf-dpi', type=int, default=DEFAULT_PDF_DPI,
                        help='Rozdzielczość rasteryzacji plików PDF (domyślnie 150)')
    parser.add_argument('--marker-size', type=float, default=DEFAULT_MARKER_SIZE_CM)
    parser.add_argument('--margin', type=float, default=DEFAULT_MARGIN_CM)
    parser.add_argument('--spacing', type=float, default=DEFAULT_TARGET_SPACING_CM)
    parser.add_argument('--border', type=float, default=DEFAULT_BORDER_CM)
    parser.add_argument('--no-border', action='store_true', help='Wyłącz białą ramkę na zgrzew')
    parser.add_argument('--inner-width', type=float, default=DEFAULT_INNER_LINE_WIDTH_CM,
                        help='Grubość linii wewnętrznej (cm)')
    parser.add_argument('--inner-opacity', type=int, default=DEFAULT_INNER_LINE_OPACITY,
                        help='Nasycenie linii wewnętrznej (0-100)')
    parser.add_argument('--no-inner', action='store_true', help='Wyłącz linię wewnętrzną')
    parser.add_argument('--outer-width', type=float, default=DEFAULT_OUTER_LINE_WIDTH_CM,
                        help='Grubość linii zewnętrznej (cm)')
    parser.add_argument('--outer-opacity', type=int, default=DEFAULT_OUTER_LINE_OPACITY,
                        help='Nasycenie linii zewnętrznej (0-100)')
    parser.add_argument('--no-outer', action='store_true', help='Wyłącz linię zewnętrzną')
    parser.add_argument('--width', type=float, default=None)
    parser.add_argument('--height', type=float, default=None)

    args = parser.parse_args()

    if not args.input:
        run_gui()
        return

    missing = [p for p in args.input if not os.path.exists(p)]
    if missing:
        for p in missing:
            print(f"Błąd: plik '{p}' nie istnieje!")
        sys.exit(1)

    params = dict(
        marker_size_cm=args.marker_size,
        margin_cm=args.margin,
        target_spacing_cm=args.spacing,
        border_cm=args.border,
        border_enabled=not args.no_border,
        inner_line_enabled=not args.no_inner,
        inner_line_width_cm=args.inner_width,
        inner_line_opacity=args.inner_opacity,
        outer_line_enabled=not args.no_outer,
        outer_line_width_cm=args.outer_width,
        outer_line_opacity=args.outer_opacity,
        target_width_cm=args.width,
        target_height_cm=args.height,
    )

    if len(args.input) == 1:
        process_banner(input_path=args.input[0], output_path=args.output,
                       pdf_render_dpi=args.pdf_dpi, **params)
    else:
        # tryb wsadowy – wszystkie pliki muszą mieć jednakowe wymiary
        try:
            outputs = process_batch(
                args.input, output_dir=args.output,
                output_ext=f".{args.format}", params=params, pdf_dpi=args.pdf_dpi)
        except ValueError as e:
            print(f"\nBŁĄD WSADU: {e}")
            sys.exit(1)
        print(f"\n{'='*60}\n  WSAD GOTOWY: {len(outputs)} plików\n{'='*60}")


if __name__ == '__main__':
    main()