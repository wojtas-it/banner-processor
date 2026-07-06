#!/usr/bin/env python3
"""
Banner Processor - StudioDelta.pl
Automatyzacja przygotowania bannerów wielkoformatowych.

Wymagane: pip install Pillow
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
DEFAULT_LINE_WIDTH_CM = 0.05     # Grubość czarnej obramówki (~0.5mm)
DEFAULT_LINE_OPACITY = 100       # Nasycenie obramówki (0-100%)
DEFAULT_BORDER_ENABLED = True
DEFAULT_OUTLINE_ENABLED = True
DEFAULT_JPEG_QUALITY = 100

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


def calculate_positions(length_cm, edge_offset_cm, target_spacing_cm):
    """
    Zwraca pozycje osi celowników wzdłuż jednego boku (w cm, od krawędzi).
    Punkty skrajne leżą w odległości edge_offset_cm od krawędzi (do osi).
    Środkowe rozłożone są równo tak, aby odstęp między kolejnymi punktami
    przebicia był jak najbliższy docelowemu. Wszystkie odstępy są równe.
    """
    first_pos = edge_offset_cm
    last_pos = length_cm - edge_offset_cm
    span = last_pos - first_pos

    if span <= 0:
        return [length_cm / 2.0]

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


def process_banner(
    input_path,
    output_path=None,
    marker_size_cm=DEFAULT_MARKER_SIZE_CM,
    margin_cm=DEFAULT_MARGIN_CM,
    target_spacing_cm=DEFAULT_TARGET_SPACING_CM,
    border_cm=DEFAULT_BORDER_CM,
    line_width_cm=DEFAULT_LINE_WIDTH_CM,
    line_opacity=DEFAULT_LINE_OPACITY,
    border_enabled=DEFAULT_BORDER_ENABLED,
    outline_enabled=DEFAULT_OUTLINE_ENABLED,
    target_width_cm=None,
    target_height_cm=None,
    jpeg_quality=DEFAULT_JPEG_QUALITY,
    save=True,
):
    # ── Otwieranie i odczyt parametrów ──
    Image.MAX_IMAGE_PIXELS = None  # wielkoformatowe pliki przekraczają domyślny limit Pillow
    img = Image.open(input_path)
    mode = img.mode
    original_dpi = img.info.get('dpi')
    if original_dpi is None:
        print("  UWAGA: plik nie zawiera metadanych DPI — przyjęto 150 DPI. Podaj wymiary ręcznie.")
        original_dpi = (150, 150)
    if isinstance(original_dpi, tuple):
        orig_dpi_x, orig_dpi_y = float(original_dpi[0]), float(original_dpi[1])
    else:
        orig_dpi_x = orig_dpi_y = float(original_dpi)

    icc_profile = img.info.get('icc_profile', None)
    width_px, height_px = img.size

    if target_width_cm and target_height_cm:
        width_cm = target_width_cm
        height_cm = target_height_cm
        dpi_x = width_px / width_cm * 2.54
        dpi_y = height_px / height_cm * 2.54
        avg_dpi = (dpi_x + dpi_y) / 2.0
        size_source = "RĘCZNIE PODANE"
    elif target_width_cm:
        width_cm = target_width_cm
        dpi_x = width_px / width_cm * 2.54
        dpi_y = dpi_x
        avg_dpi = dpi_x
        height_cm = px_to_cm(height_px, avg_dpi)
        size_source = "RĘCZNIE (szer.) + proporcja"
    elif target_height_cm:
        height_cm = target_height_cm
        dpi_y = height_px / height_cm * 2.54
        dpi_x = dpi_y
        avg_dpi = dpi_y
        width_cm = px_to_cm(width_px, avg_dpi)
        size_source = "RĘCZNIE (wys.) + proporcja"
    else:
        dpi_x, dpi_y = orig_dpi_x, orig_dpi_y
        avg_dpi = (dpi_x + dpi_y) / 2.0
        width_cm = px_to_cm(width_px, avg_dpi)
        height_cm = px_to_cm(height_px, avg_dpi)
        size_source = "Z DPI PLIKU"

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

    # ── KROK 1: Celowniki na oryginalnym obrazie ──
    print("\n[1/3] Nakładanie celowników...")

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

    h_positions = calculate_positions(width_cm, edge_offset_cm, target_spacing_cm)
    v_positions = calculate_positions(height_cm, edge_offset_cm, target_spacing_cm)

    h_inner = h_positions[1:-1] if len(h_positions) >= 2 else []
    v_inner = v_positions[1:-1] if len(v_positions) >= 2 else []

    all_markers = []
    for cx, cy in corners:
        all_markers.append((cx, cy))
    for x_cm in h_inner:
        all_markers.append((x_cm, edge_offset_cm))
    for x_cm in h_inner:
        all_markers.append((x_cm, height_cm - edge_offset_cm))
    for y_cm in v_inner:
        all_markers.append((edge_offset_cm, y_cm))
    for y_cm in v_inner:
        all_markers.append((width_cm - edge_offset_cm, y_cm))

    for x_cm, y_cm in all_markers:
        x = cm_to_px(x_cm, avg_dpi)
        y = cm_to_px(y_cm, avg_dpi)
        draw_crosshair(draw, x, y, marker_size_px, mode)

    print(f"  Nałożono {len(all_markers)} celowników ({marker_size_cm*10:.0f}x{marker_size_cm*10:.0f} mm)")
    h_spacing = (h_positions[1] - h_positions[0]) if len(h_positions) >= 2 else 0.0
    v_spacing = (v_positions[1] - v_positions[0]) if len(v_positions) >= 2 else 0.0
    print(f"  Poziomo: {len(h_positions)} oczek na bok, "
          f"rozstaw co {h_spacing:.1f} cm (docelowo {target_spacing_cm:.0f})")
    print(f"  Pionowo: {len(v_positions)} oczek na bok, "
          f"rozstaw co {v_spacing:.1f} cm (docelowo {target_spacing_cm:.0f})")

    # ── KROK 2: Biała ramka ──
    white = get_white_color(mode)

    if border_enabled and border_cm > 0:
        print("\n[2/3] Dodawanie białej ramki na zagięcie...")
        border_px = cm_to_px(border_cm, avg_dpi)
        new_width = width_px + 2 * border_px
        new_height = height_px + 2 * border_px
        new_img = Image.new(mode, (new_width, new_height), white)
        new_img.paste(img, (border_px, border_px))
        print(f"  Ramka: {border_cm} cm = {border_px} px")
    else:
        print("\n[2/3] Biała ramka: WYŁĄCZONA")
        new_img = img
        new_width, new_height = width_px, height_px

    # ── KROK 3: Czarna obramówka ──
    if outline_enabled and line_opacity > 0 and line_width_cm > 0:
        print("\n[3/3] Rysowanie czarnej obramówki...")
        draw2 = ImageDraw.Draw(new_img)
        border_color = get_black_color(mode, line_opacity)
        line_w = max(1, cm_to_px(line_width_cm, avg_dpi))

        # Rysuj 4 wypełnione prostokąty na krawędziach (przylegające do samego brzegu)
        # Góra
        draw2.rectangle([0, 0, new_width - 1, line_w - 1], fill=border_color)
        # Dół
        draw2.rectangle([0, new_height - line_w, new_width - 1, new_height - 1], fill=border_color)
        # Lewo
        draw2.rectangle([0, 0, line_w - 1, new_height - 1], fill=border_color)
        # Prawo
        draw2.rectangle([new_width - line_w, 0, new_width - 1, new_height - 1], fill=border_color)

        print(f"  Grubość: {line_width_cm*10:.1f} mm | Nasycenie: {line_opacity}%")
    else:
        print("\n[3/3] Obramówka: WYŁĄCZONA")

    # ── Zapis lub zwrot ──
    result_info = {
        'image': new_img,
        'mode': mode,
        'dpi_x': dpi_x,
        'dpi_y': dpi_y,
        'icc_profile': icc_profile,
        'jpeg_quality': jpeg_quality,
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

    new_img.save(output_path, **save_kwargs)

    print(f"\n{'='*60}")
    print(f"  GOTOWE!")
    print(f"  Zapisano: {output_path}")
    print(f"  Tryb: {mode} | DPI: {dpi_x:.1f}x{dpi_y:.1f} | ICC: {'TAK' if icc_profile else 'NIE'}")
    print(f"{'='*60}")

    result_info['output_path'] = output_path
    return result_info


# ─── GUI ─────────────────────────────────────────────────────────────────

def run_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        from PIL import ImageTk
    except ImportError:
        print("Brak modułu tkinter. Użyj wiersza poleceń.")
        sys.exit(1)

    class CollapsibleFrame(ttk.Frame):
        def __init__(self, parent, text="", default_open=False, on_toggle=None, **kwargs):
            super().__init__(parent, **kwargs)
            self.is_open = default_open
            self.on_toggle = on_toggle
            self.header = ttk.Frame(self)
            self.header.pack(fill='x')
            self.toggle_btn = ttk.Button(
                self.header, text=f"{'▼' if self.is_open else '▶'} {text}",
                command=self.toggle, style='Toolbutton'
            )
            self.toggle_btn.pack(fill='x')
            self.label_text = text
            self.content = ttk.Frame(self)
            if self.is_open:
                self.content.pack(fill='x', padx=15, pady=(0, 5))

        def toggle(self):
            self.is_open = not self.is_open
            self.toggle_btn.config(text=f"{'▼' if self.is_open else '▶'} {self.label_text}")
            if self.is_open:
                self.content.pack(fill='x', padx=15, pady=(0, 5))
            else:
                self.content.pack_forget()
            if self.on_toggle:
                self.on_toggle()

    class BannerApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Banner Processor - StudioDelta.pl")
            self.root.geometry("650x700")
            self.root.resizable(True, True)
            self.root.minsize(620, 500)

            self.input_path = tk.StringVar()
            self.preview_image = None
            self.processed_result = None

            cfg = load_config()

            self.marker_size = tk.DoubleVar(value=cfg.get('marker_size', DEFAULT_MARKER_SIZE_CM))
            self.margin = tk.DoubleVar(value=cfg.get('margin', DEFAULT_MARGIN_CM))
            self.target_spacing = tk.DoubleVar(value=cfg.get('target_spacing', DEFAULT_TARGET_SPACING_CM))
            self.border_cm = tk.DoubleVar(value=cfg.get('border', DEFAULT_BORDER_CM))
            self.line_width = tk.DoubleVar(value=cfg.get('line_width', DEFAULT_LINE_WIDTH_CM))
            self.line_opacity = tk.IntVar(value=cfg.get('line_opacity', DEFAULT_LINE_OPACITY))
            self.border_enabled = tk.BooleanVar(value=cfg.get('border_enabled', DEFAULT_BORDER_ENABLED))
            self.outline_enabled = tk.BooleanVar(value=cfg.get('outline_enabled', DEFAULT_OUTLINE_ENABLED))
            self.target_width = tk.StringVar(value="")
            self.target_height = tk.StringVar(value="")

            self.build_ui()

        def get_current_settings(self):
            return {
                'marker_size': self.marker_size.get(),
                'margin': self.margin.get(),
                'target_spacing': self.target_spacing.get(),
                'border': self.border_cm.get(),
                'line_width': self.line_width.get(),
                'line_opacity': self.line_opacity.get(),
                'border_enabled': self.border_enabled.get(),
                'outline_enabled': self.outline_enabled.get(),
            }

        def save_settings(self):
            try:
                path = save_config(self.get_current_settings())
                messagebox.showinfo("Zapisano", f"Ustawienia zapisane.\n{path}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się zapisać:\n{e}")

        def update_scroll_region(self):
            self.inner_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def build_ui(self):
            container = ttk.Frame(self.root)
            container.pack(fill='both', expand=True)

            self.canvas = tk.Canvas(container, highlightthickness=0)
            scrollbar = ttk.Scrollbar(container, orient='vertical', command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            self.canvas.pack(side='left', fill='both', expand=True)

            self.inner_frame = ttk.Frame(self.canvas)
            self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor='nw')

            def on_canvas_configure(event):
                self.canvas.itemconfig(self.canvas_window, width=event.width)
            self.canvas.bind('<Configure>', on_canvas_configure)
            self.inner_frame.bind('<Configure>', lambda e: self.update_scroll_region())

            def on_mousewheel(event):
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            def on_mousewheel_linux(event):
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
            self.canvas.bind_all("<MouseWheel>", on_mousewheel)
            self.canvas.bind_all("<Button-4>", on_mousewheel_linux)
            self.canvas.bind_all("<Button-5>", on_mousewheel_linux)

            pad = {'padx': 10, 'pady': 3}
            main = self.inner_frame

            # ── Tytuł ──
            ttk.Label(main, text="Banner Processor", font=('Segoe UI', 16, 'bold')).pack(pady=(15, 2))
            ttk.Label(main, text="StudioDelta.pl", font=('Segoe UI', 10)).pack(pady=(0, 10))

            # ── Plik ──
            frame_file = ttk.LabelFrame(main, text="Plik", padding=10)
            frame_file.pack(fill='x', **pad)

            ttk.Label(frame_file, text="Plik wejściowy:").pack(anchor='w')
            f1 = ttk.Frame(frame_file)
            f1.pack(fill='x', pady=2)
            ttk.Entry(f1, textvariable=self.input_path, state='readonly').pack(side='left', fill='x', expand=True)
            ttk.Button(f1, text="Wybierz...", command=self.browse_input).pack(side='right', padx=(5,0))

            self.info_label = ttk.Label(frame_file, text="", font=('Consolas', 9))
            self.info_label.pack(anchor='w', pady=(5,0))

            # ── Wymiary ──
            frame_size = ttk.LabelFrame(main, text="Docelowe wymiary wydruku (obrazka bez ramki)", padding=10)
            frame_size.pack(fill='x', **pad)

            ttk.Label(frame_size, text="Puste = oblicz z DPI pliku.",
                      font=('Segoe UI', 8), foreground='gray').pack(anchor='w')

            f_sz = ttk.Frame(frame_size)
            f_sz.pack(fill='x', pady=3)
            ttk.Label(f_sz, text="Szerokość (cm):", width=15).pack(side='left')
            ttk.Entry(f_sz, textvariable=self.target_width, width=10).pack(side='left')
            ttk.Label(f_sz, text="   Wysokość (cm):", width=17).pack(side='left')
            ttk.Entry(f_sz, textvariable=self.target_height, width=10).pack(side='left')

            # ── Celowniki (zwijane) ──
            self.col_markers = CollapsibleFrame(main, text="Celowniki (znaczniki pozycji)",
                                                 on_toggle=self.update_scroll_region)
            self.col_markers.pack(fill='x', **pad)

            params_markers = [
                ("Rozmiar celownika (cm):", self.marker_size),
                ("Odległość osi od krawędzi (cm):", self.margin),
                ("Docelowy rozstaw (cm):", self.target_spacing),
            ]
            for label_text, var in params_markers:
                f = ttk.Frame(self.col_markers.content)
                f.pack(fill='x', pady=1)
                ttk.Label(f, text=label_text, width=30).pack(side='left')
                ttk.Entry(f, textvariable=var, width=10).pack(side='left')

            ttk.Button(self.col_markers.content, text="Zapisz ustawienia",
                       command=self.save_settings).pack(anchor='e', pady=(5, 0))

            # ── Ramka i obramówka (zwijane) ──
            self.col_border = CollapsibleFrame(main, text="Ramka i obramówka",
                                                on_toggle=self.update_scroll_region)
            self.col_border.pack(fill='x', **pad)

            # Checkbox biała ramka
            ttk.Checkbutton(self.col_border.content, text="Dodaj białą ramkę (na zagięcie)",
                            variable=self.border_enabled).pack(anchor='w', pady=(0, 3))

            params_border_width = [
                ("Szerokość ramki (cm):", self.border_cm),
            ]
            for label_text, var in params_border_width:
                f = ttk.Frame(self.col_border.content)
                f.pack(fill='x', pady=1)
                ttk.Label(f, text=label_text, width=30).pack(side='left')
                ttk.Entry(f, textvariable=var, width=10).pack(side='left')

            # Separator
            ttk.Separator(self.col_border.content, orient='horizontal').pack(fill='x', pady=5)

            # Checkbox obramówka
            ttk.Checkbutton(self.col_border.content, text="Dodaj czarną obramówkę",
                            variable=self.outline_enabled).pack(anchor='w', pady=(0, 3))

            params_outline = [
                ("Grubość obramówki (cm):", self.line_width),
            ]
            for label_text, var in params_outline:
                f = ttk.Frame(self.col_border.content)
                f.pack(fill='x', pady=1)
                ttk.Label(f, text=label_text, width=30).pack(side='left')
                ttk.Entry(f, textvariable=var, width=10).pack(side='left')

            # Nasycenie obramówki
            f_op = ttk.Frame(self.col_border.content)
            f_op.pack(fill='x', pady=3)
            ttk.Label(f_op, text="Nasycenie obramówki (%):", width=30).pack(side='left')
            ttk.Scale(f_op, from_=0, to=100, variable=self.line_opacity,
                      orient='horizontal').pack(side='left', fill='x', expand=True)
            ttk.Label(f_op, textvariable=self.line_opacity, width=4).pack(side='left')

            ttk.Button(self.col_border.content, text="Zapisz ustawienia",
                       command=self.save_settings).pack(anchor='e', pady=(5, 0))

            # ── Przyciski ──
            btn_frame = ttk.Frame(main)
            btn_frame.pack(pady=10)

            self.preview_btn = ttk.Button(btn_frame, text="PODGLĄD", command=self.do_preview)
            self.preview_btn.pack(side='left', ipadx=15, ipady=8, padx=5)

            self.save_btn = ttk.Button(btn_frame, text="ZAPISZ PLIK", command=self.do_save, state='disabled')
            self.save_btn.pack(side='left', ipadx=15, ipady=8, padx=5)

            # ── Podgląd ──
            self.preview_frame = ttk.LabelFrame(main, text="Podgląd", padding=5)
            self.preview_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            self.preview_label = ttk.Label(self.preview_frame, text="Wybierz plik i kliknij PODGLĄD",
                                            anchor='center', font=('Segoe UI', 9, 'italic'))
            self.preview_label.pack(fill='both', expand=True)

            self.status_label = ttk.Label(main, text="", font=('Consolas', 8), foreground='gray')
            self.status_label.pack(fill='x', padx=10, pady=(0, 10))

        def browse_input(self):
            path = filedialog.askopenfilename(
                title="Wybierz plik bannera",
                filetypes=[
                    ("Pliki graficzne", "*.tif *.tiff *.psd *.png *.jpg *.jpeg *.bmp"),
                    ("TIFF", "*.tif *.tiff"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Wszystkie", "*.*"),
                ]
            )
            if path:
                self.input_path.set(path)
                self.show_file_info(path)
                self.save_btn.config(state='disabled')
                self.processed_result = None

        def show_file_info(self, path):
            try:
                img = Image.open(path)
                dpi = img.info.get('dpi', (150, 150))
                if isinstance(dpi, tuple):
                    dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
                else:
                    dpi_x = dpi_y = float(dpi)
                avg_dpi = (dpi_x + dpi_y) / 2.0
                w_cm = px_to_cm(img.size[0], avg_dpi)
                h_cm = px_to_cm(img.size[1], avg_dpi)
                icc = "TAK" if img.info.get('icc_profile') else "NIE"
                self.info_label.config(
                    text=f"{img.mode} | {dpi_x:.0f}x{dpi_y:.0f} DPI | "
                         f"{img.size[0]}x{img.size[1]} px | "
                         f"{w_cm:.1f}x{h_cm:.1f} cm | ICC: {icc}"
                )
            except Exception as e:
                self.info_label.config(text=f"Błąd: {e}")

        def get_target_dims(self):
            tw = self.target_width.get().strip().replace(',', '.')
            th = self.target_height.get().strip().replace(',', '.')
            try:
                return (float(tw) if tw else None, float(th) if th else None)
            except ValueError:
                raise ValueError(f"Nieprawidłowe wymiary: '{tw}' / '{th}'. Użyj kropki jako separatora dziesiętnego.")

        def do_preview(self):
            if not self.input_path.get():
                messagebox.showwarning("Uwaga", "Wybierz plik wejściowy!")
                return

            self.preview_btn.config(state='disabled')
            self.preview_label.config(text="Przetwarzanie...", image='')
            self.root.update()

            import io
            old_stdout = sys.stdout
            buffer = io.StringIO()
            try:
                sys.stdout = buffer

                t_w, t_h = self.get_target_dims()

                result = process_banner(
                    input_path=self.input_path.get(),
                    output_path=None,
                    marker_size_cm=self.marker_size.get(),
                    margin_cm=self.margin.get(),
                    target_spacing_cm=self.target_spacing.get(),
                    border_cm=self.border_cm.get(),
                    line_width_cm=self.line_width.get(),
                    line_opacity=self.line_opacity.get(),
                    border_enabled=self.border_enabled.get(),
                    outline_enabled=self.outline_enabled.get(),
                    target_width_cm=t_w,
                    target_height_cm=t_h,
                    save=False,
                )

                log_text = buffer.getvalue().strip()

                self.processed_result = result
                self.save_btn.config(state='normal')

                img = result['image']
                preview = img.copy()
                if preview.mode == 'CMYK':
                    preview = preview.convert('RGB')
                preview.thumbnail((600, 400))
                self.preview_image = ImageTk.PhotoImage(preview)
                self.preview_label.config(image=self.preview_image, text='')

                lines = log_text.split('\n')
                status = [l for l in lines if 'Nałożono' in l or 'Poziomo' in l or 'Pionowo' in l]
                self.status_label.config(text=' | '.join(s.strip() for s in status[:3]) if status else "Gotowe")

            except Exception as e:
                messagebox.showerror("Błąd", str(e))
            finally:
                sys.stdout = old_stdout
                self.preview_btn.config(state='normal')

        def do_save(self):
            if not self.processed_result:
                messagebox.showwarning("Uwaga", "Najpierw kliknij PODGLĄD!")
                return

            base, _ = os.path.splitext(self.input_path.get())

            output = filedialog.asksaveasfilename(
                title="Zapisz przetworzony banner",
                initialfile=os.path.basename(base) + "_processed.jpg",
                defaultextension=".jpg",
                filetypes=[
                    ("JPEG", "*.jpg *.jpeg"),
                    ("TIFF", "*.tif *.tiff"),
                    ("PNG", "*.png"),
                    ("Wszystkie", "*.*"),
                ]
            )
            if not output:
                return

            try:
                r = self.processed_result
                save_kwargs = {'dpi': (r['dpi_x'], r['dpi_y'])}
                if r['icc_profile']:
                    save_kwargs['icc_profile'] = r['icc_profile']

                ext_lower = os.path.splitext(output)[1].lower()
                if ext_lower in ('.jpg', '.jpeg'):
                    save_kwargs['quality'] = r['jpeg_quality']
                    save_kwargs['subsampling'] = 0
                elif ext_lower in ('.tif', '.tiff'):
                    save_kwargs['compression'] = 'tiff_lzw'

                r['image'].save(output, **save_kwargs)
                self.status_label.config(text=f"Zapisano: {output}")
                messagebox.showinfo("Sukces", f"Banner zapisany!\n{output}")

            except Exception as e:
                messagebox.showerror("Błąd", str(e))

    root = tk.Tk()
    app = BannerApp(root)
    root.mainloop()


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Banner Processor - StudioDelta.pl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input', nargs='?', help='Plik wejściowy')
    parser.add_argument('-o', '--output', help='Plik wyjściowy (domyślnie: _processed.jpg)')
    parser.add_argument('--marker-size', type=float, default=DEFAULT_MARKER_SIZE_CM)
    parser.add_argument('--margin', type=float, default=DEFAULT_MARGIN_CM)
    parser.add_argument('--spacing', type=float, default=DEFAULT_TARGET_SPACING_CM)
    parser.add_argument('--border', type=float, default=DEFAULT_BORDER_CM)
    parser.add_argument('--line-width', type=float, default=DEFAULT_LINE_WIDTH_CM)
    parser.add_argument('--line-opacity', type=int, default=DEFAULT_LINE_OPACITY)
    parser.add_argument('--no-border', action='store_true', help='Wyłącz białą ramkę')
    parser.add_argument('--no-outline', action='store_true', help='Wyłącz czarną obramówkę')
    parser.add_argument('--width', type=float, default=None)
    parser.add_argument('--height', type=float, default=None)

    args = parser.parse_args()

    if args.input is None:
        run_gui()
    else:
        if not os.path.exists(args.input):
            print(f"Błąd: plik '{args.input}' nie istnieje!")
            sys.exit(1)

        process_banner(
            input_path=args.input,
            output_path=args.output,
            marker_size_cm=args.marker_size,
            margin_cm=args.margin,
            target_spacing_cm=args.spacing,
            border_cm=args.border,
            line_width_cm=args.line_width,
            line_opacity=args.line_opacity,
            border_enabled=not args.no_border,
            outline_enabled=not args.no_outline,
            target_width_cm=args.width,
            target_height_cm=args.height,
        )


if __name__ == '__main__':
    main()