#!/usr/bin/env python3
"""Maintain the cross-platform-tests run history site on the gh-pages branch.

Reads the existing site (previous runs ledger + archived per-run reports), appends
the current run, prunes per retention, copies the kept reports plus this run's new
report into an output directory, and renders an `index.html` table of all runs.

Retention: keep every release run (a `v*` tag push) plus the most recent
KEEP_DISPATCH non-release (manual dispatch) runs.

Inputs (env): GITHUB_RUN_NUMBER, GITHUB_RUN_ID, GITHUB_SHA, GITHUB_REF_NAME,
GITHUB_EVENT_NAME, GITHUB_REPOSITORY, GITHUB_SERVER_URL.

Paths (argv, with defaults): old-site new-report output-site
"""

from __future__ import annotations

import datetime
import html
import json
import os
import shutil
import sys
from pathlib import Path

KEEP_DISPATCH = 10


def _stats(results: Path) -> dict[str, int]:
    # Count statuses straight from the allure-results (allure-pytest output); this
    # is independent of the report format, so it survives Allure version changes.
    out = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
    for f in results.glob("*-result.json"):
        try:
            status = json.loads(f.read_text(encoding="utf-8")).get("status")
        except Exception:
            continue
        out["total"] += 1
        if status == "passed":
            out["passed"] += 1
        elif status in ("failed", "broken"):
            out["failed"] += 1
        elif status == "skipped":
            out["skipped"] += 1
    return out


def _render_index(runs: list[dict], repo: str, server: str) -> str:
    rows = []
    for r in sorted(runs, key=lambda x: x["run"], reverse=True):
        fail_cls = ' class="fail"' if r["failed"] else ""
        ref = html.escape(r["ref"])
        tag = ' <span class="badge">release</span>' if r["release"] else ""
        commit_url = f"{server}/{repo}/commit/{r['commit']}"
        rows.append(
            "<tr>"
            f'<td><a href="{html.escape(r["report"])}">#{r["run"]}</a></td>'
            f'<td>{html.escape(r["date"])}</td>'
            f"<td>{ref}{tag}</td>"
            f'<td><a href="{html.escape(commit_url)}"><code>{html.escape(r["short_commit"])}</code></a></td>'
            f'<td>{html.escape(r["trigger"])}</td>'
            f'<td class="pass">{r["passed"]}</td>'
            f'<td{fail_cls}>{r["failed"]}</td>'
            f'<td class="skip">{r["skipped"]}</td>'
            f'<td><a href="{html.escape(r["report"])}">report</a></td>'
            f'<td><a href="{html.escape(r["ci_url"])}">CI run</a></td>'
            "</tr>"
        )
    table = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenGeneral cross-platform test runs</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem auto; max-width: 1000px; color: #1b1f23; }}
  h1 {{ font-size: 1.4rem; }}
  p.sub {{ color: #57606a; margin-top: -0.4rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #eaecef; }}
  th {{ background: #f6f8fa; }}
  tr:hover td {{ background: #f6f8fa; }}
  td.pass {{ color: #1a7f37; }}
  td.skip {{ color: #9a6700; }}
  td.fail {{ color: #cf222e; font-weight: 600; }}
  .badge {{ background: #ddf4ff; color: #0969da; border-radius: 6px; padding: 0 0.4rem; font-size: 0.75rem; }}
  code {{ background: #f6f8fa; padding: 0.1rem 0.3rem; border-radius: 4px; }}
  a {{ color: #0969da; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>OpenGeneral &mdash; cross-platform test runs</h1>
<p class="sub">Click a run to open its full Allure report. Newest first.</p>
<table>
<thead><tr>
  <th>Run</th><th>Date (UTC)</th><th>Ref</th><th>Commit</th><th>Trigger</th>
  <th>Passed</th><th>Failed</th><th>Skipped</th><th>Report</th><th>CI</th>
</tr></thead>
<tbody>
{table}
</tbody>
</table>
</body>
</html>
"""


def main() -> int:
    old = Path(sys.argv[1] if len(sys.argv) > 1 else "gh-pages")
    new_report = Path(sys.argv[2] if len(sys.argv) > 2 else "report")
    out = Path(sys.argv[3] if len(sys.argv) > 3 else "site")
    results = Path(sys.argv[4] if len(sys.argv) > 4 else "allure-results")

    run = int(os.environ["GITHUB_RUN_NUMBER"])
    ref = os.environ.get("GITHUB_REF_NAME", "")
    trigger = os.environ.get("GITHUB_EVENT_NAME", "")
    sha = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    is_release = trigger == "push" and ref.startswith("v")

    stats = _stats(results)
    record = {
        "run": run,
        "run_id": run_id,
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "ref": ref,
        "commit": sha,
        "short_commit": sha[:7],
        "trigger": trigger,
        "release": is_release,
        "report": f"runs/{run}/",
        "ci_url": f"{server}/{repo}/actions/runs/{run_id}",
        **stats,
    }

    ledger = old / "runs.json"
    runs: list[dict] = []
    if ledger.exists():
        runs = json.loads(ledger.read_text(encoding="utf-8"))
    runs = [r for r in runs if r.get("run") != run]  # idempotent re-run
    runs.append(record)

    ordered = sorted(runs, key=lambda r: r["run"])
    releases = [r for r in ordered if r["release"]]
    dispatch = [r for r in ordered if not r["release"]][-KEEP_DISPATCH:]
    keep_numbers = {r["run"] for r in releases} | {r["run"] for r in dispatch}
    kept = [r for r in ordered if r["run"] in keep_numbers]

    (out / "runs").mkdir(parents=True, exist_ok=True)
    for r in kept:
        n = r["run"]
        if n == run:
            continue
        src = old / "runs" / str(n)
        if src.exists():
            shutil.copytree(src, out / "runs" / str(n), dirs_exist_ok=True)
    shutil.copytree(new_report, out / "runs" / str(run), dirs_exist_ok=True)

    (out / "runs.json").write_text(json.dumps(kept, indent=2), encoding="utf-8")
    (out / "index.html").write_text(_render_index(kept, repo, server), encoding="utf-8")

    print(f"Runs kept: {sorted(keep_numbers)} (releases={len(releases)}, dispatch<= {KEEP_DISPATCH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
