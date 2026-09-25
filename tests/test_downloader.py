"""Testy stahovaciho vlakna bez site - misto yt-dlp bezi nahrada z fake_ytdlp."""
from __future__ import annotations

import queue

import pytest
from fake_ytdlp import FakeYoutubeDL, Script, info, playlist

from tracki.core import downloader as dl
from tracki.core import urls

VIDEO_URL = "https://www.youtube.com/watch?v=aBcD1234_-x"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL123"


@pytest.fixture
def script(monkeypatch, tmp_path):
    """Nasadi falesne yt-dlp a existujici ffmpeg."""
    script = Script()
    FakeYoutubeDL.script = script

    class FakeModule:
        YoutubeDL = FakeYoutubeDL

    monkeypatch.setattr(dl, "yt_dlp", FakeModule)
    monkeypatch.setattr(dl.paths, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    return script


def run(request: dl.DownloadRequest) -> tuple[list, dl.DownloadJob]:
    events: list = []
    job = dl.run_job(request, events.append)
    job.join(timeout=10)
    return events, job


def make_request(parsed_url: str, dest, **kwargs) -> dl.DownloadRequest:
    return dl.DownloadRequest(parsed=urls.parse(parsed_url), dest_dir=dest, **kwargs)


def of_type(events: list, kind) -> list:
    return [e for e in events if isinstance(e, kind)]


# --- jedno video ------------------------------------------------------------
def test_single_video_produces_mp3_named_after_title(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Moje písnička")

    events, _ = run(make_request(VIDEO_URL, dest))

    finished = of_type(events, dl.ItemFinished)
    assert len(finished) == 1
    assert finished[0].path == dest / "Moje písnička.mp3"
    assert finished[0].path.is_file()
    assert finished[0].size > 0

    done = of_type(events, dl.JobFinished)[-1]
    assert len(done.downloaded) == 1
    assert not done.failed and not done.cancelled


def test_event_order_for_single_video(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    events, _ = run(make_request(VIDEO_URL, dest))

    kinds = [type(e).__name__ for e in events]
    assert kinds[0] == "Resolving"
    assert "ItemStarted" in kinds
    assert "Progress" in kinds
    assert "Converting" in kinds
    assert kinds.index("ItemFinished") < kinds.index("JobFinished")
    assert kinds[-1] == "JobFinished"


def test_progress_reports_percent_and_speed(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    events, _ = run(make_request(VIDEO_URL, dest))

    progress = of_type(events, dl.Progress)
    assert progress
    assert progress[-1].percent == pytest.approx(100.0)
    assert progress[-1].total_bytes == 1_000_000
    assert progress[-1].speed == 250_000.0


def test_title_with_forbidden_characters_is_sanitized(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", 'A/B: "C" <D> 100%')
    events, _ = run(make_request(VIDEO_URL, dest))

    path = of_type(events, dl.ItemFinished)[0].path
    assert path.is_file()
    for char in '/\\:*?"<>|':
        assert char not in path.name


def test_percent_sign_in_title_survives_outtmpl(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "100% Live Session")
    events, _ = run(make_request(VIDEO_URL, dest))

    path = of_type(events, dl.ItemFinished)[0].path
    assert path.name == "100% Live Session.mp3"
    assert path.is_file()


# --- playlist ---------------------------------------------------------------
def build_playlist(script, count: int = 3) -> list[str]:
    item_urls = []
    entries = []
    for index in range(count):
        url = f"https://www.youtube.com/watch?v=vid{index:08d}"
        item_urls.append(url)
        entries.append({"id": f"vid{index:08d}", "title": f"Skladba {index + 1}",
                        "url": url})
        script.infos[url] = info(f"vid{index:08d}", f"Skladba {index + 1}")
    script.infos[PLAYLIST_URL] = playlist("Můj playlist", entries)
    return item_urls


def test_playlist_downloads_every_item(script, dest):
    build_playlist(script, 3)
    events, _ = run(make_request(PLAYLIST_URL, dest))

    resolved = of_type(events, dl.PlaylistResolved)[0]
    assert resolved.total == 3
    assert resolved.title == "Můj playlist"

    finished = of_type(events, dl.ItemFinished)
    assert [e.path.name for e in finished] == [
        "Skladba 1.mp3", "Skladba 2.mp3", "Skladba 3.mp3",
    ]
    assert all(e.path.is_file() for e in finished)
    assert [e.index for e in finished] == [1, 2, 3]
    assert all(e.total == 3 for e in finished)


def test_playlist_continues_after_one_item_fails(script, dest):
    item_urls = build_playlist(script, 3)
    script.errors[item_urls[1]] = "ERROR: Private video. Sign in if you've been granted access"

    events, _ = run(make_request(PLAYLIST_URL, dest))

    failed = of_type(events, dl.ItemFailed)
    assert len(failed) == 1
    assert failed[0].error.code == "VIDEO_PRIVATE"
    assert failed[0].index == 2

    done = of_type(events, dl.JobFinished)[-1]
    assert len(done.downloaded) == 2
    assert len(done.failed) == 1


def test_empty_playlist_fails_with_clear_code(script, dest):
    script.infos[PLAYLIST_URL] = playlist("Prázdný", [])
    events, _ = run(make_request(PLAYLIST_URL, dest))

    failure = of_type(events, dl.JobFailed)[-1]
    assert failure.error.code == "PLAYLIST_EMPTY"


def test_cancel_stops_playlist_and_keeps_finished_items(script, dest):
    item_urls = build_playlist(script, 5)
    holder: dict = {}

    def cancel_after_second(url: str) -> None:
        if url == item_urls[1]:
            holder["job"].cancel()

    script.before_download = cancel_after_second

    events: list = []
    job_queue: "queue.Queue" = queue.Queue()
    job = dl.DownloadJob(make_request(PLAYLIST_URL, dest), job_queue)
    holder["job"] = job
    job.start()
    while job.is_alive() or not job_queue.empty():
        try:
            events.append(job_queue.get(timeout=0.1))
        except queue.Empty:
            continue
    job.join(timeout=10)

    done = of_type(events, dl.JobFinished)[-1]
    assert done.cancelled is True
    # prvni polozka se dokoncila, zbytek uz ne
    assert len(done.downloaded) == 1
    assert len(script.downloaded) == 1


# --- chovani pri uz existujicim souboru ------------------------------------
def test_existing_file_is_skipped(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    (dest / "Song.mp3").write_bytes(b"old")

    events, _ = run(make_request(VIDEO_URL, dest, existing_policy="skip"))

    skipped = of_type(events, dl.ItemSkipped)
    assert len(skipped) == 1
    assert (dest / "Song.mp3").read_bytes() == b"old"
    assert not script.downloaded


def test_existing_file_gets_numbered_copy(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    (dest / "Song.mp3").write_bytes(b"old")

    events, _ = run(make_request(VIDEO_URL, dest, existing_policy="rename"))

    path = of_type(events, dl.ItemFinished)[0].path
    assert path.name == "Song (2).mp3"
    assert (dest / "Song.mp3").read_bytes() == b"old"


def test_existing_file_is_overwritten(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    (dest / "Song.mp3").write_bytes(b"old")

    events, _ = run(make_request(VIDEO_URL, dest, existing_policy="overwrite"))

    path = of_type(events, dl.ItemFinished)[0].path
    assert path.name == "Song.mp3"
    assert path.read_bytes() != b"old"


# --- chyby okoli ------------------------------------------------------------
def test_missing_ffmpeg_is_reported(script, dest, monkeypatch):
    monkeypatch.setattr(dl.paths, "ffmpeg_path", lambda: None)
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")

    events, _ = run(make_request(VIDEO_URL, dest))
    assert of_type(events, dl.JobFailed)[-1].error.code == "FFMPEG_MISSING"


def test_unwritable_destination_is_reported(script, tmp_path):
    blocked = tmp_path / "file-not-a-dir"
    blocked.write_text("x")
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")

    events, _ = run(make_request(VIDEO_URL, blocked))
    assert of_type(events, dl.JobFailed)[-1].error.code == "DEST_NOT_WRITABLE"


def test_network_error_is_translated(script, dest):
    script.errors[VIDEO_URL] = (
        "ERROR: unable to download webpage: <urlopen error [Errno -3] "
        "Temporary failure in name resolution>"
    )
    events, _ = run(make_request(VIDEO_URL, dest))

    error = of_type(events, dl.JobFailed)[-1].error
    assert error.code == "NETWORK"
    assert error.detail  # technicky detail se nese dal pro diagnostiku


def test_live_stream_is_refused_before_download(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Live!", is_live=True)
    events, _ = run(make_request(VIDEO_URL, dest))

    assert of_type(events, dl.JobFailed)[-1].error.code == "VIDEO_LIVE"
    assert not script.downloaded


def test_upcoming_premiere_is_refused(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Soon", live_status="is_upcoming")
    events, _ = run(make_request(VIDEO_URL, dest))

    assert of_type(events, dl.JobFailed)[-1].error.code == "VIDEO_NOT_STARTED"


def test_missing_output_file_is_detected(script, dest, monkeypatch):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    # download nic nezapise -> downloader to musi poznat, ne mlcet
    monkeypatch.setattr(FakeYoutubeDL, "download", lambda self, urls: None)

    events, _ = run(make_request(VIDEO_URL, dest))
    assert of_type(events, dl.JobFailed)[-1].error.code == "OUTPUT_MISSING"


# --- nastaveni se propisuje do yt-dlp --------------------------------------
def test_quality_and_postprocessors_reflect_settings(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    captured: list[dict] = []
    original = FakeYoutubeDL.__init__

    def capture(self, options):
        captured.append(options)
        original(self, options)

    FakeYoutubeDL.__init__ = capture
    try:
        run(make_request(VIDEO_URL, dest, quality="192", write_tags=False,
                         embed_cover=False))
    finally:
        FakeYoutubeDL.__init__ = original

    download_opts = [o for o in captured if "postprocessors" in o][-1]
    steps = download_opts["postprocessors"]
    assert steps[0]["key"] == "FFmpegExtractAudio"
    assert steps[0]["preferredquality"] == "192"
    assert len(steps) == 1  # tagy ani obal se nepridavaji
    assert download_opts["writethumbnail"] is False


def test_best_quality_maps_to_vbr_zero(script, dest):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Song")
    captured: list[dict] = []
    original = FakeYoutubeDL.__init__

    def capture(self, options):
        captured.append(options)
        original(self, options)

    FakeYoutubeDL.__init__ = capture
    try:
        run(make_request(VIDEO_URL, dest, quality="best", write_tags=True,
                         embed_cover=True))
    finally:
        FakeYoutubeDL.__init__ = original

    steps = [o for o in captured if "postprocessors" in o][-1]["postprocessors"]
    assert steps[0]["preferredquality"] == "0"
    # FFmpegMetadata tu zamerne neni - tagy pise tracki.core.tagging, protoze
    # yt-dlp dosazuje za interpreta nazev kanalu.
    assert [s["key"] for s in steps] == ["FFmpegExtractAudio", "EmbedThumbnail"]
    assert not any(s["key"] == "FFmpegMetadata" for s in steps)


# --- tagy ------------------------------------------------------------------
def read_tags(path):
    from mutagen.id3 import ID3

    return ID3(str(path))


def test_tags_are_written_and_channel_is_not_used_as_artist(script, dest):
    script.infos[VIDEO_URL] = info(
        "aBcD1234_-x", "Kapela - Pisnicka",
        uploader="Nahodny Kanal 123", channel="Nahodny Kanal 123",
        uploader_id="@nahodnykanal",
    )

    events, _ = run(make_request(VIDEO_URL, dest, write_tags=True))
    path = of_type(events, dl.ItemFinished)[0].path

    frames = read_tags(path)
    assert frames["TPE1"].text == ["Kapela"]
    assert frames["TIT2"].text == ["Pisnicka"]
    assert "Kanal" not in str(frames["TPE1"].text)


def test_tags_are_not_written_when_disabled(script, dest):
    from mutagen.id3 import ID3, ID3NoHeaderError

    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Kapela - Pisnicka")
    events, _ = run(make_request(VIDEO_URL, dest, write_tags=False))
    path = of_type(events, dl.ItemFinished)[0].path

    with pytest.raises(ID3NoHeaderError):
        ID3(str(path))


def test_tagging_failure_does_not_fail_the_download(script, dest, monkeypatch):
    script.infos[VIDEO_URL] = info("aBcD1234_-x", "Kapela - Pisnicka")
    monkeypatch.setattr(dl.tagging, "write", lambda path, tags: False)

    events, _ = run(make_request(VIDEO_URL, dest, write_tags=True))

    finished = of_type(events, dl.ItemFinished)
    assert len(finished) == 1
    assert finished[0].path.is_file()
    assert not of_type(events, dl.JobFailed)


def test_filename_and_tags_use_cleaned_title(script, dest):
    script.infos[VIDEO_URL] = info(
        "aBcD1234_-x", "Kapela - Pisnicka (Official Video) [HD]",
        uploader="Nahodny Kanal",
    )

    events, _ = run(make_request(VIDEO_URL, dest, clean_titles=True,
                                 write_tags=True))
    finished = of_type(events, dl.ItemFinished)[0]

    assert finished.path.name == "Kapela - Pisnicka.mp3"
    assert finished.title == "Kapela - Pisnicka"  # i v historii a v UI

    frames = read_tags(finished.path)
    assert frames["TPE1"].text == ["Kapela"]
    assert frames["TIT2"].text == ["Pisnicka"]


def test_cleaning_can_be_disabled(script, dest):
    script.infos[VIDEO_URL] = info(
        "aBcD1234_-x", "Kapela - Pisnicka (Official Video)",
    )

    events, _ = run(make_request(VIDEO_URL, dest, clean_titles=False,
                                 write_tags=True))
    finished = of_type(events, dl.ItemFinished)[0]

    assert finished.path.name == "Kapela - Pisnicka (Official Video).mp3"
    assert read_tags(finished.path)["TIT2"].text == ["Pisnicka (Official Video)"]


def test_settings_drive_cleaning(dest):
    from tracki.core.config import Settings

    settings = Settings().normalized()
    assert settings.clean_titles is True

    settings.clean_titles = False
    request = dl.DownloadRequest.from_settings(urls.parse(VIDEO_URL), settings)
    assert request.clean_titles is False
