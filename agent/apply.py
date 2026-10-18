"""Approved-queue applier. Usage:
  python apply.py approved.json            # fills each form, asks before submit
  python apply.py approved.json --auto     # submits when every required field was answered from the bank
  python apply.py approved.json --max 10
LinkedIn URLs in the file are PRE-FILL ONLY: the agent stops before Submit and you click it yourself."""
import sys, re, csv, json, time, random, difflib, pathlib, datetime, yaml
from playwright.sync_api import sync_playwright
H = pathlib.Path(__file__).parent
P = yaml.safe_load((H / "profile.yaml").read_text()); A = yaml.safe_load((H / "answers.yaml").read_text()) or {}
FIELDS = [(r"first name", P["first_name"]), (r"last name", P["last_name"]), (r"^(full )?name", P["full_name"]),
          (r"e-?mail", P["email"]), (r"phone|mobile", P["phone"]), (r"linkedin", P["linkedin"]),
          (r"current (company|employer)", P["current_company"]), (r"^location|city", P["city"])]
LABEL = "e=>(e.labels&&e.labels[0]?e.labels[0].innerText:(e.getAttribute('aria-label')||e.placeholder||'')).trim()"

def fill_known(pg):
    for rx, val in FIELDS:
        try:
            el = pg.get_by_label(re.compile(rx, re.I)).first
            if el.count() and el.is_visible() and not el.input_value(): el.fill(val)
        except Exception: pass
    try: pg.locator("input[type=file]").first.set_input_files(str(H / P["resume"]))
    except Exception: pass

def answer(pg, ask):
    """Fill empty required text fields from the bank. Returns labels it could not answer."""
    missing = []
    for el in pg.locator("input[required]:not([type=file]):not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea[required]").all():
        try:
            if not el.is_visible() or el.input_value(): continue
            lab = el.evaluate(LABEL).lower()
            best = max(A, key=lambda k: difflib.SequenceMatcher(None, k, lab).ratio() + (1 if k in lab else 0), default=None)
            if best and (best in lab or difflib.SequenceMatcher(None, best, lab).ratio() > .7) and A[best] != "TODO":
                el.fill(str(A[best]))
            elif ask:
                v = input(f"  Answer for “{lab}” (blank = skip): ").strip()
                el.fill(v) if v else missing.append(lab)
            else: missing.append(lab)
        except Exception: pass
    return missing

def log(job, result):
    new = not (H / "applications.csv").exists()
    with open(H / "applications.csv", "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["time", "company", "title", "url", "result"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), job.get("company"), job.get("title"), job["url"], result])

def career_page(pg, job, auto):
    pg.goto(job["url"]); pg.wait_for_load_state("networkidle")
    try: pg.get_by_role("link", name=re.compile(r"^apply", re.I)).first.click(timeout=3000)
    except Exception: pass
    fill_known(pg); missing = answer(pg, ask=not auto)
    if missing or not auto:
        print(f"  Review the form in the browser. Unresolved: {missing or 'none'}")
        if input("  Submit this application? [y/N] ").lower() != "y": return "skipped"
    pg.get_by_role("button", name=re.compile(r"submit( application)?", re.I)).last.click()
    time.sleep(4); return "submitted"

def linkedin(pg, job):
    pg.goto(job["url"]); pg.wait_for_load_state("domcontentloaded")
    try: pg.get_by_role("button", name=re.compile(r"easy apply", re.I)).first.click(timeout=6000)
    except Exception: return "no easy apply button (apply manually)"
    for _ in range(8):
        fill_known(pg); answer(pg, ask=True)
        nxt = pg.get_by_role("button", name=re.compile(r"^(next|review)", re.I))
        if not nxt.count(): break
        nxt.first.click(); time.sleep(1.2)
    input("  LinkedIn form is pre-filled. Check it, click Submit yourself, then press Enter… ")
    return "prefilled (you submitted)"

def main():
    args = sys.argv[1:]; auto = "--auto" in args
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 15
    jobs = json.loads(pathlib.Path(args[0]).read_text())[:mx]
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(pathlib.Path.home() / ".jobagent-profile"), headless=False)
        pg = ctx.new_page()
        for i, j in enumerate(jobs, 1):
            print(f"[{i}/{len(jobs)}] {j.get('company')} – {j.get('title')}")
            try: res = linkedin(pg, j) if "linkedin.com" in j["url"] else career_page(pg, j, auto)
            except Exception as e: res = f"error: {type(e).__name__}"
            print("  →", res); log(j, res)
            if i < len(jobs): time.sleep(random.randint(20, 60))
        ctx.close()
if __name__ == "__main__": main()
