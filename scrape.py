"""Collects DevOps/SRE jobs, filters to my targets, writes docs/jobs.json."""
import json, re, html, hashlib, pathlib, datetime as dt, urllib.request, yaml
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
OUT = ROOT / "docs" / "jobs.json"
MY = CFG["my_years"]

GEO = {"SG": r"singapore", "TH": r"thailand|bangkok|phuket", "MY": r"malaysia|kuala lumpur|penang|\bKL\b",
       "AE": r"dubai|abu dhabi|\buae\b|united arab emirates"}
IN = r"india|bengaluru|bangalore|hyderabad|pune|mumbai|chennai|delhi|gurgaon|gurugram|noida|kolkata|coimbatore|ahmedabad"
OPEN = r"worldwide|anywhere|global|apac|asia|india"
CLOSED = r"\b(us|usa|united states|canada|uk|europe|emea|eu|latam|brazil|germany|france|australia)\b"
ROLE = re.compile(r"devops|dev ops|site reliability|\bsre\b|reliability engineer", re.I)
JUNIOR = re.compile(r"junior|\bjr\b|intern\b|graduate|trainee|entry|associate", re.I)
SENIOR = re.compile(r"senior|\bsr\b|lead|staff|principal|manager|architect|head", re.I)

def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "devops-jobs-portal/1.0"})
        return json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        print("skip", url, type(e).__name__); return None

def txt(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h or "")))
def J(src, co, title, loc, url, desc="", posted="", curated=False, remote=None):
    return dict(source=src, company=co, title=title.strip(), location=(loc or "").strip(), url=url,
                desc=txt(desc), posted=(posted or "")[:10], curated=curated, remote=remote)

def greenhouse(t):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true") or {}
    return [J("greenhouse", j.get("company_name", t), j["title"], j["location"]["name"], j["absolute_url"],
              j.get("content"), j.get("updated_at"), True) for j in d.get("jobs", []) if ROLE.search(j["title"])]
def lever(s):
    d = get(f"https://api.lever.co/v0/postings/{s}?mode=json") or []
    return [J("lever", s, j["text"], j["categories"].get("location"), j["hostedUrl"], j.get("descriptionPlain"),
              dt.datetime.fromtimestamp(j["createdAt"] / 1000).isoformat(), True,
              j.get("workplaceType") == "remote") for j in d if ROLE.search(j["text"])]
def ashby(o):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{o}") or {}
    return [J("ashby", o, j["title"], j.get("location"), j["jobUrl"], j.get("descriptionPlain"),
              j.get("publishedAt"), True, j.get("isRemote")) for j in d.get("jobs", []) if ROLE.search(j["title"])]
def remotive(q):
    d = get(f"https://remotive.com/api/remote-jobs?search={q}") or {}
    return [J("remotive", j["company_name"], j["title"], j["candidate_required_location"], j["url"],
              j["description"], j["publication_date"], False, True) for j in d.get("jobs", []) if ROLE.search(j["title"])]
def remoteok():
    d = (get("https://remoteok.com/api") or [])[1:]
    return [J("remoteok", j["company"], j["position"], j.get("location") or "Worldwide", j["url"],
              j.get("description"), j.get("date"), False, True) for j in d if ROLE.search(j.get("position", ""))]

def years(t):
    for s in re.split(r"\.\s|•|;", t):
        if re.search(r"experience", s, re.I):
            m = re.search(r"(\d{1,2})\s*(?:\+|[-–]|to)?\s*(\d{1,2})?\s*\+?\s*(?:years|yrs)", s, re.I)
            if m: return int(m[1]), int(m[2]) if m[2] else None
    return None, None

def region(j):
    loc = j["location"]
    remote = j["remote"] if j["remote"] is not None else bool(re.search(r"remote|anywhere|worldwide", loc + j["title"], re.I))
    for tag, rx in GEO.items():
        if re.search(rx, loc, re.I): return tag
    if re.search(IN, loc, re.I):
        return "IN-REMOTE" if remote else ("IN-PRODUCT" if j["curated"] else None)
    if remote and (re.search(OPEN, loc, re.I) or (j["curated"] and not re.search(CLOSED, loc, re.I))):
        return "GLOBAL"
    return None

def main():
    prev = {j["id"]: j for j in json.loads(OUT.read_text())["jobs"]} if OUT.exists() else {}
    tasks = [(greenhouse, t) for t in CFG["greenhouse"]] + [(lever, t) for t in CFG["lever"]] + \
            [(ashby, t) for t in CFG["ashby"]] + [(remotive, "devops"), (remotive, "sre"), (remoteok, None)]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda a: a[0](a[1]) if a[1] else a[0](), tasks))
    raw = [j for r in results for j in r]
    print(f"fetched {len(raw)} DevOps/SRE postings from {sum(1 for r in results if r)} sources")
    today, out, seen = dt.date.today().isoformat(), [], set()
    for j in raw:
        jid = hashlib.sha1(j["url"].encode()).hexdigest()[:12]
        if jid in seen or JUNIOR.search(j["title"]): continue
        if any(b in j["company"].lower() + " " for b in CFG["blocklist"]): continue
        reg = region(j)
        lo, hi = years(j["desc"])
        if not reg or (lo is not None and not (5 <= lo <= MY + 1 and (hi is None or hi >= 7))): continue
        seen.add(jid)
        out.append(dict(id=jid, title=j["title"], company=j["company"], location=j["location"] or "Remote",
                        region=reg, url=j["url"], source=j["source"], posted=j["posted"],
                        years=("" if lo is None else f"{lo}{'-' + str(hi) if hi else '+'} yrs"),
                        senior=bool(SENIOR.search(j["title"]) or (lo and lo >= 6)),
                        first_seen=prev.get(jid, {}).get("first_seen", today)))
    out.sort(key=lambda j: (j["posted"] or j["first_seen"]), reverse=True)
    OUT.write_text(json.dumps({"updated": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z", "jobs": out}))
    print(f"kept {len(out)} jobs")
if __name__ == "__main__": main()
