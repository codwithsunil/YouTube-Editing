"""End card: every video ends on "Happy Coding!" (user rule, 2026-11-02).

After the last spoken goodbye the render appends an ~8 s card: the video's last frame, blurred and darkened, under
  Happy Coding!  ·  Keep in touch for more interesting videos  ·  a motivational code line  ·  NEXT <next topic> (when set)  ·  <site>
with the music track's own ending, faded out over the last 2 s. The text sits in the upper middle, so YouTube's end-screen
elements (Subscribe, watch-next; allowed in the last 5-20 s) fit in the lower third.

  render       appends the card after QA when end_card.enabled (the outro music bed is skipped: the card carries the ending)
  end-card     rebuilds the card and the final from full_video/_parts/<id>_no_end_card.mp4 (e.g. after changing "next")

Motivational code (user rule, 2026-11-04: "always share some motivational code for the learner at the end, make it a
format"): a code panel with a comment line and one line of code, syntax-coloured, e.g.
  // every day, one more row
  while (learning) { addOneMoreStar(); }
end_card.motto = {"comment", "code"} per lesson (written to fit the video's topic), else end_card.mottos[lesson_number % n].

The final without the card is kept in full_video/_parts/. Parts are joined by stream copy with the card's video track
re-timed to the main video's time base (different time bases made the joined video stop 8 s before its audio)."""
import json, os, re, shutil, subprocess, time, urllib.parse
from PIL import Image, ImageDraw, ImageFont
from . import config

W, H = 1920, 1080

def _rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def site(cfg):
    """end_card.site, else the WordPress site's host (never invented)."""
    E = cfg["end_card"]
    if E.get("site"): return E["site"]
    u = (cfg.get("wordpress") or {}).get("site_url")
    return urllib.parse.urlparse(u).netloc if u else ""

KEYWORDS = {"while", "for", "if", "else", "do", "try", "catch", "return", "true", "false", "var", "int"}

def motto(cfg):
    """{"comment", "code"}: the lesson's own end_card.motto, else one of end_card.mottos by lesson number."""
    E = cfg["end_card"]
    if E.get("motto"): return E["motto"]
    ms = E.get("mottos") or []
    return ms[int(cfg["project"].get("lesson_number") or 0) % len(ms)] if ms else None

def code_tokens(code, pal):
    """[(text, rgb)]: keywords cyan, function names lime, the rest plain."""
    out = []
    for m in re.finditer(r"[A-Za-z_]\w*|\s+|.", code):
        t = m.group(); after = code[m.end():m.end() + 1]
        c = pal["cyan"] if t in KEYWORDS else pal["lime"] if after == "(" and t[0].isalpha() else pal["text"]
        out.append((t, _rgb(c)))
    return out

def layers(cfg, out_dir):
    """Four transparent 1920x1080 PNGs, faded in one after the other: title, line, motivational code, next + site."""
    E, G = cfg["end_card"], cfg["graphics"]; pal = G["palette"]; os.makedirs(out_dir, exist_ok=True)
    font = lambda k, s: ImageFont.truetype(os.path.join(config.ROOT, G[k]), s)
    text, lime, cyan, muted, ink = _rgb(pal["text"]), _rgb(pal["lime"]), _rgb(pal["cyan"]), (203, 213, 225), _rgb(pal["canvas"])
    def centered(d, y, parts, f):
        x = (W - sum(d.textlength(t, font=f) for t, _ in parts)) / 2
        for t, c in parts: d.text((x, y), t, font=f, fill=c); x += d.textlength(t, font=f)
    paths = []
    a = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(a)
    centered(d, 95, [(E["title"][0], text), (E["title"][1], lime)], font("font_black", 150))
    b = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(b)
    d.rounded_rectangle(((W - 120) / 2, 318, (W + 120) / 2, 326), 4, fill=lime)
    centered(d, 345, [(E["line"], text)], font("font_semibold", 52))
    m = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(m); mo = motto(cfg)
    if mo:                                            # the code panel: comment line, then the code line
        def mono(size, weight):
            f = ImageFont.truetype(os.path.join(config.ROOT, G.get("font_mono", "assets/fonts/JetBrainsMono-wght.ttf")), size)
            try: f.set_variation_by_axes([weight])
            except (OSError, AttributeError): pass
            return f
        fc, fk = mono(30, 500), mono(42, 700); toks = code_tokens(mo["code"], pal)
        cw = sum(d.textlength(t, font=fk) for t, _ in toks); w = max(cw, d.textlength(mo.get("comment", ""), font=fc)) + 96
        if w > W - 160: raise ValueError(f"end_card motto too long ({w:.0f} px > {W - 160}): shorten the code line")
        x0 = (W - w) / 2; d.rounded_rectangle((x0, 440, x0 + w, 560), 18, fill=(*_rgb(pal["card"]), 235), outline=_rgb(pal["border"]), width=2)
        if mo.get("comment"): d.text((x0 + 48, 455), mo["comment"], font=fc, fill=_rgb(pal["muted"]))
        x = x0 + 48
        for t, col in toks: d.text((x, 498), t, font=fk, fill=col); x += d.textlength(t, font=fk)
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c); fb = font("font_bold", 38)
    if E.get("next"):
        lw, nw = d.textlength("NEXT", font=fb), d.textlength("  " + E["next"], font=fb); x = (W - lw - nw - 36) / 2
        d.rounded_rectangle((x, 595, x + lw + 36, 653), 29, fill=cyan); d.text((x + 18, 601), "NEXT", font=fb, fill=ink)
        d.text((x + lw + 36, 601), "  " + E["next"], font=fb, fill=text)
    if site(cfg): centered(d, 680 if E.get("next") else 600, [(site(cfg), muted)], font("font_semibold", 34))
    for n, im in enumerate((a, b, m, c), 1):
        p = os.path.join(out_dir, f"l{n}.png"); im.save(p); paths.append(p)
    return paths

