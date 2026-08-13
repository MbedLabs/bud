"""Does the UI suite actually catch a regression, or only pass?

Coverage says a line ran, not that anything checked what it did. This breaks
the source in ways a real change might - loosening a guard, reading the wrong
field, dropping a reset - and reports which breakages the suite notices. A
SURVIVED entry is a test that is watching nothing.

Run from ui/:  python3 scripts/mutation-check.py
Each mutation is applied on its own, the whole suite is run, and the file is
put back afterwards whether or not the run succeeded.
"""

import pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (label, file, old, new) - each is a plausible regression, not a typo.
MUTANTS = [
 ("Auth: keep the access token in localStorage instead of sessionStorage",
  "src/lib/tokenStorage.ts",
  "    return window.sessionStorage",
  "    return window.localStorage"),

 ("Auth: retry a failed auth call through the refresh loop",
  "src/api/client.ts",
  "      url.includes('/auth/refresh') || url.includes('/auth/login') || url.includes('/auth/logout')",
  "      false"),

 ("Auth: refresh once per request instead of sharing one in flight",
  "src/api/client.ts",
  "      if (!refreshPromise) {",
  "      if (true) {"),

 ("Auth: retry a 401 forever instead of once",
  "src/api/client.ts",
  "    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {",
  "    if (error.response?.status === 401 && original && !isAuthCall) {"),

 ("Results: 'failed only' keeps the passing assertions too",
  "src/lib/testRunResultFilters.ts",
  "    return assertions.filter((assertion) => assertion.passed === false)",
  "    return assertions"),

 ("Results: 'failed only' and 'failed' stop being exclusive",
  "src/lib/testRunResultFilters.ts",
  "  if (key === 'failedOnly' && next.failedOnly) {\n    next.failed = false\n  }",
  "  if (false) {\n    next.failed = false\n  }"),

 ("Results: no filter selected hides every row instead of showing all",
  "src/lib/testRunResultFilters.ts",
  "  if (!hasActiveOutcomeFilters(filters)) return true",
  "  if (!hasActiveOutcomeFilters(filters)) return false"),

 ("Results: a passed filter also matches failing cases",
  "src/lib/testRunResultFilters.ts",
  "  if (filters.passed && isPassedCase) return true",
  "  if (filters.passed) return true"),

 ("Run list: search stops matching the runner account",
  "src/pages/TestRuns.tsx",
  "      (run.runner_account && run.runner_account.toLowerCase().includes(q))",
  "      false"),

 ("Run list: search stops matching the test case list",
  "src/pages/TestRuns.tsx",
  "      run.test_case_list.toLowerCase().includes(q) ||",
  "      false ||"),

 ("Run list: the location filter matches every station",
  "src/pages/TestRuns.tsx",
  "          .filter((station) => station.location === locationFilter)",
  "          .filter(() => true)"),

 ("Run list: the location filter takes only the first bench at that location",
  "src/pages/TestRuns.tsx",
  "          .filter((station) => station.location === locationFilter)\n          .map((station) => station.account)",
  "          .filter((station) => station.location === locationFilter)\n          .slice(0, 1)\n          .map((station) => station.account)"),

 ("Run list: a location with several benches is listed once per bench",
  "src/pages/TestRuns.tsx",
  "    return Array.from(locations).sort((a, b) => a.localeCompare(b))",
  "    return stations.map((s) => s.location).filter(Boolean).sort((a, b) => a.localeCompare(b))"),

 ("Run list: clearing the filters leaves the search in place",
  "src/pages/TestRuns.tsx",
  "    setSearch('')\n    setStatusFilter('')",
  "    setStatusFilter('')"),

 ("Users: delete without confirming",
  "src/pages/Users.tsx",
  "if (pendingDeleteUserId !== u.id && confirm('Delete this user?')) {",
  "if (pendingDeleteUserId !== u.id) {"),

 ("Settings: revoke the sync credential without confirming",
  "src/pages/Settings.tsx",
  "if (!window.confirm('Remove the Bloom result-sync credential from Bud?')) return",
  "if (false) return"),

 ("One-time token: accept a token from the query string too",
  "src/hooks/useOneTimeToken.ts",
  "return new URLSearchParams((loc.hash || '').replace(/^#/, '')).get('token') || ''",
  "return new URLSearchParams((loc.hash || '').replace(/^#/, '')).get('token') || new URLSearchParams(loc.search || '').get('token') || ''"),

 ("One-time token: leave the token in the URL after reading it",
  "src/hooks/useOneTimeToken.ts",
  "    if (loc && loc.hash) {",
  "    if (false) {"),
]

results = []


def restore_any_leftovers() -> None:
    """Put back anything a previous run was killed in the middle of.

    The per-mutant `finally` cannot help against SIGKILL, and a mutated file
    left in the tree is worse than useless - it is a deliberately broken guard
    that looks like ordinary uncommitted work and can be committed by mistake.
    So the original is written to a sidecar *before* the source is touched, and
    the next run puts it back before doing anything else.
    """
    for backup in sorted(ROOT.glob('**/*.mutation-backup')):
        target = backup.with_suffix('')
        target.write_text(backup.read_text())
        backup.unlink()
        print(f"restored {target.relative_to(ROOT)} from an interrupted run", flush=True)


restore_any_leftovers()

for label, rel, old, new in MUTANTS:
    path = ROOT / rel
    original = path.read_text()
    if old not in original:
        results.append((label, rel, "NOT-APPLIED"))
        print(f"{'NOT-APPLIED':10} {label}", flush=True)
        continue
    backup = path.with_name(path.name + '.mutation-backup')
    backup.write_text(original)
    path.write_text(original.replace(old, new, 1))
    try:
        proc = subprocess.run(
            [str(ROOT / 'node_modules/.bin/vitest'), 'run', '--reporter=dot'],
            cwd=ROOT, capture_output=True, text=True, timeout=900)
        results.append((label, rel, "CAUGHT" if proc.returncode != 0 else "SURVIVED"))
    finally:
        path.write_text(original)
        backup.unlink(missing_ok=True)
    print(f"{results[-1][2]:10} {label}", flush=True)

print()
caught = sum(1 for r in results if r[2] == 'CAUGHT')
total = sum(1 for r in results if r[2] != 'NOT-APPLIED')
print(f"=== {caught}/{total} caught ===")
for label, rel, verdict in results:
    if verdict != 'CAUGHT':
        print(f"  {verdict}: {label}  [{rel}]")
