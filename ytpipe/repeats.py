"""Stage 'repeats': phrases said twice in the flow of speech (user, 2026-11-03: "remove repetitive phrases",
reference lesson08 1:03-1:05 "is problem ko, ya is case ke liye"). Runs on the reviewed transcripts/transcript.txt
and proposes cuts for the cut list; nothing is applied automatically, because the exact boundaries need word timing
(Claude re-decodes the stretch with word timestamps and cuts in the nearest pauses, as in PRODUCTION_PLAYBOOK C23).

Patterns (all seen in lesson08):
  doubled      the same phrase twice in a row          "print kya karna hai? Print kya karna hai ji?"
  restatement  an alternative added with "ya"           "ek chhota sa example hai, ya ek bada task hai, ya ek problem hai"
  echo         a question echoed before its answer      "chalaana kab tak hai? / Ye loop counter chalaana hai"
  false start  a fragment, then the same words again    "to main kind of / isko main kind of string ke andar leta hoon"
  reworded     one word said twice in one breath        "initialise kar diya maine: loop counter ... initialise ho gaya"
  filler       a filler restart                         "par ye jo hai, ye boloon ki mera ye jo cheez hai"

-> reports/repeats.md (and the proposals in the returned list: face time, line text, the repeated part, the pattern)."""
import os, re
from . import transcript

STOP = set("to ye wo jo hai hain ki ke ka mein main hum log aur bhi ji theek a the is of and or so ek ye kya".split())
WINDOW_S = 8.0
FILLERS = ("ye boloon ki", "par ye jo hai", "let me say", "kya bolte hain", "matlab ki matlab")
TERMS = {"counter", "number", "flowchart", "condition", "program", "print"}     # the lesson's own words repeat on purpose

def tokens(text):
    return re.findall(r"[a-z0-9×<=>]+", text.lower().replace("’", "'"))

def _distinct(ws):
    return any(w not in STOP for w in ws)

def _doubled(ws, nmin=3):
    """The same n words (n >= nmin, not only filler) twice, back to back or with up to 2 words between."""
    for n in range(min(6, len(ws) // 2), nmin - 1, -1):
        for i in range(len(ws) - n):
            for gap in range(0, 3):
                j = i + n + gap
                if j + n <= len(ws) and ws[i:i + n] == ws[j:j + n] and _distinct(ws[i:i + n]):
                    return " ".join(ws[j:j + n])
    return None

def find(lines, window_s=WINDOW_S):
    """lines: transcript.parse() rows ({face, text, ...}); lines marked '—cut—' are skipped."""
    rows = [l for l in lines if not l["text"].startswith("—cut—")]; out = []
    for k, l in enumerate(rows):
        ws = tokens(l["text"]); t = l["face"]
        d = _doubled(ws)
        if d: out.append({"face": t, "pattern": "doubled", "repeated": d, "text": l["text"]})
        for i, w in enumerate(ws):                                         # the same long word again within 10 words
            if len(w) >= 7 and w not in TERMS and w in ws[i + 1:i + 11]:
                out.append({"face": t, "pattern": "reworded", "repeated": w, "text": l["text"]}); break
        low = l["text"].lower()
        for f in FILLERS:
            if f in low:
                out.append({"face": t, "pattern": "filler", "repeated": f, "text": l["text"]}); break
        if re.search(r",\s*ya\s+(is|ek|phir|uske|iske)\b", l["text"], re.I):
            m = re.search(r",\s*(ya\s+(?:is|ek|phir|uske|iske)\b[^,.?]*)", l["text"], re.I)
            out.append({"face": t, "pattern": "restatement", "repeated": m.group(1).strip(), "text": l["text"]})
        if k + 1 < len(rows) and rows[k + 1]["face"] - t <= window_s:
            nx = rows[k + 1]; a, b = ws[-8:], tokens(nx["text"])[:8]
            if l["text"].rstrip().endswith("?"):
                common = [w for w in a if w in b and w not in STOP]
                if len(common) >= 2 and len(tokens(nx["text"])) <= 8:
                    out.append({"face": nx["face"], "pattern": "echo", "repeated": nx["text"], "text": l["text"] + " / " + nx["text"]})
            elif not re.search(r"[.?!]\s*$", l["text"]):
                tail = a[-3:]
                for n in (3, 2):
                    if len(tail) >= n and _distinct(tail[-n:]) and " ".join(tail[-n:]) in " ".join(b):
                        out.append({"face": t, "pattern": "false start", "repeated": l["text"], "text": l["text"] + " / " + nx["text"]})
                        break
    return out

def report(found, path):
    L = ["# Repeated phrases (proposals)", "",
         "Phrases said twice in the flow of speech. Not cut automatically: for each one Claude re-decodes the stretch with word "
         "timestamps, cuts in the nearest pauses, and lists it in the cut list for your approval (PRODUCTION_PLAYBOOK C23).", ""]
    if not found: L.append("None found.")
    L += [f"- **{f['pattern']}** at face {int(f['face'] // 60)}:{f['face'] % 60:04.1f}: \"{f['repeated']}\"  \n  in: {f['text']}" for f in found]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    return path

def run(cfg):
    P = cfg["paths"]; src = os.path.join(P["transcripts"], "transcript.txt")
    found = find(transcript.parse(src)); os.makedirs(P["reports"], exist_ok=True)
    return found, report(found, os.path.join(P["reports"], "repeats.md"))