def _probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip().splitlines()[0]

def clip(cfg, main_mp4, out_mp4):
    """The card as its own clip, encoded like the main video, its video track on the main video's time base."""
    E = cfg["end_card"]; d = float(E["duration_s"]); wd = os.path.dirname(out_mp4); os.makedirs(wd, exist_ok=True)
    dur = float(_probe(main_mp4, "format=duration")); tb = _probe(main_mp4, "stream=time_base", "v:0").split("/")[1]
    bg = os.path.join(wd, "bg.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, dur - 0.25):.3f}", "-i", main_mp4, "-frames:v", "1", bg], check=True)
    l1, l2, l3, l4 = layers(cfg, wd); music = os.path.join(config.ROOT, cfg["audio"]["music"]["file"])
    mlen = float(_probe(music, "format=duration")); fps = cfg["output"]["fps"]; fo = max(0.0, d - 2.0)
    fc = (f"[0]scale=2112:1188,zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(d * fps)}:s={W}x{H}:fps={fps},"
          "gblur=sigma=22,eq=brightness=-0.22:saturation=0.7,drawbox=c=0x101827@0.35:t=fill,fade=t=in:st=0:d=0.5[bg];"
          "[1]format=rgba,fade=t=in:st=0.3:d=0.6:alpha=1[a];[2]format=rgba,fade=t=in:st=0.9:d=0.6:alpha=1[b];"
          "[3]format=rgba,fade=t=in:st=1.5:d=0.6:alpha=1[m];[4]format=rgba,fade=t=in:st=2.1:d=0.6:alpha=1[c];"
          "[bg][a]overlay[x];[x][b]overlay[y];[y][m]overlay[z];[z][c]overlay,format=yuv420p[v];"
          f"[5]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.4,afade=t=out:st={fo}:d={d - fo},"
          f"loudnorm=I={E['music_lufs']}:TP=-2[aud]")
    tmp = out_mp4 + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", str(d), "-i", bg]
                   + sum((["-loop", "1", "-framerate", str(fps), "-t", str(d), "-i", p] for p in (l1, l2, l3, l4)), [])
                   + ["-ss", f"{max(0.0, mlen - d - 0.5):.3f}", "-t", str(d), "-i", music, "-filter_complex", fc, "-map", "[v]", "-map", "[aud]"]
                   + cfg["output"]["x264"] + ["-r", str(fps), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
                   + cfg["output"]["audio_codec"] + ["-ar", "48000", "-t", str(d), tmp], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c", "copy", "-video_track_timescale", tb, out_mp4], check=True); os.remove(tmp)
    return out_mp4

def _keep(path, parts, why):
    """Never overwrite: move an earlier file into _parts with a suffix that says why and when."""
    base, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(parts, f"{base}_{why}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"); shutil.move(path, dst); return dst

def append(cfg, final_mp4, fresh=False):
    """final -> _parts/<id>_no_end_card.mp4 (kept), then final = that + card.
    fresh=True (after a render): the new final is the new part; an older part is kept with a suffix.
    fresh=False (the end-card stage): rebuilds from the part; the previous final is kept with a suffix."""
    P = cfg["paths"]; lid = cfg["project"]["lesson_id"]; parts = os.path.join(P["full_video"], "_parts"); os.makedirs(parts, exist_ok=True)
    main = os.path.join(parts, f"{lid}_no_end_card.mp4"); mark = os.path.join(parts, "end_card.json")
    if fresh and os.path.exists(main):
        _keep(main, parts, "previous_render")
    if not os.path.exists(main):
        if not os.path.exists(final_mp4): raise FileNotFoundError(final_mp4)
        shutil.move(final_mp4, main)
    elif os.path.exists(final_mp4):
        made = json.load(open(mark)) if os.path.exists(mark) else {}
        if made.get("final_size") != os.path.getsize(final_mp4):         # the final changed since the card made it
            raise FileExistsError(f"{final_mp4} was not made from {main}: move one of them aside first (finals are never overwritten silently)")
    card = clip(cfg, main, os.path.join(P["full_video"], "end_card", "end_card.mp4"))
    lst = os.path.join(parts, "concat.txt")
    open(lst, "w").write(f"file '{os.path.abspath(main)}'\nfile '{os.path.abspath(card)}'\n")
    tmp = final_mp4 + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", tmp], check=True)
    v, a = float(_probe(tmp, "stream=duration", "v:0")), float(_probe(tmp, "stream=duration", "a:0"))
    want = float(_probe(main, "format=duration")) + float(cfg["end_card"]["duration_s"])
    if abs(v - a) > 0.1 or abs(v - want) > 0.15:
        os.remove(tmp); raise RuntimeError(f"joined video {v:.2f} s, audio {a:.2f} s, expected {want:.2f} s: not replacing the final")
    if os.path.exists(final_mp4): _keep(final_mp4, parts, "previous_end_card")
    os.replace(tmp, final_mp4)
    json.dump({"main_size": os.path.getsize(main), "final_size": os.path.getsize(final_mp4), "card": card, "duration_s": round(v, 3)},
              open(mark, "w"), indent=1)
    return {"file": final_mp4, "duration_s": round(v, 2), "without_card": main}
