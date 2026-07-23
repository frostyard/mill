#!/usr/bin/env python3
"""Deterministic state machine for the mill workflow (workflows/mill.yaml).

Every subcommand prints a single JSON object on stdout; conductor routes on
the parsed fields. All counters, gates, and git operations live here so the
LLM steps never control loop termination or touch version control.

State lives in .mill/ inside the worktree the mill runs in:
  spec.md          the specification text
  plan.json        planner output: {"chunks": [{id,title,description,files,acceptance}]}
  plan.md          human-readable plan
  progress.json    {base, branch, title, source, plan_rounds, chunk, attempts,
                    review_rounds}
  objections.json  most recent reviewer objections for the current chunk
  review.sha256    staged-diff hash taken before a review (no-touch check)
  final_report.md  final review verdicts + compliance matrix
"""
import json
import pathlib
import re
import subprocess
import sys
import tomllib

MILL = pathlib.Path(".mill")
PROGRESS = MILL / "progress.json"
CONFIG = pathlib.Path(".mill.toml")

GATE_LOG_TAIL = 4000
DEFAULT_LIMITS = {"plan_rounds": 3, "gate_attempts": 3, "review_rounds": 2}


def load_config():
    """Read and validate the repo's .mill.toml; every repo-specific value
    lives there. Raises with a friendly message on any problem."""
    if not CONFIG.is_file():
        raise RuntimeError(
            ".mill.toml not found — this repo is not set up for the mill")
    cfg = tomllib.loads(CONFIG.read_text())
    def need(section, key, typ):
        val = cfg.get(section, {}).get(key)
        if not isinstance(val, typ) or not val:
            raise RuntimeError(f".mill.toml missing/invalid [{section}] {key}")
        return val
    limits = dict(DEFAULT_LIMITS)
    for key, val in cfg.get("limits", {}).items():
        if key not in DEFAULT_LIMITS or not isinstance(val, int) or not 1 <= val <= 20:
            raise RuntimeError(f".mill.toml [limits] {key} must be an int 1-20 "
                               f"named one of {sorted(DEFAULT_LIMITS)}")
        limits[key] = val
    return {
        "gates_chunk": need("gates", "chunk", list),
        "gates_deep": need("gates", "deep", list),
        "context_docs": need("context", "docs", list),
        "skills_dir": need("context", "skills_dir", str),
        "security_invariants": need("review", "security_invariants", str),
        "harvest_allowlist": need("harvest", "allowlist", list),
        "limits": limits,
    }


def journal(event, **fields):
    """Append a friction/progress event for the harvest step to distill."""
    MILL.mkdir(exist_ok=True)
    with (MILL / "journal.jsonl").open("a") as f:
        f.write(json.dumps({"event": event, **fields}) + "\n")


def sh(*args, timeout=900, check=False):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {p.stderr.strip()[:500]}")
    return p


def out(**kw):
    print(json.dumps(kw))
    sys.exit(0)


def load_progress():
    return json.loads(PROGRESS.read_text())


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, indent=2))


def tree_dirty_outside_mill():
    """Paths changed in the working tree, ignoring .mill/ (which is self-ignored)."""
    p = sh("git", "status", "--porcelain")
    return [line for line in p.stdout.splitlines() if line.strip()]


def staged_hash():
    p = sh("git", "diff", "--cached")
    import hashlib
    return hashlib.sha256(p.stdout.encode()).hexdigest()


def parse_review(text, _depth=0):
    """Normalize a reviewer's free-form reply into (verdict, payload).

    Reviewer output shapes must never be able to kill a run (conductor
    treats schema ValidationError as fatal), so reviewers emit plain text
    ending in a JSON block and this function does tolerant extraction:
    full-JSON reply, fenced ```json block (last one wins), any {...} span,
    dict-wrapped verdicts, then keyword fallback. It also unwraps conductor's
    raw-output envelopes — standalone agents expose text under 'result',
    parallel-group members under 'response' — by recursing into the wrapped
    text, so callers can pass either the raw text or the whole output object.
    Unparseable replies are rejection-biased ("unparseable" — callers treat
    it as revise/fail).
    """
    text = text or ""
    if not isinstance(text, str):
        text = json.dumps(text)
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates.extend(reversed(fenced))
    candidates.append(text.strip())
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            d = json.loads(c)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        # Unwrap a conductor output envelope by recursing into its text.
        if _depth < 3:
            for wrap in ("response", "result", "content", "output"):
                inner = d.get(wrap)
                if isinstance(inner, str) and inner.strip():
                    v2, p2 = parse_review(inner, _depth + 1)
                    if v2 != "unparseable":
                        return v2, p2
        v = d.get("verdict")
        if isinstance(v, dict):
            v = v.get("verdict") or v.get("decision") or v.get("value")
        if isinstance(v, str) and v.strip():
            return v.strip().lower(), d
    low = text.lower()
    for kw in ("approve", "revise", "pass", "fail", "sound", "needs_clarification"):
        if re.search(rf"verdict\W{{0,20}}{kw}", low):
            return kw, {}
    return "unparseable", {}


