"""Integracni kontrola cele aplikace vcetne UI.

Neni to pytest test - potrebuje graficke prostredi. Spousti se rucne:

    python tests/ui_smoke.py            # Windows / Linux s displejem
    xvfb-run -a --server-args="-screen 0 700x820x24" python tests/ui_smoke.py

Parametry obrazovky u xvfb-run nejsou kosmetika: vychozi Xvfb ma 8bitovou
hloubku a mala okna, kontrola zamereni pak hlasi chybu, i kdyz je aplikace
v poradku.

Projde skutecnou cestou uzivatele: vlozeni odkazu -> stahovani -> hotovo ->
zapis do historie -> prepnuti obrazovek a jazyka. Misto yt-dlp bezi nahrada
z fake_ytdlp, takze se nic nestahuje ze site.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

from fake_ytdlp import FakeYoutubeDL, Script, info, playlist  # noqa: E402

from tracki.core import downloader as dl  # noqa: E402
from tracki.core.config import Store  # noqa: E402
from tracki.ui import theme  # noqa: E402

VIDEO_URL = "https://www.youtube.com/watch?v=aBcD1234_-x"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLsmoke123"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "ok  " if condition else "CHYBA"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def install_fake(dest: pathlib.Path) -> Script:
    script = Script()
    FakeYoutubeDL.script = script

    class FakeModule:
        YoutubeDL = FakeYoutubeDL

    dl.yt_dlp = FakeModule
    dl.paths.ffmpeg_path = lambda: "/usr/bin/ffmpeg"

    script.infos[VIDEO_URL] = info(
        "aBcD1234_-x",
        "Ukázková kapela - Ukázková skladba (Oficiální videoklip) [HD]",
        uploader="Naprosto nesouvisejici kanal",
        channel="Naprosto nesouvisejici kanal",
    )
    entries = []
    for index in range(3):
        url = f"https://www.youtube.com/watch?v=pl{index:09d}"
        entries.append({"id": f"pl{index:09d}", "title": f"Playlist {index + 1}",
                        "url": url})
        script.infos[url] = info(f"pl{index:09d}", f"Playlist {index + 1}")
    script.infos[PLAYLIST_URL] = playlist("Smoke playlist", entries)
    return script


def main() -> int:
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="tracki-smoke-"))
    dest = workdir / "Downloads"
    dest.mkdir()
    script = install_fake(dest)

    store = Store(workdir / "tracki.json").load()
    store.settings.output_dir = str(dest)
    store.settings.language = "cs"
    theme.apply_mode("dark")

    from tracki.ui.main_window import TrackiApp

    app = TrackiApp(store)
    steps = iter(build_steps(app, store, dest, script))

    def advance() -> None:
        try:
            next(steps)()
        except StopIteration:
            app.destroy()
            return
        app.after(500, advance)

    app.after(600, advance)
    app.mainloop()

    print()
    if failures:
        print(f"NEPROSLO: {len(failures)} kontrol -> {failures}")
        return 1
    print("vsechny kontrolni body prosly")
    return 0


def build_steps(app, store, dest, script):
    """Kroky se posouvaji timerem, aby mezi nimi stihla probehnout pumpa."""

    def paste_video():
        app.download_view.clear_url()
        app.download_view.url_entry.insert(0, VIDEO_URL)
        app.start_download(VIDEO_URL, "best")
        check("stahovani jednoho videa se rozjelo", app.is_working)

    def wait_video():
        for _ in range(40):
            if not app.is_working:
                break
            app.update()
            app.after(50)
            import time
            time.sleep(0.05)
        app.update()

    def verify_video():
        target = dest / "Ukázková kapela - Ukázková skladba.mp3"
        check("MP3 vznikl na disku (s vycistenym nazvem)", target.is_file(),
              str(target))
        check("v nazvu souboru nezustal balast",
              not any(w in target.name.lower()
                      for w in ("videoklip", "official", "hd]")),
              target.name)
        check("UI je ve stavu hotovo", app.download_view.done.winfo_ismapped())
        check("v historii je zaznam", len(store.history) == 1,
              f"{len(store.history)}")
        if store.history:
            check("historie ukazuje na spravny soubor",
                  store.history[0].path == str(target))
            check("historie zna velikost", store.history[0].size > 0)
            # Pole se po stazeni maze, odkaz se proto musi ulozit driv.
            check("historie si zapamatovala odkaz",
                  store.history[0].url == VIDEO_URL, store.history[0].url)
        check("config se ulozil", (store.path).is_file())
        check("pole s odkazem je po stazeni prazdne",
              app.download_view.url_entry.get() == "",
              repr(app.download_view.url_entry.get()))
        try:
            from mutagen.id3 import ID3

            frames = ID3(str(target))
            check("tag interpret je z nazvu videa, ne z kanalu",
                  frames["TPE1"].text == ["Ukázková kapela"],
                  str(frames["TPE1"].text))
            check("tag nazev je jen nazev skladby",
                  frames["TIT2"].text == ["Ukázková skladba"],
                  str(frames["TIT2"].text))
        except Exception as exc:  # noqa: BLE001
            check("tagy se daji precist", False, repr(exc))

        check("pole s odkazem ma zamereni",
              str(app.focus_get()).startswith(str(app.download_view.url_entry)),
              str(app.focus_get()))

    def download_playlist():
        app.download_view.reset()
        app.start_download(PLAYLIST_URL, "best")

    def wait_playlist():
        import time
        for _ in range(80):
            if not app.is_working:
                break
            app.update()
            time.sleep(0.05)
        app.update()

    def verify_playlist():
        names = sorted(p.name for p in dest.glob("Playlist *.mp3"))
        check("playlist stahl vsechny 3 polozky",
              names == ["Playlist 1.mp3", "Playlist 2.mp3", "Playlist 3.mp3"],
              str(names))
        check("historie ma 4 zaznamy", len(store.history) == 4,
              f"{len(store.history)}")

    def error_path():
        app.download_view.reset()
        app.start_download("https://vimeo.com/12345", "best")
        app.update()
        check("neplatny odkaz ukaze chybu bez stahovani",
              app.download_view.error.winfo_ismapped())
        check("chyba zna hostname",
              "vimeo.com" in app.download_view.error_hint.cget("text"),
              app.download_view.error_hint.cget("text"))

    def screens():
        app.show_screen("history")
        app.update()
        check("historie se zobrazila", app.current_screen == "history")
        check("historie vykreslila radky", len(app.history_view._rows) == 4,
              f"{len(app.history_view._rows)}")
        app.show_screen("settings")
        app.update()
        check("nastaveni se zobrazilo", app.current_screen == "settings")
        check("posledni obrazovka se zapamatovala",
              store.settings.last_screen == "settings")

    def language():
        app.set_language("en")
        app.update()
        check("prepnuti do anglictiny",
              app.nav_buttons["settings"].cget("text") == "Settings",
              app.nav_buttons["settings"].cget("text"))
        app.set_language("cs")
        app.update()
        check("prepnuti zpet do cestiny",
              app.nav_buttons["settings"].cget("text") == "Nastavení")

    def keyboard():
        app.show_screen("download")
        app.update()
        app.ring.focus_first()
        app._on_down()
        app._on_down()
        app._on_up()
        check("sipky posunuly zamereni bez vyjimky", True)
        app._on_escape()
        check("Esc neshodil aplikaci", True)

    def theme_switch():
        theme.apply_mode("light")
        app.update()
        theme.apply_mode("dark")
        app.update()
        check("prepnuti motivu za behu", True)

    def cancel_keeps_url():
        app.download_view.reset()
        app.download_view.url_entry.insert(0, PLAYLIST_URL)
        script.before_download = lambda url: app.job and app.job.cancel()
        app.start_download(PLAYLIST_URL, "best")
        import time
        for _ in range(60):
            if not app.is_working:
                break
            app.update()
            time.sleep(0.05)
        app.update()
        script.before_download = None
        check("po zruseni odkaz v poli zustane",
              app.download_view.url_entry.get() == PLAYLIST_URL,
              repr(app.download_view.url_entry.get()))

    return [paste_video, wait_video, verify_video, download_playlist,
            wait_playlist, verify_playlist, cancel_keeps_url, error_path,
            screens, language, keyboard, theme_switch]


if __name__ == "__main__":
    sys.exit(main())
