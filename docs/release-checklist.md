# Production Release Checklist — Phase 0 Engineering Review Harness

Run through this before announcing a deployment (or an update) to reviewers.
Everything here is verifiable from the command line; nothing depends on the
server internals. Check each item.

Target: **https://buyafraction.com** (`192.168.160.98`).

---

## Pre-flight (build & correctness)

- [ ] **Package installs cleanly**
  ```bash
  /opt/sanuvia/.venv/bin/pip install /opt/sanuvia
  ```
  (Docker path only, if used: `docker compose build` succeeds.)

- [ ] **Tests pass** — full suite green.
  ```bash
  cd /opt/sanuvia && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q
  # expect: all passed
  ```
  > Dev-only step; the production venv does not need pytest. Run on a build/CI
  > host or before deploying.

- [ ] **Exit Test passes** — the Phase 0 determinism proof.
  ```bash
  sudo -u sanuvia /opt/sanuvia/.venv/bin/python -m sanuvia.exit_test
  # expect: RESULT: PASS — Phase 0 proof holds   (exit code 0)
  ```

- [ ] **Type checks pass** (build/CI host).
  ```bash
  .venv/bin/python -m mypy
  # expect: Success: no issues found
  ```

- [ ] **Subject/space isolation regressions pass** (Finding 1).
  ```bash
  .venv/bin/pytest -q tests/test_space_isolation.py tests/adapters/test_sqlite_migration.py
  ```

- [ ] **SQLite reset/rerun regression passes** (Finding 2).
  ```bash
  .venv/bin/pytest -q tests/adapters/test_sqlite_reset_rerun.py
  ```

- [ ] **Clean-host deployment smoke passes** (Finding 3).
  ```bash
  .venv/bin/pytest -q tests/test_clean_host_smoke.py
  bash scripts/smoke.sh          # real end-to-end clean-host flow
  ```

- [ ] **CI is green** on the commit (`.github/workflows/ci.yml`: suite · mypy ·
  exit test · isolation · reset/rerun · deployment smoke).

---

## Data & functionality (against the running service)

Use the local port (bypasses nginx) or the public URL — both must work.

- [ ] **Health endpoint working**
  ```bash
  curl -s http://127.0.0.1:8000/health
  # {"status":"ok","version":"phase0","backend":"sqlite"}
  curl -s https://buyafraction.com/health      # same, through nginx
  ```

- [ ] **Review datasets available** — all 12 (`D1…D12`) present.
  ```bash
  curl -s http://127.0.0.1:8000/api/samples \
    | grep -o '"id": *"dataset-[^"]*"' | sort -u | wc -l   # expect 12
  ```

- [ ] **SQLite persistence verified** — state/definitions survive a restart.
  ```bash
  sudo /opt/sanuvia/scripts/restart.sh
  ls -1 /var/lib/sanuvia/*.db /var/lib/sanuvia/testcases/  # data still present
  ```

- [ ] **Review package export verified** — the one-click `.zip` contains all six
  artifacts.
  ```bash
  curl -s -XPOST http://127.0.0.1:8000/api/samples/load -d '{"sample_id":"dataset-competing-resolve"}' >/dev/null
  curl -s -XPOST http://127.0.0.1:8000/api/run-all >/dev/null
  curl -s http://127.0.0.1:8000/api/export/package \
    | python3 -c "import sys,json,base64,io,zipfile;z=zipfile.ZipFile(io.BytesIO(base64.b64decode(json.load(sys.stdin)['zip_base64'])));print(sorted(z.namelist()))"
  # expect: ['exit_test.json','reasoning_graph.dot','reasoning_graph.md','reasoning_trace.md','review-report.md','test_case.json']
  ```

- [ ] **Trace rendering verified**
  ```bash
  curl -s http://127.0.0.1:8000/api/trace | python3 -c "import sys,json;print(len(json.load(sys.stdin)['markdown'])>0)"  # True
  ```

- [ ] **Graph rendering verified**
  ```bash
  curl -s http://127.0.0.1:8000/api/graph | python3 -c "import sys,json;print('flowchart' in json.load(sys.stdin).get('mermaid',''))"  # True
  ```

- [ ] **Review verdict verified** — final engineering result reads PASS.
  ```bash
  curl -s http://127.0.0.1:8000/api/review-result
  # overall:PASS, expected_vs_actual:100%, reasoning_correct:YES, deterministic:YES,
  # exit_test:PASS, ready_for_phase_1:YES
  ```

---

## Operations

- [ ] **Service is enabled at boot** — `systemctl is-enabled sanuvia` → `enabled`.
- [ ] **Restart policy active** — unit has `Restart=on-failure`.
- [ ] **Backup runs** — `sudo /opt/sanuvia/scripts/backup.sh` writes an archive.
- [ ] **Restore rehearsed at least once** on a non-critical snapshot.
- [ ] **Logs reachable** — `/opt/sanuvia/scripts/logs.sh -n 20` shows startup line.
- [ ] **HTTPS valid** — browser shows a valid certificate for `buyafraction.com`
  (or the internal-CA path is documented for reviewers).
- [ ] **App not directly exposed** — `SANUVIA_HOST=127.0.0.1`; only nginx is public.

---

## Determinism sign-off

- [ ] Running the same Review Dataset twice yields **byte-identical** trace,
  graph, report, and review-package artifacts.
- [ ] `PYTHONHASHSEED=0` set in both the systemd unit and `/etc/sanuvia/sanuvia.env`.
- [ ] No change to the reasoning engine, domain model, or Application API in this
  release (deployment/adapter layer only).

---

## Acceptance — reviewer walkthrough (no server access)

A reviewer, using only **https://buyafraction.com**, can:

- [ ] Load a Review Dataset
- [ ] Run the full sequence
- [ ] Inspect **Expected vs Actual**
- [ ] Read the **Automatic Reasoning Summary**
- [ ] Open **Explain Why**
- [ ] Open the **Reasoning Trace**
- [ ] Open the **Reasoning Lineage Graph**
- [ ] Read the **Final Engineering Verdict**
- [ ] Download the **Complete Review Package**
- [ ] Run the **Exit Test**

- [ ] **Ready for Lillian / Felix review** ✅