# ---------------------------------------------------------------- subcommands

def cmd_init(source, base_branch="main"):
    """source: an issue number or a path to a spec file.
    base_branch: the branch the run was launched from (for the pre-ship rebase)."""
    try:
        cfg = load_config()
    except RuntimeError as e:
        out(ok=False, error=str(e))
    MILL.mkdir(exist_ok=True)
    (MILL / ".gitignore").write_text("*\n")  # .mill never enters version control
    # Resolved config for agents to read (prompts reference .mill/config.json).
    (MILL / "config.json").write_text(json.dumps(cfg, indent=2))
    if re.fullmatch(r"\d+", source):
        p = sh("gh", "issue", "view", source, "--json", "title,body", timeout=60)
        if p.returncode != 0:
            out(ok=False, error=f"gh issue view {source}: {p.stderr.strip()[:300]}")
        data = json.loads(p.stdout)
        title, spec = data["title"], data["body"]
        label = f"issue #{source}"
    else:
        path = pathlib.Path(source)
        if not path.is_file():
            out(ok=False, error=f"spec file not found: {source}")
        spec = path.read_text()
        title = spec.strip().splitlines()[0].lstrip("# ").strip()[:80]
        label = source
    if not spec.strip():
        out(ok=False, error=f"empty spec from {label}")
    (MILL / "spec.md").write_text(spec)
    # Resume: an existing plan + progress means committed chunks are on the
    # branch. Preserve the cursor; the workflow skips straight back to the
    # chunk loop. (--fresh discards the worktree for a true restart.)
    if PROGRESS.is_file() and (MILL / "plan.json").is_file():
        prog = load_progress()
        prog.update(attempts=0, review_rounds=0)
        prog.pop("fail_reason", None)
        prog.setdefault("base_branch", base_branch)  # backfill for older runs
        save_progress(prog)
        journal("resumed", chunk=prog["chunk"])
        out(ok=True, resuming=True, title=title, source=label,
            chunk=prog["chunk"])
    base = sh("git", "rev-parse", "HEAD", check=True).stdout.strip()
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD", check=True).stdout.strip()
    save_progress({
        "base": base, "branch": branch, "base_branch": base_branch,
        "title": title, "source": label,
        "plan_rounds": 0, "chunk": 0, "attempts": 0, "review_rounds": 0,
    })
    out(ok=True, resuming=False, title=title, source=label,
        spec_chars=len(spec))


def run_gates(deep=False):
    """Run the repo-configured quality gates; return (ok, log_tail).

    Gate commands come from .mill.toml and are repo-committed, so they carry
    the same trust as the Makefile they invoke.
    """
    cfg = load_config()
    for cmd in cfg["gates_deep"] if deep else cfg["gates_chunk"]:
        p = sh("bash", "-c", cmd, timeout=3600 if deep else 900)
        if p.returncode != 0:
            log = (p.stdout + "\n" + p.stderr)[-GATE_LOG_TAIL:]
            return False, f"$ {cmd[:120]}\n{log}"
    return True, ""


def cmd_baseline():
    ok, log = run_gates()
    if not ok:
        out(gate="fail", log=log)
    out(gate="pass")


def cmd_check_plan():
    prog = load_progress()
    dirty = tree_dirty_outside_mill()
    if dirty:
        sh("git", "checkout", "--", ".")
        sh("git", "clean", "-fd")
        out(ok=False, error=f"planner modified the tree (reverted): {dirty[:10]}")
    try:
        plan = json.loads((MILL / "plan.json").read_text())
        chunks = plan["chunks"]
        assert isinstance(chunks, list) and chunks, "chunks must be a non-empty list"
        for i, c in enumerate(chunks):
            for field in ("id", "title", "description", "acceptance"):
                assert c.get(field), f"chunk {i} missing '{field}'"
    except Exception as e:  # noqa: BLE001 - any malformed plan routes back to the planner
        out(ok=False, error=f"plan.json invalid: {e}")
    if not (MILL / "plan.md").is_file():
        out(ok=False, error="plan.md was not written")
    out(ok=True, num_chunks=len(chunks))


