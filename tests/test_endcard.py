"""End card (user rule 2026-11-02: every video ends on "Happy Coding!"): layers, the joined final (video and audio the
same length, the card's time base matched), the card-less part kept, nothing overwritten, and no outro music bed."""
import glob, os, subprocess
from PIL import Image
from ytpipe import audio, endcard
from tests.test_core import make_cfg

def probe(path, entries, stream=None):
    return endcard._probe(path, entries, stream)

def make_main(path, seconds=3):
    """A 1080p30 clip with a tone, encoded like a final, on a different time base than the card's default."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=30:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}:sample_rate=48000", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-video_track_timescale", "16000", path], check=True)

def cfg_for(tmp_path, **card):
    music = str(tmp_path / "music.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=20:sample_rate=48000", music], check=True)
    cfg = make_cfg(tmp_path); cfg["audio"]["music"]["file"] = music
    cfg["end_card"].update({"duration_s": 2.0, **card}); cfg["output"]["x264"] = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]
    cfg["wordpress"]["site_url"] = "https://example.test"
    os.makedirs(cfg["paths"]["full_video"], exist_ok=True)
    return cfg

def test_layers_and_site(tmp_path):
    cfg = cfg_for(tmp_path, next="Pattern printing with loops")
    ps = endcard.layers(cfg, str(tmp_path / "l"))
    assert len(ps) == 4 and all(Image.open(p).size == (1920, 1080) for p in ps)
    assert Image.open(ps[3]).getbbox() is not None                         # NEXT row and site drawn
    assert endcard.site(cfg) == "example.test"
    cfg["end_card"]["next"] = None; cfg["wordpress"]["site_url"] = None
    assert Image.open(endcard.layers(cfg, str(tmp_path / "m"))[3]).getbbox() is None     # nothing invented

def test_append_keeps_the_part_and_matches_lengths(tmp_path):
    cfg = cfg_for(tmp_path); final = os.path.join(cfg["paths"]["full_video"], f"{cfg['project']['lesson_id']}.mp4")
    make_main(final)
    r = endcard.append(cfg, final, fresh=True)
    v, a = float(probe(final, "stream=duration", "v:0")), float(probe(final, "stream=duration", "a:0"))
    assert abs(v - 5.0) < 0.15 and abs(v - a) < 0.1 and r["duration_s"] > 4.8
    assert os.path.exists(r["without_card"]) and abs(float(probe(r["without_card"], "format=duration")) - 3.0) < 0.1
    assert subprocess.run(["ffmpeg", "-v", "error", "-i", final, "-f", "null", "-"], capture_output=True, text=True).stderr == ""
    endcard.append(cfg, final)                                              # rebuild the card: the previous final is kept
    parts = os.path.join(cfg["paths"]["full_video"], "_parts")
    assert len(glob.glob(os.path.join(parts, "*_previous_end_card_*.mp4"))) == 1
    make_main(final); endcard.append(cfg, final, fresh=True)                # a new render: the previous part is kept
    assert len(glob.glob(os.path.join(parts, "*_previous_render_*.mp4"))) == 1

def test_a_final_not_made_from_the_part_is_not_replaced(tmp_path):
    cfg = cfg_for(tmp_path); final = os.path.join(cfg["paths"]["full_video"], f"{cfg['project']['lesson_id']}.mp4")
    make_main(final); endcard.append(cfg, final, fresh=True)
    make_main(final, seconds=4)                                             # someone rendered again without --fresh
    try:
        endcard.append(cfg, final); assert False, "should refuse"
    except FileExistsError:
        pass

def test_no_outro_bed_while_the_card_is_on(tmp_path):
    cfg = cfg_for(tmp_path); cfg["audio"]["music"]["placement"] = ["outro"]
    segs = [{"face_in": 0.0, "face_out": 60.0}]
    assert audio.music_plan(cfg, segs, [], []) == []
    cfg["end_card"]["enabled"] = False
    assert len(audio.music_plan(cfg, segs, [], [])) == 1

def test_every_card_has_motivational_code(tmp_path):
    """User rule 2026-11-04: the card always shares a motivational code line; the lesson's own, else a default."""
    cfg = cfg_for(tmp_path)
    assert endcard.motto(cfg)["code"]                                      # a default from end_card.mottos
    cfg["end_card"]["motto"] = {"comment": "// keep going", "code": "while (learning) { addOneMoreStar(); }"}
    assert endcard.motto(cfg)["code"].startswith("while")
    cols = {t: c for t, c in endcard.code_tokens(cfg["end_card"]["motto"]["code"], cfg["graphics"]["palette"])}
    assert cols["while"] != cols["learning"] and cols["addOneMoreStar"] != cols["learning"]
    assert len(endcard.layers(cfg, str(tmp_path / "layers"))) == 4
    cfg["end_card"]["motto"]["code"] = "x" * 200
    try:
        endcard.layers(cfg, str(tmp_path / "layers2")); assert False, "too long should refuse"
    except ValueError:
        pass
