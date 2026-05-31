#!/usr/bin/env python3
"""
import_lode_lore_addendum.py — 補漏 5 條 (第二批)

寫進 Vein 自己的 .vein/（cross-project lore，不放在 Lode repo）。

使用方式：
  python3 /Users/lion/Documents/vein/shell/import_lode_lore_addendum.py
"""

import sys
from pathlib import Path

VEIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VEIN_ROOT / "src"))

from vein.core.store import VeinStore
from vein.core.models import Entry

store = VeinStore(VEIN_ROOT)
print(f"Writing to: {store.vein_dir}\n")

ENTRIES = [

dict(type="pitfall",
title="App Store Sandbox breaks Lode's core feature: any-folder drag-in needs SSB rewrite",
tags=["app-store","sandbox","ssb","security-scoped-bookmarks","file-access","tauri","rust","architecture"],
body="""\
**Symptom:** Lode works perfectly in Direct Sale build. Switch to App Store (Sandbox) build → \
user drags a folder in → app can't read any files. Core feature completely broken.

**Root cause:** macOS App Store forces all apps into Sandbox. Lode's core design \
("user drags any folder, Lode reads directly") does NOT work in Sandbox.

**Required rewrite (4-6 days engineering):**
- Every user-selected path must call SSB API (Security-Scoped Bookmarks)
- Serialize NSURL bookmark → workspace.json
- On next launch: resolve bookmark + `startAccessingSecurityScopedResource()`
- Handle stale bookmarks (moved/deleted folders)
- Handle multi-instance access
- file_watcher must be sandbox-aware
- Web Clipper (lode:// URL scheme) needs new entitlement

**bookmarks.rs** already has Phase 0 skeleton in Lode CLAUDE.md. Full migration estimate: 4-6 days.

**After SSB migration:** still need notarize + submit + 1-7 day review + likely 1-2 rejections.
Total: 2-3 weeks for App Store migration.

**This is why Direct Sale ships first.** Don't attempt App Store until Direct Sale validates PMF."""),

dict(type="pitfall",
title="CF Pages HTML cached 4 hours at edge — deploy looks broken to users",
tags=["cloudflare","cache","deployment","html","headers","cdn"],
body="""\
**Symptom:** Deploy finishes successfully (green in dashboard). Users still see old version \
30 minutes later. Looks like deploy failed.

**Root cause:** Cloudflare CDN defaults to 4hr edge cache for HTML responses.
New deploy doesn't automatically purge edge cache.

**Fix:** Add `_headers` file to repo root:
```
/*
  Cache-Control: public, max-age=60, s-maxage=300, must-revalidate

/assets/*
  Cache-Control: public, max-age=31536000, immutable
```

HTML: max 5 min edge cache. Static assets: long cache (content-addressed by build).

**Debug tell:** Old page after 30s → cache issue. Old page after 10 minutes → actual deploy issue.
Run: `curl -I https://yourdomain.com | grep cache-control` to check current headers."""),

dict(type="pitfall",
title="Google Search Console: Domain property only accepts DNS TXT, not meta tag",
tags=["google","gsc","seo","dns","verification","cloudflare","domain"],
body="""\
**Symptom:** Added `<meta name="google-site-verification" content="...">` to all pages. \
GSC Domain property still shows "Unverified." URL inspection fails.

**Root cause:** GSC has two property types with different verification methods:
- **Domain property** (covers all subdomains + http/https): ONLY accepts DNS TXT record
- **URL Prefix property** (single URL pattern): accepts meta tag / HTML file / GA / DNS

**Fix:**
1. Cloudflare DNS → Add TXT record: `@ TXT google-site-verification=YOUR_TOKEN`
2. Keep meta tag too — useful for URL Prefix property as backup

**Recommended setup:** Create BOTH property types in GSC simultaneously:
- Domain property (primary, full coverage via DNS TXT)
- URL Prefix `https://yourdomain.com/` (backup, via meta tag)

**Also add Bing Webmaster Tools** — import from GSC in one click, worth 5 minutes."""),

dict(type="pitfall",
title="CF Pages env vars added in dashboard don't apply until Retry Deployment",
tags=["cloudflare","pages","env-vars","worker","environment","deployment"],
body="""\
**Symptom:** Added environment variable in CF Pages dashboard (e.g. GITHUB_TOKEN). \
Worker still fails with auth error. Logs show variable is undefined.

**Root cause:** CF Pages does not automatically re-deploy when env vars change. \
The existing deploy was built without the new variable. It stays cached until triggered.

**Fix:** After adding/changing env vars:
Dashboard → Pages project → Deployments → Latest → ⋮ menu → **Retry deployment**

This rebuilds with the new env vars applied.

**Pattern:** Every time you add a new env var:
1. Add in dashboard
2. Immediately Retry deployment
3. Verify in Worker logs

**Applies to:** GITHUB_TOKEN, API keys, feature flags, any runtime config."""),

dict(type="pitfall",
title="App Store never gives you buyer email — plan email strategy before launch",
tags=["app-store","email","marketing","launch","stripe","direct-sale","user-acquisition"],
body="""\
**Symptom:** App goes live on App Store. Users buy. You have zero way to contact them.

**Root cause:** App Store does not share buyer information with developers. Ever.
No email, no name, no purchase date visible to you.

**What you lose:**
- Cannot send welcome / onboarding email
- Cannot notify users of v1.1 release
- Cannot interview users for feedback
- Cannot send launch newsletter to past buyers
- Cannot cross-sell future products

**Direct Sale advantage:**
Stripe gives you buyer email at purchase. Full contact list from day 1:
```
Day 1: welcome + license key
Day 7: check-in (how is it going?)
Day 30: v1.1 release notes
Day 90: feedback survey + testimonial request
```

**Mitigation if App Store only:**
- Add "Register your purchase" flow inside app → collect email voluntarily
- Add newsletter signup in app (not mentioning it's for "buying elsewhere" — Apple prohibits that)
- Add support email link → users who email become contactable

**This is a core reason to do Direct Sale first** — build the email list before App Store \
takes over distribution."""),

]

for e in ENTRIES:
    entry = Entry.make(
        type=e["type"],
        title=e["title"],
        body=e["body"],
        tags=e["tags"],
        source="lode-retrospective-2026-addendum",
    )
    path = store.write_entry(entry)
    print(f"  ✓ [{e['type']:8}] {e['title'][:65]}")

print(f"\n{len(ENTRIES)} additional entries written to {store.vein_dir}")
print("\nRun: vein reindex && vein brief")