def plan_trajectory():
    """Summarize plan-review rounds from the journal: counts, repeats, and a
    heuristic diagnosis the escalation gate can show a human."""
    rounds = []
    path = MILL / "journal.jsonl"
    if path.is_file():
        for line in path.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "plan_revise":
                rounds.append([str(o.get("section", ""))[:40].lower()
                               for o in e.get("objections", [])])
    if not rounds:
        return "no revision rounds recorded"
    counts = [len(r) for r in rounds]
    overlaps = []
    for prev, cur in zip(rounds, rounds[1:]):
        shared = sum(1 for s_ in cur if any(s_[:25] and s_[:25] in p_ for p_ in prev))
        overlaps.append(shared / len(cur) if cur else 0)
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
    if avg_overlap > 0.6:
        diag = ("objections REPEAT across rounds — likely reviewer/planner "
                "disagreement on one point; read the objections and decide, "
                "or fix the spec on that point")
    elif counts[-1] <= 2 and counts[-1] <= counts[0]:
        diag = ("objections are CONVERGING — the spec likely has one or two "
                "specific defects; fix those in the spec and rerun")
    else:
        diag = ("objections keep finding NEW sections — the spec is likely "
                "too large to converge; consider decomposing into phases")
    return f"objections per round: {' -> '.join(map(str, counts))}; {diag}"


def cmd_spec_verdict(review_text):
    """Gate after the spec reviewer: sound -> plan, anything else -> human."""
    verdict, payload = parse_review(review_text)
    dirty = tree_dirty_outside_mill()
    if dirty:
        sh("git", "checkout", "--", ".")
        sh("git", "clean", "-fd")
    findings = payload.get("findings", [])
    est = payload.get("estimated_chunks", 0)
    (MILL / "spec_findings.json").write_text(json.dumps(
        {"verdict": verdict, "estimated_chunks": est, "findings": findings},
        indent=2))
    journal("spec_review", verdict=verdict, findings=findings,
            estimated_chunks=est)
    if verdict == "sound" and not dirty:
        out(action="plan", findings_count=len(findings), estimated_chunks=est)
    out(action="clarify", findings_count=len(findings), estimated_chunks=est,
        summary="; ".join(str(f.get("detail", ""))[:100] for f in findings[:4]))


def cmd_plan_verdict(review_text):
    verdict, payload = parse_review(review_text)
    objections_json = json.dumps(payload.get("objections", []))
    prog = load_progress()
    dirty = tree_dirty_outside_mill()
    if dirty:
        sh("git", "checkout", "--", ".")
        sh("git", "clean", "-fd")
        out(action="abort", error=f"plan reviewer modified the tree (reverted): {dirty[:10]}")
    if verdict == "approve":
        (MILL / "objections.json").unlink(missing_ok=True)
        out(action="proceed", rounds=prog["plan_rounds"])
    prog["plan_rounds"] += 1
    save_progress(prog)
    journal("plan_revise", rounds=prog["plan_rounds"],
            objections=json.loads(objections_json))
    (MILL / "objections.json").write_text(objections_json)
    max_rounds = load_config()["limits"]["plan_rounds"]
    if prog["plan_rounds"] >= max_rounds:
        prog["fail_reason"] = (f"plan not approved after {max_rounds} rounds — "
                               "spec likely needs human clarification")
        save_progress(prog)
        out(action="escalate", error=prog["fail_reason"],
            trajectory=plan_trajectory())
    out(action="revise", rounds=prog["plan_rounds"])


def cmd_select():
    prog = load_progress()
    chunks = json.loads((MILL / "plan.json").read_text())["chunks"]
    i = prog["chunk"]
    if i >= len(chunks):
        out(done=True, total=len(chunks))
    objections = None
    if (MILL / "objections.json").is_file():
        objections = json.loads((MILL / "objections.json").read_text())
    out(done=False, index=i, total=len(chunks), chunk=chunks[i],
        objections=objections)


def cmd_impl_gate():
    prog = load_progress()
    ok, log = run_gates()
    if ok:
        prog["attempts"] = 0
        save_progress(prog)
        out(gate="pass")
    prog["attempts"] += 1
    give_up = prog["attempts"] >= load_config()["limits"]["gate_attempts"]
    if give_up:
        prog["fail_reason"] = (f"chunk {prog['chunk']} could not pass quality "
                               f"gates after {prog['attempts']} attempts")
    save_progress(prog)
    journal("gate_fail", chunk=prog["chunk"], attempt=prog["attempts"],
            log=log[-1500:])
    out(gate="fail", attempts=prog["attempts"], give_up=give_up, log=log)


