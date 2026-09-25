# Tracki

Jednoduchý nástroj pro stahování MP3 z YouTube. Jeden portable `.exe` pro
Windows 10 a 11 — bez instalace, bez telemetrie, bez reklam.

![stav](https://img.shields.io/badge/verze-1.0.0-blue) ![platforma](https://img.shields.io/badge/Windows-10%20%7C%2011-blue)

---

## Co to umí

- Vložíte odkaz na **video** → vznikne jeden MP3 soubor.
- Vložíte odkaz na **playlist** → stáhne se postupně každá položka jako
  samostatný MP3.
- Název souboru se bere automaticky z názvu videa (očištěný tak, aby ho
  Windows přijal).
- Výchozí kvalita je **nejlepší dostupná**; volitelně se aplikace může na
  kvalitu zeptat před každým stažením.
- Cílová složka je nastavitelná, výchozí je uživatelova složka **Stažené**.
- Po dokončení ukáže název souboru a tlačítko **Otevřít složku**.
- Vede **historii** stažených souborů — lze z ní soubor přehrát nebo otevřít
  jeho složku.
- Tmavý i světlý motiv, čeština i angličtina, přepínatelné v nastavení.

## První spuštění — varování Windows

`Tracki.exe` **není digitálně podepsaný** (podpis vyžaduje placený
certifikát). Při prvním spuštění proto Windows SmartScreen může zobrazit
modré okno **„Windows protected your PC" / „Systém Windows ochránil váš
počítač"**.

Spustíte ho takto: **Více informací** (*More info*) → **Spustit přesto**
(*Run anyway*).

To samé platí pro antiviry — u nepodepsaných aplikací zabalených
PyInstallerem jde o běžný jev (tzv. false positive), ne o skutečnou hrozbu.
Build proto dělá dvě věci, které počet těchto hlášení snižují:

- **opravuje PE checksum** hotového `.exe` (PyInstaller ho nechává nulový,
  tedy neplatný — a to je jedna z věcí, které heuristiky hodnotí),
- **nepoužívá UPX kompresi**, která false positivy naopak výrazně zvyšuje.

Pokud chcete mít jistotu, že máte přesně ten soubor, který vyrobilo CI,
porovnejte `SHA256` z přiloženého `Tracki.exe.sha256`.

## Ovládání

| Klávesa | Akce |
|---|---|
| `Ctrl+V` | vloží odkaz ze schránky (funguje odkudkoli v aplikaci) |
| `↑` / `↓` | pohyb mezi prvky |
| `Enter` | potvrzení zaměřeného prvku |
| `Esc` | návrat na hlavní obrazovku / zavření dialogu |

Myš funguje všude normálně. Po spuštění je pole pro odkaz aktivní, takže jde
hned dát `Ctrl+V` a `Enter`.

Během stahování `Esc` záměrně nic nedělá — zrušení je vědomý krok přes
tlačítko **Zrušit**, aby se dlouhý playlist nezrušil omylem.

## Nastavení

| Volba | Výchozí | Poznámka |
|---|---|---|
| Cílová složka | Stažené | zjišťuje se ze systému, ne z pevné cesty |
| Kvalita MP3 | nejlepší dostupná | nebo 320 / 256 / 192 / 128 kbps |
| Ptát se na kvalitu | vypnuto | při zapnutí se volba objeví na hlavní obrazovce |
| Když soubor už existuje | uložit vedle | nebo přepsat / přeskočit |
| Motiv | podle systému | tmavý / světlý |
| Jazyk | čeština | English |
| Zapisovat ID3 tagy | zapnuto | název a interpret do souboru — viz níž |
| Vložit obal | zapnuto | náhled videa jako obal albumu |
| Čistit názvy | zapnuto | odstraní „(Official Video)" apod. — viz níž |
| Po stažení otevřít složku | vypnuto | |
| Velikost historie | 100 záznamů | 25 – 500 |
| Ptát se u playlistů nad | 20 položek | ochrana proti omylem vloženému velkému playlistu |

Aplikace si pamatuje naposledy otevřenou obrazovku i všechna nastavení.

### Kde se ukládá nastavení

Nastavení a historie jsou v jediném souboru `tracki.json`. Ukládá se
**do profilu uživatele**, ne vedle `.exe`:

```
%APPDATA%\Tracki\tracki.json
```

Vedle `Tracki.exe` tak nezůstává žádný další soubor — můžete ho mít třeba
přímo na ploše a nic se tam nepletе.

Aktuální cestu ukazuje **Nastavení → O aplikaci** i s tlačítkem, které tu
složku otevře.

#### Přenosný režim

Když chcete aplikaci nosit na flashce i s nastavením, vytvořte vedle
`Tracki.exe` prázdný soubor:

```
tracki-portable.txt
```

`tracki.json` se pak bude ukládat k němu a do profilu se nesáhne. Bez toho
souboru se přenosný režim nezapne — právě proto, aby `.exe` na ploše
nezakládalo nic dalšího.

#### Přechod ze starší verze

Verze 1.0.0 ukládala nastavení vedle `.exe`. Pokud tam takový `tracki.json`
máte, aplikace ho při prvním spuštění **sama přesune** do `%APPDATA%\Tracki`
— historie i nastavení zůstanou, soubor z plochy zmizí. Existující nastavení
v profilu se nikdy nepřepíše.

Poškozený soubor aplikaci nezastaví — nepoužitelné hodnoty se zahodí
a nahradí výchozími.

## Soukromí

- Žádná telemetrie, analytika, reklamy ani kontrola aktualizací.
- Jediné síťové připojení vede na **YouTube**, a to jen ve chvíli stahování.
- Nic se nikam neodesílá, žádné účty, žádné přihlašování.

## Sestavení `.exe`

### Na Windows (lokálně)

```bat
build.bat
```

Skript si vytvoří virtuální prostředí, nainstaluje závislosti, spustí testy,
stáhne `ffmpeg.exe`, zabalí vše PyInstallerem a opraví PE checksum.
Výsledek je `dist\Tracki.exe`.

Jednotlivé kroky ručně:

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-build.txt pytest
python build\build.py
```

### Přes GitHub Actions

`.github/workflows/build-windows.yml` sestaví `.exe` na `windows-latest`
runneru a nahraje ho jako artefakt (`Tracki-windows-portable`). Workflow jde
spustit ručně přes **Actions → build-windows → Run workflow**. Při pushnutí
tagu `v*` navíc vytvoří GitHub Release.

Workflow po buildu ověří, že `.exe` má rozumnou velikost a že po spuštění
nespadne.

> **Poznámka:** Windows `.exe` musí vzniknout na Windows — PyInstaller neumí
> cross-kompilaci. `build/build.py` se na jiném systému sám zastaví
> s vysvětlením.

## Vývoj

```bash
pip install -r requirements.txt pytest
python src/tracki_main.py     # spuštění z kódu
python -m pytest -q           # testy
```

Testy běží bez sítě — místo yt-dlp se používá náhrada
(`tests/fake_ytdlp.py`), takže se dá otestovat i chování u playlistů,
zrušení uprostřed stahování nebo nedostupné video.

Nad rámec unit testů je k dispozici integrační kontrola celé aplikace včetně
UI — projde cestu vložení odkazu → stahování → hotovo → historie → přepnutí
obrazovek a jazyka. Potřebuje grafické prostředí, proto není součástí pytestu:

```bash
python tests/ui_smoke.py
```

## Struktura projektu

```
src/tracki/
  app.py               vstupní bod
  paths.py             portable vs. %APPDATA%, složka Stažené, ffmpeg, Průzkumník
  core/
    config.py          nastavení + historie (atomický zápis JSON)
    downloader.py      stahovací vlákno, události pro UI
    errors.py          překlad chyb yt-dlp na srozumitelné kódy
    urls.py            rozpoznání a validace YouTube odkazů
    naming.py          názvy souborů bezpečné pro Windows
    tagging.py         ID3 tagy a čištění názvů (interpret nikdy z názvu kanálu)
    humanize.py        formátování velikostí, rychlosti a času
  ui/
    main_window.py     okno, navigace, klávesy, pumpa událostí
    download_view.py   hlavní obrazovka (klid / průběh / hotovo / chyba)
    history_view.py    historie
    settings_view.py   nastavení
    keynav.py          pohyb šipkami a Enter
    theme.py           barvy a fonty pro oba motivy
    widgets.py         opakované prvky UI
  i18n/                české a anglické texty
build/                 PyInstaller spec, ffmpeg, ikona, oprava checksumu
tests/                 testy (bez sítě)
```

### Proč tato technologie

| Vrstva | Volba | Důvod |
|---|---|---|
| stahování | `yt-dlp` jako knihovna | aktivně udržovaný, dává progress callbacky a strukturované chyby |
| MP3 | přibalený `ffmpeg.exe` | uživatel nic neinstaluje |
| GUI | `customtkinter` | moderní vzhled, nativní light/dark, malá stopa |
| balení | PyInstaller `--onefile` | jeden portable soubor bez admin práv |

Zvažované alternativy: Electron (~150 MB a externí binárky stejně potřebuje),
Tauri (nutný Rust toolchain), C#/WPF (runtime .NET nebo obří AOT build),
PySide6/Qt (+60 MB a licenční komplikace při statickém balení).

## ID3 tagy — odkud se bere interpret

Aplikace **nikdy nezapíše jako interpreta název kanálu**. Standardní
postprocessor `FFmpegMetadata` z yt-dlp to dělá (v jeho zdrojáku doslova
`add('artist', ('artist', 'artists', 'creator', 'creators', 'uploader', 'uploader_id'))`),
takže u běžných uploadů skončí v poli *interpret* náhodný text — název
kanálu, který s písničkou nemá nic společného. Tracki proto tagy píše sám
(`core/tagging.py`) v tomto pořadí:

1. **Hudební metadata od YouTube** (`artist` / `track` / `album` /
   `release_year`) — když existují, jsou spolehlivá a mají přednost.
2. **Rozdělení názvu videa** na `Interpret - Skladba`. Bere se jen první
   oddělovač a jen pomlčka s mezerami okolo, takže `Post-punková písnička`
   se nerozpadne. Číslo na začátku (`01 - Skladba`) se uloží jako číslo
   skladby, ne jako interpret.
3. **Nic.** Když z názvu interpreta poznat nejde, pole zůstane prázdné.
   Prázdné pole je lepší než nesprávné.

Rok nahrání se jako rok vydání nepoužívá. Obal albumu vložený z náhledu
videa zůstává při zápisu tagů zachovaný. Ukládá se jako ID3v2.3, protože
Průzkumník Windows čte tuhle verzi spolehlivěji než 2.4.

Tagování se dá vypnout v **Nastavení → Zapisovat ID3 tagy**; názvu souboru
se to nijak nedotkne.

## Čištění názvů

Zapnuté **Nastavení → Čistit názvy** odstraní z názvu marketingový balast,
a to jak z ID3 tagů, tak z **názvu souboru** — aby všude sedělo totéž.

Co se maže: `(Official Video)`, `[Official Music Video]`, `(Official Audio)`,
`(Lyrics)`, `(Lyric Video)`, `(Visualizer)`, `(Oficiální videoklip)`,
`(Text písně)`, `| Official Video` a rozlišení `[HD]`, `4K`, `1080p`.

Co zůstává, protože to je údaj o konkrétní verzi nahrávky:
`(Live)`, `(Live at Wembley 1985)`, `(Acoustic)`, `(Remastered 2011)`,
`(Remix)`, `(Radio Edit)`, `(Cover)`, `(Demo)`, `(Instrumental)`,
`(feat. …)`.

Pravidla, která mazání drží na uzdě:

- smaže se jen to, co tvoří **celý** obsah závorky nebo **celý** konec názvu
  za oddělovačem — `(Live at Wembley)` se nedotkne, i když obsahuje slovo,
  které jinde noise je,
- kdyby po vyčištění nezbylo nic, vrátí se původní název —
  video pojmenované jen `Official Video` si svůj název nechá,
- holé `4K` nebo `HD` na konci se nesmaže, pokud by tím zmizel celý název
  skladby (`Kapela - 4K` zůstává).

Když se vám heuristika nelíbí, vypněte ji — názvy pak zůstanou přesně tak,
jak je má video na YouTube.

## Chybové hlášky

Chyba se hlásí ve třech úrovních, aby posloužila běžnému uživateli i
diagnostice:

1. **co se stalo** — např. „Tohle není odkaz na YouTube",
2. **proč a co s tím** — „Odkaz vede na vimeo.com. Tracki umí stahovat pouze
   z YouTube.",
3. **technický detail** — rozbalitelný, s kódem chyby a původní hláškou
   z yt-dlp, včetně tlačítka pro zkopírování.

Rozlišují se mimo jiné: odkaz na kanál / vyhledávání / úvodní stránku,
poškozené ID videa, soukromé nebo smazané video, věkové omezení,
geoblokace, živý přenos, naplánovaná premiéra, problém se sítí, omezení
počtu požadavků, plný disk, chybějící práva k zápisu.

## Licence a právní poznámka

Kód projektu je k dispozici pod licencí MIT (viz `LICENSE`).

Přibalené komponenty mají vlastní licence:

- **FFmpeg** — LGPL build; text licence se distribuuje v balíčku
  (`ffmpeg/FFMPEG-LICENSE.txt`),
- **yt-dlp** — Unlicense,
- **customtkinter** — MIT.

Stahování obsahu z YouTube je v rozporu s jeho podmínkami užití. Nástroj
používejte pro obsah, ke kterému máte práva — například vlastní nahrávky
nebo materiál uvolněný pod svobodnou licencí. Za způsob použití odpovídá
uživatel.
