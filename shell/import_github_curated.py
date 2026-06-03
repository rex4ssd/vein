#!/usr/bin/env python3
"""
import_github_curated.py — Curated lore extracted from the repos in
docs/Ref_resources/github_260602.md.

WHY THIS instead of `vein fetch`:
  `vein fetch` / `vein study` only summarise a repo's README into shallow
  blurbs ("Click is a Python library...") — exactly the noise pruned on
  2026-06-02. Rex's vision (high-end coding style / macOS GUI behaviour /
  when to close a window / when an exception needs extra handling /
  validation scripts) needs SPECIFIC, actionable patterns, not README text.

  These entries are hand-curated from well-known, stable patterns of each
  repo, mapped to Rex's vision categories. volatility=external-fact so recall
  flags them for re-validation after ~6 months (libraries evolve).

  This is the *template* for ingesting github_260602: one targeted extraction
  per repo into the right category, curated — not auto-fetched.

Run inside venv:
  cd /Users/lion/Documents/vein && python3 shell/import_github_curated.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

VEIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VEIN_ROOT / "src"))

from vein.core.store import VeinStore   # noqa: E402
from vein.core.models import Entry      # noqa: E402

SOURCE = "github_260602:curated"
VOL = "external-fact"

# Each: (type, title, tags, body)
ENTRIES: list[tuple[str, str, list[str], str]] = [

    # ── high-end coding style + validation ───────────────────────────────
    ("reference",
     "SwiftLint — lint as a CI/build gate (high-end Swift style)",
     ["swift", "coding-style", "validation", "ci", "source:realm/SwiftLint", "ref:github_260602"],
     "**Summary:** SwiftLint enforces Swift style/conventions via `.swiftlint.yml`. "
     "Key dial: `opt_in_rules` (off by default — turn on the strict ones you want, e.g. "
     "`force_unwrapping`, `empty_count`, `closure_spacing`, `first_where`, `contains_over_filter_count`). "
     "`disabled_rules` to silence noise; `analyzer_rules` (e.g. `unused_declaration`) need "
     "`swiftlint analyze` + compiler args.\n\n"
     "**Pattern (maps to Lode's `validate_lode.py`):** run it as a Run Script build phase "
     "AND in CI — fail the build on violations so style is mechanically enforced, not reviewed by eye. "
     "`--strict` promotes warnings to errors for the CI gate.\n\n"
     "**Why it matters:** this is the canonical 'validation script' shape for Swift — "
     "the same invariant-gate idea Lode uses for Rust/TS."),

    ("reference",
     "SwiftLint custom rules — regex-based project invariants",
     ["swift", "coding-style", "validation", "regex", "source:realm/SwiftLint", "ref:github_260602"],
     "**Summary:** beyond built-ins, `custom_rules:` in `.swiftlint.yml` lets you assert "
     "project-specific invariants with regex:\n\n"
     "```yaml\ncustom_rules:\n  no_print:\n    regex: '\\bprint\\('\n    message: \"Use Logger, not print\"\n    severity: error\n```\n\n"
     "**Pattern:** this is line-by-line regex grep — same engine class as Lode's "
     "`validate_lode.py::grep_files`, and the SAME pitfall applies (multi-line signatures "
     "escape a single-line regex). Keep asserted patterns on one line. "
     "Good for 'ban this API / enforce this prefix' rules a type-checker can't express."),

    # ── exception / error handling, memory ───────────────────────────────
    ("decision",
     "Alamofire — errors are values (Result), not exceptions",
     ["swift", "networking", "error-handling", "source:Alamofire/Alamofire", "ref:github_260602"],
     "Alamofire models failures as `Result<T, AFError>` delivered in the response handler, "
     "not thrown exceptions. Pattern: `.validate()` to turn non-2xx + wrong content-type into "
     "`.failure` up front, then a single `switch response.result` site handles success/failure.\n\n"
     "**Why (when an 'exception' needs extra handling):** network/decoding failure is an "
     "expected runtime value, not an exceptional crash — handle `.failure` explicitly at the "
     "call site; never force-unwrap `response.value`. `RetryPolicy` / `RequestInterceptor` "
     "centralise auth-refresh + backoff so retry logic isn't scattered."),

    ("pitfall",
     "RxSwift — subscriptions leak without DisposeBag; capture [weak self]",
     ["swift", "rxswift", "memory", "error-handling", "source:ReactiveX/RxSwift", "ref:github_260602"],
     "**Symptom:** observers never released → retain cycles, duplicate side effects firing "
     "after a screen is gone.\n\n"
     "**Root cause:** an `.subscribe(...)` returns a `Disposable`; if it isn't added to a "
     "`DisposeBag` owned by the subscriber, it lives forever. Closures that reference `self` "
     "without `[weak self]` form a cycle (self → bag → subscription → self).\n\n"
     "**Fix:** `.disposed(by: disposeBag)` on every subscription; `[weak self]` in subscription "
     "closures; let the bag deallocate with its owner. Also know hot vs cold: cold sequences "
     "re-run work per subscriber (multiple network calls); share with `.share(replay:)`."),

    ("pitfall",
     "SnapKit — use updateConstraints to change a constant, not makeConstraints twice",
     ["swift", "autolayout", "snapkit", "gui", "source:SnapKit/SnapKit", "ref:github_260602"],
     "**Symptom:** calling `snp.makeConstraints` a second time on the same view adds a "
     "*duplicate* constraint → 'Unable to simultaneously satisfy constraints' / layout breakage.\n\n"
     "**Fix:** `makeConstraints` once at setup. To change a value later use "
     "`snp.updateConstraints { $0.height.equalTo(newH) }` (same constraint, new constant), "
     "or `snp.remakeConstraints` to replace the whole set. Store a constraint ref only when "
     "you must animate it.\n\n"
     "**Principle:** any constraint-DSL has 'declare once / update vs remake' semantics — "
     "re-declaring is the silent bug."),

    ("pitfall",
     "Kingfisher — cancel image load on cell reuse or the wrong image flashes",
     ["swift", "image", "gui", "cell-reuse", "source:onevcat/Kingfisher", "ref:github_260602"],
     "**Symptom:** fast scrolling shows the wrong thumbnail briefly in a reused cell.\n\n"
     "**Root cause:** the async download from the cell's previous content resolves after the "
     "cell was reused for new content.\n\n"
     "**Fix:** `imageView.kf.setImage(with:)` already cancels the prior request for that view; "
     "for custom flows call `kf.cancelDownloadTask()` in `prepareForReuse()`. Use "
     "`.cacheOriginalImage` + a processor for resize-on-disk. **GUI rule:** any per-cell async "
     "work must be cancelled when the cell is recycled."),

    # ── macOS GUI behaviour / when to close ──────────────────────────────
    ("reference",
     "macOS menu-bar app pattern (Stats) — LSUIElement + NSStatusItem lifecycle",
     ["macos", "appkit", "gui", "menu-bar", "source:exelban/stats", "ref:github_260602"],
     "**Summary:** a status-bar utility (like Stats) sets `LSUIElement = true` in Info.plist "
     "(no Dock icon, no main window), owns an `NSStatusItem` from `NSStatusBar.system`, and "
     "shows content via an `NSPopover` or a menu.\n\n"
     "**When to close / lifecycle:** popover closes on outside click "
     "(`behavior = .transient`); the app does NOT quit when a window closes (there is no main "
     "window) — quit only via the menu. Heavy sampling loops must pause when the popover/menu "
     "is closed (don't poll sensors while nothing is visible). Relevant to Lode if it ever "
     "ships a background/menu-bar surface."),

    ("reference",
     "macOS window lifecycle (IINA) — controller-owned windows, close vs terminate",
     ["macos", "appkit", "gui", "window-lifecycle", "source:iina/iina", "ref:github_260602"],
     "**Summary:** IINA drives multiple windows (player, preferences, inspector) via "
     "`NSWindowController` subclasses; the controller owns the window and decides hide-vs-close.\n\n"
     "**When to close (directly answers '何時要關'):** "
     "`applicationShouldTerminateAfterLastWindowClosed` decides whether closing the last window "
     "quits the app — a document/utility app returns false and keeps running. Distinguish "
     "`window.orderOut(_:)` (hide, keep state) from `performClose`/releasing the controller "
     "(destroy). Prefs windows hide; document windows close. Mirrors Lode's Tauri "
     "`close vs destroy` pitfall — same concept, AppKit layer."),

    ("decision",
     "Tuist — generate the Xcode project to kill .pbxproj merge conflicts",
     ["swift", "xcode", "workflow", "source:tuist/tuist", "ref:github_260602"],
     "Tuist defines the project in a Swift `Project.swift` manifest and generates the "
     "`.xcodeproj` on demand (`tuist generate`), so the generated project is gitignored.\n\n"
     "**Why:** `.pbxproj` is a notoriously merge-conflict-prone serialized blob; generating it "
     "removes it from version control entirely and makes targets/settings reviewable as code. "
     "Trade-off: a build dependency on Tuist + a generate step. Useful reference if an iOS "
     "project ever joins the stack."),

    # ── general macOS gotcha that answers '何時要關' head-on ───────────────
    ("pitfall",
     "macOS AppKit — last-window-closed does NOT quit by default",
     ["macos", "appkit", "gui", "window-lifecycle", "ref:github_260602"],
     "**Symptom:** closing the only window leaves the app running (Dock icon stays) — or, "
     "if you force-quit on close, a utility app dies when the user only meant to dismiss a window.\n\n"
     "**Rule:** `NSApplicationDelegate.applicationShouldTerminateAfterLastWindowClosed(_:)` "
     "controls this — default behaviour differs from the Windows mental model. Decide per app "
     "type: document/editor apps usually return false; single-window apps return true. "
     "Pair with `applicationShouldHandleReopen` (Dock-click with no windows → reopen one). "
     "This is the macOS-native version of Lode's Tauri close/destroy gate."),
]


def main() -> None:
    store = VeinStore(VEIN_ROOT)
    existing = {(e.source, e.title.strip()) for e in store.iter_entries()}

    written = skipped = 0
    for etype, title, tags, body in ENTRIES:
        if (SOURCE, title.strip()) in existing:
            skipped += 1
            continue
        e = Entry.make(type=etype, title=title, body=body, tags=tags,
                       source=SOURCE, volatility=VOL)
        store.write_entry(e)
        existing.add((SOURCE, title.strip()))
        written += 1
        print(f"  + [{etype:9}] {title[:60]}")

    print(f"\nWrote {written}, skipped {skipped} (dupes).")

    vein = shutil.which("vein")
    if vein:
        print("Reindexing ...")
        subprocess.run([vein, "reindex"], cwd=str(VEIN_ROOT))
    else:
        print(f"Now run:  cd {VEIN_ROOT} && vein reindex")

    print('\nVerify:  vein recall "swiftlint validation gate"')
    print('         vein recall "macos when to close window"')
    print('         vein recall "rxswift memory leak disposebag"')


if __name__ == "__main__":
    main()
