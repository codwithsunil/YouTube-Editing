"""Instagram: posts a lesson's rendered Shorts as Reels on the presenter's Instagram (Instagram Graph API with Facebook
Login: a Professional account linked to the 'Code With Sunil' Facebook Page; user 2026-11-20).

  python -m ytpipe.instagram check                      read-only: the account behind the stored token
  python -m ytpipe.instagram reel <key> [--publish]     S01 ... : container + upload + processing; publishes only with --publish
  python -m ytpipe.instagram due [--publish]            the next queued Reel whose day has come (18:00 IST), at most one a run

The queue (lessons/_series/instagram_queue.json) holds every Short in series order, one a day at 18:00 IST, like the YouTube
Shorts (user 2026-11-20); a Reel is only posted once its YouTube Short is public. Instagram's API cannot schedule: the
daily job runs 'due --publish', so a missed day moves the rest of the queue by a day instead of posting two at once.

Safety rules (enforced here):
  - the caption is the Short's own "Instagram Reel" text (metadata/shorts/*.md), never generated here; it must point to the
    full YouTube video (user 2026-11-20: Reel captions cannot link, so the caption says where the full video is)
  - without --publish nothing appears on Instagram: the container is uploaded and processed only (a dry run Meta keeps 24 h)
  - each Short is published at most once: lessons/_series/instagram_state.json records every published media id
  - credentials (a never-expiring Page token, the account ids) come from the macOS Keychain (service ytpipe-instagram)
The HTTP transport is injectable: tests run against a fake Graph API."""
import argparse, json, os, subprocess, sys, time, urllib.parse, urllib.request
from . import publish, youtube as y

GRAPH = "https://graph.facebook.com/v21.0"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v21.0"
SERVICE = "ytpipe-instagram"
STATE = "lessons/_series/instagram_state.json"
QUEUE = "lessons/_series/instagram_queue.json"
FULL_VIDEO_HINT = "full video"                                    # every caption must say where the full video is

class IGError(Exception): pass

def _keychain(account, run=subprocess.run):
    r = run(["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip(): raise IGError(f"no '{account}' in the Keychain ({SERVICE}): run the Meta app setup first")
    return r.stdout.strip()

def http(method, url, params=None, data=None, headers=None):
    """-> (status, json). Default transport; tests pass their own."""
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except ValueError: return e.code, {"error": {"message": str(e)}}

class Client:
    def __init__(self, token, ig_user_id, transport=http, sleep=time.sleep):
        self.t, self.ig, self.tr, self.sleep = token, ig_user_id, transport, sleep

    @classmethod
    def from_keychain(cls):
        ids = json.loads(_keychain("ids")); return cls(_keychain("page_token"), ids["ig_user_id"])

    def call(self, method, path, params=None):
        s, b = self.tr(method, f"{GRAPH}/{path}", {**(params or {}), "access_token": self.t})
        if s >= 400 or "error" in b: raise IGError(f"{method} {path}: {b.get('error', {}).get('message', s)}")
        return b

    def account(self): return self.call("GET", self.ig, {"fields": "id,username,media_count"})

    def container(self, path, caption, cover_ms=None):
        """Reel container, then the file itself (resumable upload to Meta's servers), then wait until it is processed."""
        p = {"media_type": "REELS", "upload_type": "resumable", "caption": caption, "share_to_feed": "true"}
        if cover_ms is not None: p["thumb_offset"] = str(int(cover_ms))
        c = self.call("POST", f"{self.ig}/media", p); cid = c["id"]
        with open(path, "rb") as f: data = f.read()
        s, b = self.tr("POST", c.get("uri") or f"{RUPLOAD}/{cid}", None, data, {"Authorization": f"OAuth {self.t}", "offset": "0", "file_size": str(len(data)), "Content-Type": "application/octet-stream"})
        if s >= 400 or not b.get("success"): raise IGError(f"upload of {os.path.basename(path)} failed: {b}")
        for _ in range(120):                                          # up to 10 minutes of processing
            st = self.call("GET", cid, {"fields": "status_code,status"})
            if st["status_code"] == "FINISHED": return cid
            if st["status_code"] in ("ERROR", "EXPIRED"): raise IGError(f"Instagram could not process the Reel: {st.get('status')}")
            self.sleep(5)
        raise IGError("Instagram is still processing after 10 minutes; try again later")

    def publish(self, cid):
        mid = self.call("POST", f"{self.ig}/media_publish", {"creation_id": cid})["id"]
        return mid, self.call("GET", mid, {"fields": "permalink"}).get("permalink")

def reel_item(key, queue=QUEUE):
    """The queued Short with this key: its file and the caption from its metadata .md."""
    for it in json.load(open(queue))["items"]:
        if it["key"] == key:
            c = publish.short_copy(open(it["metadata"], encoding="utf-8").read())
            if not c["caption"]: raise IGError(f"{key}: no 'Instagram Reel' caption in {it['metadata']}")
            if FULL_VIDEO_HINT not in c["caption"].lower(): raise IGError(f"{key}: the caption must say where the full video is ('Full video on YouTube ...')")
            if not os.path.exists(it["file"]): raise IGError(f"{key}: missing {it['file']}")
            return {**it, "caption": c["caption"]}
    raise IGError(f"{key}: not in the Instagram queue")

def next_due(queue, state, now):
    """The first unpublished queue item whose day and time have come (now = 'YYYY-MM-DD HH:MM', local time)."""
    for it in queue["items"]:
        if state.get(it["key"], {}).get("media_id"): continue
        return it if f"{it['date']} {it['time']}" <= now else None
    return None

def post(key, client, publish_now=False, state_path=STATE, queue=QUEUE):
    st = json.load(open(state_path)) if os.path.exists(state_path) else {}
    if st.get(key, {}).get("media_id"): return {"key": key, "already": st[key]}
    it = reel_item(key, queue); cid = client.container(it["file"], it["caption"])
    if not publish_now: return {"key": key, "container": cid, "published": False}
    mid, link = client.publish(cid)
    st[key] = {"media_id": mid, "permalink": link, "published_at": time.strftime("%Y-%m-%d %H:%M"), "file": it["file"]}
    json.dump(st, open(state_path, "w"), indent=1)
    return {"key": key, "media_id": mid, "permalink": link, "published": True}

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ytpipe.instagram", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "reel", "due"]); ap.add_argument("key", nargs="?")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--ids", default=os.path.join(os.path.dirname(y.SERIES), "youtube_ids.json"))
    a = ap.parse_args(argv)
    try:
        c = Client.from_keychain()
        if a.cmd == "check": a_ = c.account(); print(f"@{a_['username']} ({a_['media_count']} posts): token OK, nothing posted")
        elif a.cmd == "reel": print(json.dumps(post(a.key, c, a.publish), indent=1))
        elif a.cmd == "due":
            st = json.load(open(STATE)) if os.path.exists(STATE) else {}
            it = next_due(json.load(open(QUEUE)), st, time.strftime("%Y-%m-%d %H:%M"))
            if not it: print("nothing due"); return
            ids = json.load(open(a.ids))
            if it["key"] not in y.public_now(y.Client.from_keychain(), {it["key"]: ids[it["key"]]}):
                print(f"{it['key']}: its YouTube Short is not public yet; waiting"); return
            print(json.dumps(post(it["key"], c, a.publish)))
    except (IGError, y.YTError) as e:
        sys.exit(f"instagram: {e}")

if __name__ == "__main__":
    main()