def cmd_pre_review():
    sh("git", "add", "-A", check=True)
    (MILL / "review.sha256").write_text(staged_hash())
    stat = sh("git", "diff", "--cached", "--stat").stdout[-2000:]
    if not stat.strip():
        out(empty=True, stat="")
    out(empty=False, stat=stat)


def cmd_review_gate(review_text):
    verdict, payload = parse_review(review_text)
    objections_json = json.dumps(payload.get("objections", []))
    prog = load_progress()
    unstaged = sh("git", "diff").stdout
    touched = bool(unstaged.strip()) or staged_hash() != (MILL / "review.sha256").read_text()
    if touched:
        sh("git", "checkout", "--", ".")
        out(action="abort", error="chunk reviewer modified the tree (reverted)")
    if verdict == "approve":
        (MILL / "objections.json").unlink(missing_ok=True)
        out(action="commit")
    prog["review_rounds"] += 1
    save_progress(prog)
    journal("chunk_revise", chunk=prog["chunk"], rounds=prog["review_rounds"],
            objections=json.loads(objections_json))
    (MILL / "objections.json").write_text(objections_json)
    max_rounds = load_config()["limits"]["review_rounds"]
    if prog["review_rounds"] > max_rounds:
        prog["fail_reason"] = (f"chunk {prog['chunk']} not approved after "
                               f"{max_rounds} review rounds")
        save_progress(prog)
        out(action="abort", error=prog["fail_reason"])
    out(action="revise", rounds=prog["review_rounds"])


def cmd_commit_chunk():
    prog = load_progress()
    chunks = json.loads((MILL / "plan.json").read_text())["chunks"]
    chunk = chunks[prog["chunk"]]
    msg = f"mill: chunk {prog['chunk'] + 1}/{len(chunks)} — {chunk['title']}\n\nCo-Authored-By: mill <noreply@frostyard>"
    p = sh("git", "commit", "-m", msg)
    if p.returncode != 0:
        out(ok=False, error=f"git commit failed: {p.stderr.strip()[:300]}")
    sha = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    journal("chunk_done", chunk=prog["chunk"], sha=sha, title=chunk["title"])
    prog.update(chunk=prog["chunk"] + 1, attempts=0, review_rounds=0)
    save_progress(prog)
    (MILL / "objections.json").unlink(missing_ok=True)
    out(ok=True, committed=sha, next=prog["chunk"], total=len(chunks))


def cmd_final_gate(sec_text, comp_text):
    dirty = tree_dirty_outside_mill()
    if dirty:
        sh("git", "checkout", "--", ".")
        sh("git", "clean", "-fd")
        out(action="abort", error=f"final reviewer modified the tree (reverted): {dirty[:10]}")
    sec_v, sec = parse_review(sec_text)
    comp_v, comp = parse_review(comp_text)
    report = ["# Mill final review\n",
              f"## Security review — verdict: {sec_v}\n",
              "```json", json.dumps(sec or {"raw": sec_text[-2000:]}, indent=2), "```\n",
              f"## Spec compliance review — verdict: {comp_v}\n",
              "```json", json.dumps(comp or {"raw": comp_text[-2000:]}, indent=2), "```\n"]
    (MILL / "final_report.md").write_text("\n".join(report))
    ok = sec_v in ("pass", "approve") and comp_v in ("pass", "approve")
    out(action="ship" if ok else "abort", sec_verdict=sec_v, comp_verdict=comp_v,
        error="" if ok else "final review failed — see .mill/final_report.md")


def cmd_harvest_gate():
    """Enforce the harvest path allowlist, then commit any surviving lessons."""
    allowed = load_config()["harvest_allowlist"]
    reverted = []
    for line in tree_dirty_outside_mill():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if not any(path == a or path.startswith(a) for a in allowed):
            reverted.append(path)
            sh("git", "checkout", "--", path)
            sh("git", "clean", "-fd", "--", path)
    fail_reason = load_progress().get("fail_reason", "")
    changed = [line[3:].strip() for line in tree_dirty_outside_mill()]
    if not changed:
        out(committed=False, files=[], reverted=reverted,
            fail_reason=fail_reason)
    sh("git", "add", "-A", check=True)
    p = sh("git", "commit", "-m",
           "mill: harvest — agent skills learned during this run\n\n"
           "Co-Authored-By: mill <noreply@frostyard>")
    if p.returncode != 0:
        out(committed=False, files=[], reverted=reverted,
            fail_reason=fail_reason,
            error=f"commit failed: {p.stderr.strip()[:300]}")
    out(committed=True, files=changed, reverted=reverted,
        fail_reason=fail_reason)


