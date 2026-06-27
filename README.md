# Banner Processor

Narzędzie do przygotowania plików graficznych pod druk wielkoformatowy. Napisałem je podczas praktyk w Studio Delta (drukarnia wielkoformatowa) i jest tam teraz używane produkcyjnie.

Przed każdym wydrukiem trzeba było ręcznie dodawać celowniki rejestracyjne i ramkę — to zajmowało kilka minut i łatwo było coś przekrzywić. Ten skrypt robi to automatycznie i zapisuje gotowy plik.

## Co robi

- Nakłada celowniki rejestracyjne (registration marks / paserki) — automatycznie dobiera ich liczbę i rozstaw do rozmiaru bannera (domyślnie co ~50 cm)
- Dodaje białą ramkę na zagięcie/zawieszenie (domyślnie 3,6 cm)
- Rysuje czarną obramówkę na krawędzi (domyślnie ~0,5 mm)
- Zachowuje profil ICC i DPI — plik CMYK wychodzi jako CMYK z profilem

![Główne okno aplikacji](screens/1_main.jpg)

## Uruchomienie

Wymagania: Python 3.8+, Pillow

```bash
pip install Pillow
python main.py
```

Bez argumentów odpala GUI. Z argumentem — CLI:

```bash
python main.py baner.tif
python main.py baner.tif -o wynik.jpg --width 300 --height 150
python main.py baner.tif --no-border --spacing 40
python main.py --help
```

## GUI

Po wybraniu pliku można kliknąć PODGLĄD żeby zobaczyć efekt przed zapisaniem. Ustawienia (rozstaw celowników, szerokość ramki itd.) zapisują się do `banner_processor_config.json` obok exe/skryptu.

![Podgląd z nałożonymi celownikami](screens/2_podglad.jpg)

## Obsługiwane formaty

Wejście: TIFF, JPEG, PNG, PSD (wymaga Pillow z obsługą PSD)
Wyjście: JPEG (jakość 100%) lub TIFF (kompresja LZW)
Przestrzenie kolorów: RGB i CMYK

## Parametry

Wszystkie mają wartości domyślne dopasowane do workflow drukarni:

| Parametr | Domyślnie | Co robi |
|----------|-----------|---------|
| `marker_size` | 1.0 cm | rozmiar celownika (10x10 mm) |
| `margin` | 2.0 cm | odległość celownika od krawędzi |
| `target_spacing` | 50.0 cm | docelowy rozstaw celowników |
| `min_spacing` | 45.0 cm | dolna granica rozstawu |
| `max_spacing` | 55.0 cm | górna granica rozstawu |
| `border` | 3.6 cm | biała ramka na zagięcie |
| `line_width` | 0.05 cm | grubość czarnej obramówki |
| `line_opacity` | 100% | nasycenie obramówki |

## Jak działa rozmieszczanie celowników

Zawsze są 4 w narożnikach. Dla dłuższych boków program dobiera liczbę pośrednich celowników tak, żeby rozstaw był jak najbliższy 50 cm i mieścił się w [45–55 cm]. Jeśli odstęp między skrajnymi jest mniejszy niż ~82 cm, pośrednie nie są dodawane.

## Budowanie exe (Windows)

```bash
pip install pyinstaller
pyinstaller BannerProcessor_v2.spec
```

Gotowy plik ląduje w `dist/`.

## Znane ograniczenia

- Podgląd CMYK w GUI jest konwertowany do RGB bez profilu ICC, więc kolory w podglądzie mogą się różnić od wydruku
- Jeśli plik nie ma metadanych DPI, program zakłada 150 DPI i wyświetla ostrzeżenie — w takim przypadku trzeba podać wymiary ręcznie
