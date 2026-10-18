# DevOps & SRE job portal

**Portal** (`docs/`, GitHub Pages) – roles for Singapore, Thailand, Malaysia, Dubai/UAE, India remote, India product-company on-site, and global remote. Senior band for 9.5 yrs (roles asking 5–10.5 yrs, junior titles dropped). Refreshed daily by `.github/workflows/daily.yml`.

## Deploy
1. Create a GitHub repo, push this folder.
2. Settings → Pages → Deploy from branch `main`, folder `/docs`.
3. Actions → refresh-jobs → Run workflow (first fill). Open the Pages URL.
4. Add companies in `config.yaml` (Greenhouse/Lever/Ashby slugs from their careers URLs); check the workflow log to see which boards returned jobs.

## Daily use
Open portal → **Approve** the roles you want → **Export approved queue** (`approved.json`).
LinkedIn jobs: add `{"company":"X","title":"Y","url":"https://www.linkedin.com/jobs/view/..."}` entries to that file.

## Auto-apply agent (runs on your laptop)
```
cd agent && pip install -r requirements.txt && playwright install chromium
# edit answers.yaml (TODO items), then:
python apply.py approved.json          # asks before each submit
python apply.py approved.json --auto   # submits when all required fields were answered from your bank
```
First run: log in to LinkedIn once in the opened browser (session is kept in `~/.jobagent-profile`).
LinkedIn is pre-fill only; you click Submit. Results go to `agent/applications.csv`.
Captchas and dropdown-style questions pause for you. Keep to ~10–15 applications per run.
