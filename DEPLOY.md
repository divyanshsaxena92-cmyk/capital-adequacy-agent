# Deploying the Capital Adequacy Agent

## Your plan: GitHub + hosted website (Streamlit Community Cloud)
**Who can change what**
| Change | Who can do it |
|---|---|
| Code, rules, RBI PDFs in `regulatory_kb/library/` | Only people with write access to the GitHub repository. Every push redeploys the site for everyone. |
| Uploading a client workbook, updating the RBI knowledge base, importing data | Only an admin signed in on the site (viewer mode, below). |
| Exploring every page, the sample client, what-ifs, downloads | Every invited viewer. Decisions they try are session-only and are not saved. |

**Steps**
1. Create a **private** GitHub repository. Upload the *contents* of the `capital_agent` folder so `app.py`
   and `requirements.txt` sit at the top level. The `.gitignore` keeps local data and secrets out.
2. Go to share.streamlit.io, sign in with GitHub, choose **Create app** → your repository → branch `main` →
   main file `app.py`. Under *Advanced settings*: Python 3.12, and paste into **Secrets**:
   ```
   mode = "viewer"
   admin_password = "a-long-password-only-you-know"
   ```
3. Deploy. The app is private (it inherits the private repo). Click **Share** → invite colleagues by email;
   they sign in with Google or a one-time emailed link. The free tier allows one private app per account.
4. To change anything: edit and push to GitHub. The site redeploys; everyone sees the new version.

**Keeping RBI documents current on the hosted site**
The hosted service does not keep files written while the app runs - they disappear when it restarts or redeploys.
So add RBI PDFs by committing them to `regulatory_kb/library/` in GitHub (they are indexed automatically on every
start), and correct titles/dates in `regulatory_kb/sources.yaml`. "Update from RBI" may also be blocked from
cloud servers by RBI's website; the library folder always works.

**Confidentiality**
Community Cloud runs on servers outside Grant Thornton. Show the sample client only - viewer mode already blocks
workbook uploads for visitors; as admin, do not upload real client files there. For client work use option B.

## Other options
**A. Share from your laptop** (office network / VPN, while your laptop runs it): double-click `run_shared.bat`,
run `ipconfig`, colleagues open `http://<your IPv4>:8501`.

**B. GT internal server** (production, client data): `docker build -t capital-agent .` then
`docker run -d -p 8501:8501 -v capital-agent-data:/data -e CAPITAL_AGENT_MODE=viewer -e CAPITAL_AGENT_ADMIN_PASSWORD=... capital-agent`.
Ask IT for an intranet URL behind GT single sign-on, a backed-up volume for `/data`, and outbound HTTPS to
`*.rbi.org.in` only. Here uploads persist and are shared by all users.

## Shared vs private
- Shared: the RBI knowledge base and imported data (persistent on option B; reset on restart on Community Cloud).
- Private per browser session: the uploaded client workbook, the run, decisions, chat, theme.
