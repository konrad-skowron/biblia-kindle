# biblia-kindle

Prosta, statyczna strona z czytaniem liturgicznym na dziś — zaprojektowana
przede wszystkim do przeglądania na czytniku **Kindle**.

- Po godzinie **18:00** (czas `Europe/Warsaw`) wyświetlane jest już czytanie
  na **następny dzień**.
- Strona jest w pełni statyczna (HTML + minimalny CSS, **bez JavaScriptu**),
  więc działa w eksperymentalnej przeglądarce każdego Kindle.
- Zero zewnętrznych zasobów (fontów, ikon) — szybkie ładowanie na słabym łączu.
- Treść jest pobierana z [mateusz.pl/czytania](https://www.mateusz.pl/czytania/).

## Jak to działa

1. Skrypt [`generate.py`](./generate.py) ustala datę docelową (czas warszawski,
   przesunięcie o dobę po 18:00), pobiera odpowiednią stronę z mateusz.pl,
   wyciąga datę, dzień liturgiczny, kolejne czytania oraz Ewangelię (z autorem
   i sygnaturą), a następnie generuje `index.html` w stylu Kindle-friendly.
2. Workflow GitHub Actions [`.github/workflows/update.yml`](./.github/workflows/update.yml)
   uruchamia skrypt co 30 minut, commituje zmiany do gałęzi `main`.
3. GitHub Pages serwuje `index.html` z `main` (root).

## Uruchomienie i konfiguracja

### Wymagania

- Python 3.11+ (używa `zoneinfo` i wyłącznie biblioteki standardowej).
- Konto GitHub z włączonymi GitHub Pages dla repozytorium.

### Lokalne wygenerowanie strony

```bash
python generate.py             # czytanie na dziś (po 18:00 — na jutro)
python generate.py 2026-05-21  # czytanie na konkretny dzień (testy)
```

Wygenerowany plik `index.html` można otworzyć w dowolnej przeglądarce.

### Włączenie GitHub Pages

1. W ustawieniach repozytorium → **Pages** → **Source: Deploy from a branch**.
2. Wybierz `main` i `/ (root)`.
3. Strona będzie dostępna pod `https://<user>.github.io/<repo>/`.
4. W ustawieniach repozytorium → **Actions** → **General** upewnij się, że
   **Workflow permissions** są ustawione na **Read and write permissions**
   (potrzebne, by Action mogła commitować zaktualizowany `index.html`).

## Źródło treści

Czytania pobierane są z [mateusz.pl/czytania](https://www.mateusz.pl/czytania/).
Stopka strony wskazuje konkretny adres źródłowy danego dnia.
