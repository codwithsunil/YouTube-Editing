"""Instagram Reels against a fake Graph API: nothing appears without --publish, nothing is published twice, and every
caption points to the full YouTube video (user 2026-11-20)."""
import json
import pytest
from ytpipe import instagram as ig

class FakeGraph:
    def __init__(self, statuses=("IN_PROGRESS", "FINISHED")):
        self.calls, self.statuses = [], list(statuses)
    def __call__(self, method, url, params=None, data=None, headers=None):
        self.calls.append((method, url.split("v21.0/")[-1], dict(params or {}), len(data or b""), dict(headers or {})))
        if url.endswith("/media") and method == "POST": return 200, {"id": "C1"}
        if "rupload" in url: return 200, {"success": True}
        if url.endswith("/C1"): return 200, {"status_code": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]}
        if url.endswith("/media_publish"): return 200, {"id": "M1"}
        if url.endswith("/M1"): return 200, {"permalink": "https://www.instagram.com/reel/abc/"}
        return 404, {"error": {"message": "unexpected " + url}}

def _item(tmp_path, monkeypatch, caption):
    f = tmp_path / "short_01.mp4"; f.write_bytes(b"x" * 1000)
    monkeypatch.setattr(ig, "reel_item", lambda key, queue=None: {"key": key, "file": str(f), "caption": caption})

def test_without_publish_nothing_is_posted(tmp_path, monkeypatch):
    _item(tmp_path, monkeypatch, "16 = 10000!\nFull video on YouTube: Code With Sunil (link in bio)")
    g = FakeGraph(); c = ig.Client("T", "IG1", g, sleep=lambda s: None)
    r = ig.post("S31", c, publish_now=False, state_path=str(tmp_path / "st.json"))
    assert r == {"key": "S31", "container": "C1", "published": False}
    assert not any(p.endswith("media_publish") for _, p, *_ in g.calls)
    up = [x for x in g.calls if "rupload" in x[1] or x[3]]
    assert up and up[0][3] == 1000 and up[0][4]["file_size"] == "1000" and up[0][4]["Authorization"] == "OAuth T"
    first = g.calls[0]; assert first[2]["media_type"] == "REELS" and first[2]["upload_type"] == "resumable"

def test_published_once_then_skipped(tmp_path, monkeypatch):
    _item(tmp_path, monkeypatch, "x\nFull video on YouTube: Code With Sunil (link in bio)")
    st = str(tmp_path / "st.json"); g = FakeGraph(); c = ig.Client("T", "IG1", g, sleep=lambda s: None)
    r = ig.post("S31", c, publish_now=True, state_path=st)
    assert r["published"] and r["media_id"] == "M1" and json.load(open(st))["S31"]["permalink"].endswith("/reel/abc/")
    n = len(g.calls); r2 = ig.post("S31", c, publish_now=True, state_path=st)
    assert "already" in r2 and len(g.calls) == n

def test_processing_error_stops_before_publishing(tmp_path, monkeypatch):
    _item(tmp_path, monkeypatch, "x\nFull video on YouTube")
    g = FakeGraph(statuses=("ERROR",)); c = ig.Client("T", "IG1", g, sleep=lambda s: None)
    with pytest.raises(ig.IGError): ig.post("S31", c, publish_now=True, state_path=str(tmp_path / "st.json"))
    assert not any(p.endswith("media_publish") for _, p, *_ in g.calls)

def test_caption_must_point_to_the_full_video(tmp_path):
    md = tmp_path / "s.md"; f = tmp_path / "S9.mp4"; f.write_bytes(b"x")
    md.write_text("# T\n\n## YouTube Shorts\n**Title:** T\n\n**Description:**\nd\n\n## Instagram Reel\n**Caption:**\nOnly a hook #tag\n\n## Cover frame\n1:00\n")
    q = tmp_path / "q.json"; q.write_text(json.dumps({"items": [{"key": "S9", "file": str(f), "metadata": str(md), "date": "2026-11-21", "time": "18:00"}]}))
    with pytest.raises(ig.IGError, match="full video"): ig.reel_item("S9", str(q))

def test_one_reel_a_day_in_queue_order():
    q = {"items": [{"key": k, "date": d, "time": "18:00"} for k, d in (("S01", "2026-11-21"), ("S02", "2026-11-22"))]}
    assert ig.next_due(q, {}, "2026-11-21 17:59") is None
    assert ig.next_due(q, {}, "2026-11-21 18:00")["key"] == "S01"
    assert ig.next_due(q, {"S01": {"media_id": "M"}}, "2026-11-21 20:00") is None        # S02's day has not come
    assert ig.next_due(q, {}, "2026-11-23 18:30")["key"] == "S01"                         # a missed day: still one, in order