def cmd_rebase():
    """Rebase the run branch onto the latest base branch before the deep gate,
    so the gate validates the actual integrated result. A long run's base
    moves under it; this keeps the eventual PR current. Conflicts are never
    auto-resolved — the rebase is aborted and the run stops for a human."""
    prog = load_progress()
    base_branch = prog.get("base_branch", "main")
    dirty = tree_dirty_outside_mill()
    if dirty:
        out(action="abort", error=f"tree dirty before rebase (unexpected): {dirty[:5]}")
    f = sh("git", "fetch", "origin", base_branch, timeout=120)
    if f.returncode != 0:
        # Offline / no remote — proceed on the local base rather than block.
        out(action="skip", note=f"fetch origin {base_branch} failed; shipping without rebase")
    target = f"origin/{base_branch}"
    behind = sh("git", "rev-list", "--count", f"HEAD..{target}").stdout.strip()
    if behind in ("", "0"):
        out(action="clean", rebased=False, note="already up to date with base")
    r = sh("git", "rebase", target, timeout=300)
    if r.returncode != 0:
        sh("git", "rebase", "--abort")
        out(action="conflict", base_branch=base_branch, behind=behind,
            error=(f"base {base_branch} advanced {behind} commit(s) and the rebase "
                   f"conflicts. Resolve manually in the worktree:\n"
                   f"  git rebase {target}   # fix conflicts, git rebase --continue\n"
                   f"then re-run the mill to finish (deep gate + ship)."))
    head = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    journal("rebased", onto=target, behind=int(behind), head=head)
    out(action="clean", rebased=True, behind=int(behind), onto=target)


def cmd_deep_gate(deep):
    ok, log = run_gates(deep=(deep == "true"))
    if not ok:
        out(gate="fail", log=log)
    out(gate="pass")


def cmd_publish():
    prog = load_progress()
    p = sh("git", "push", "-u", "origin", prog["branch"], timeout=120)
    if p.returncode != 0:
        out(ok=False, error=f"git push failed: {p.stderr.strip()[:300]}")
    body = MILL / "pr_body.md"
    parts = [f"Implements {prog['source']} via the mill workflow.\n",
             (MILL / "plan.md").read_text(), "\n---\n",
             (MILL / "final_report.md").read_text(),
             "\n🤖 Generated with the mill (workflows/mill.yaml)"]
    if re.fullmatch(r"issue #\d+", prog["source"]):
        parts.insert(1, f"Closes #{prog['source'].split('#')[1]}\n")
    body.write_text("\n".join(parts))
    p = sh("gh", "pr", "create", "--title", f"mill: {prog['title']}",
           "--body-file", str(body), timeout=120)
    if p.returncode != 0:
        out(ok=False, error=f"gh pr create failed: {p.stderr.strip()[:300]}")
    out(ok=True, url=p.stdout.strip().splitlines()[-1])


def main():
    cmds = {
        "init": (cmd_init, 2),
        "rebase": (cmd_rebase, 0),
        "baseline": (cmd_baseline, 0),
        "check-plan": (cmd_check_plan, 0),
        "spec-verdict": (cmd_spec_verdict, 1),
        "plan-verdict": (cmd_plan_verdict, 1),
        "select": (cmd_select, 0),
        "impl-gate": (cmd_impl_gate, 0),
        "pre-review": (cmd_pre_review, 0),
        "review-gate": (cmd_review_gate, 1),
        "commit-chunk": (cmd_commit_chunk, 0),
        "final-gate": (cmd_final_gate, 2),
        "harvest-gate": (cmd_harvest_gate, 0),
        "deep-gate": (cmd_deep_gate, 1),
        "publish": (cmd_publish, 0),
    }
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        out(ok=False, error=f"usage: mill_state.py <{'|'.join(cmds)}> [args]")
    fn, nargs = cmds[sys.argv[1]]
    # Pass up to nargs positional args; optional trailing ones (with function
    # defaults, e.g. init's base_branch) may be omitted. Wrong arity surfaces
    # as a TypeError caught by the top-level handler.
    args = sys.argv[2:2 + nargs]
    fn(*args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - routing needs JSON even on bugs here
        print(json.dumps({"ok": False, "gate": "fail", "action": "abort",
                          "error": f"mill_state.py crashed: {e!r}"}))
        sys.exit(0)
