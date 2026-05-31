#!/usr/bin/env python3
"""
import_lode_lore.py

在 Lode app repo 建立 .vein/ 知識庫。
從 2 個月 App Store 上架經驗提取 19 條 lore。

使用方式：
  cd /Users/lion/Documents/lode
  vein init              # 如果還沒建
  python3 /Users/lion/Documents/vein/shell/import_lode_lore.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vein.core.store import VeinStore
from vein.core.models import Entry

store = VeinStore.require()
print(f"Writing to: {store.vein_dir}\n")

ENTRIES = [

# ── DECISIONS ──────────────────────────────────────────────────────────────

dict(type="decision",
title="Direct Sale first 6 months, App Store as second channel",
tags=["app-store","direct-sale","stripe","business","revenue"],
body="""\
**Why:** App Store takes 30% vs Stripe 3%. First 6 months is PMF validation — don't burn \
2-3 weeks on Sandbox migration before knowing anyone wants the product.

**Numbers:** 150 users × $19 = $2,850/mo. Direct Sale keeps $2,765. App Store keeps $1,995. Year-1 gap: $9,240.

**Trade-off:**
- Direct Sale: own email list, instant hotfix, free pricing — no App Store trust signal
- App Store: 30% cut, 1-7 day review per hotfix, no user email — but auto-update + credibility

**The plan:**
- Day 0-90: Direct Sale only, validate pricing + product
- Day 90-180: Direct Sale + begin Sandbox/SSB refactor for App Store
- Day 180+: App Store as second channel, Direct Sale stays primary (97% revenue)

**Rejected:** "Ship App Store day 1" — Sandbox migration = 4-6 days. Add 2-4 weeks review. \
First product shipped 2 months after needed it.

**Revisit when:** revenue > $5K/mo or users specifically request App Store."""),

dict(type="decision",
title="Rebuild Cloudflare Pages project when stuck-state corrupts — do not repair",
tags=["cloudflare","pages","infrastructure","deployment","500"],
body="""\
**Why:** CF Pages uses Content-Addressable Storage for asset dedup. One upload error corrupts \
the CAS entry. All future deploys skip re-upload ("already uploaded") but serve corrupted asset. \
No cache-busting, empty commits, or build cache toggles fix this.

**Signal you're in stuck-state:**
`Uploaded 2 files (30 already uploaded)` when you know 30+ files actually changed.

**Tried and failed:** Disable Build Cache / empty commits / moving functions / try-catch wrappers.

**Only fix:** Rebuild CF Pages project (~45 min one-time). New project = fresh manifest from scratch.

**Steps:**
1. Backup env vars + DNS snapshot
2. New CF Pages project → same GitHub repo
3. Smoke test: push layout change → verify deploy
4. Switch custom domain → new project
5. Delete old project after 48h

**Revisit when:** CF Pages fixes CAS corruption in their changelog."""),

dict(type="decision",
title="notarytool store-credentials once with profile name — never store raw password",
tags=["apple","notarize","notarytool","codesign","keychain","security"],
body="""\
**Why:** notarytool requires App-Specific Password (not real Apple ID password). \
Store-credentials puts it in macOS Keychain once. Every release script references profile name only.

**One-time setup (~2 hours total):**
1. Apple Developer Program $99/yr (1-2 business days approval)
2. Xcode → Settings → Accounts → Manage Certificates → + → Developer ID Application
3. appleid.apple.com → App-Specific Passwords → generate → save securely
4. `xcrun notarytool store-credentials lode-notary --apple-id you@email.com --team-id XXXXXXXXXX --password xxxx-xxxx-xxxx-xxxx`
5. `xcrun notarytool history --keychain-profile lode-notary` to verify

**Every release after:** pass `--notarize-profile lode-notary` to release script. Done.

**Common failures:**
- Apple ID + Team ID mismatch (one ID can belong to multiple teams)
- Used real password instead of app-specific password
- Apple ID has no 2FA (notarytool requires 2FA)
- Login Keychain locked → `security unlock-keychain login.keychain` first"""),

dict(type="decision",
title="Developer ID Application cert for notarize (NOT Mac App Distribution)",
tags=["apple","codesign","certificate","notarize","distribution"],
body="""\
**Two completely different cert types for two different distribution paths:**

Developer ID Application → Direct Sale / notarize path
- Signs .app for distribution outside App Store
- Required for notarytool
- Verify: `security find-identity -v -p codesigning | grep "Developer ID Application"`

Mac App Distribution → App Store path
- Signs .app for upload to App Store Connect via Transporter
- Cannot be used for notarize

**Entitlements also differ:**
- Direct Sale: `Entitlements.directsale.plist` — no sandbox
- App Store: sandbox=true + SSB (Security-Scoped Bookmarks) required for file access

**If you mix these up:** notary rejects with `Invalid Code Signing Entitlements` or \
spctl says "source=Unnotarized Developer ID"."""),

dict(type="decision",
title="Universal Binary from day 1 (Apple Silicon + Intel)",
tags=["tauri","rust","universal-binary","apple-silicon","distribution","app-store"],
body="""\
**Why:** App Store requires Universal Binary. Retrofitting later = build system changes + full re-test. \
Cost is low if done on day 1.

**Verify after build:**
```bash
lipo -info /path/to/Lode.app/Contents/MacOS/lode
# Expected: Architectures in the fat file: lode are: x86_64 arm64
```

**tauri.conf.json required settings:**
```json
"macOS": {
  "minimumSystemVersion": "12.0",
  "hardenedRuntime": true,
  "entitlements": "./Entitlements.directsale.plist"
}
```
hardenedRuntime: true is mandatory for notarize. Missing it = instant reject."""),

# ── PITFALLS ──────────────────────────────────────────────────────────────

dict(type="pitfall",
title="App Store first submission: expect 2-3 rejections, 2-4 weeks total",
tags=["apple","app-store","review","rejection","timeline","planning"],
body="""\
**Symptom:** Submit → wait 3-7 days → rejected → fix → resubmit → repeat. \
Lode hit 4 rejections over 2 weeks.

**Common first-submission rejection reasons:**
- Missing Support URL in metadata
- Missing Pricing page URL
- IAP not configured in App Store Connect before binary upload
- App description mentions external pricing (prohibited by Apple)
- Privacy nutrition label incomplete or inaccurate
- Review Notes absent (reviewer can't test key features)
- App icon has alpha channel (not allowed)

**Mitigation:**
1. Read App Store Review Guidelines 2.1, 4.2, 4.8 before writing any code
2. Create support + pricing pages on website FIRST
3. Configure all IAPs in App Store Connect BEFORE uploading binary
4. Include detailed Review Notes: how to trigger each key feature
5. If rejected: reply in Resolution Center within 24h, be specific

**Timeline reality:** Do not schedule launch-dependent events within 4 weeks of first submission."""),

dict(type="pitfall",
title="App Store submission blocked: Support URL + Pricing URL must exist before submit",
tags=["apple","app-store","metadata","support","pricing","url","pre-launch"],
body="""\
**Symptom:** Submit for review → metadata validation error or early rejection about missing URLs.

**Required before submitting binary:**
- Support URL: real page with contact info (e.g. rexcode.app/lode/support/)
- Marketing URL: optional but good to have
- All IAPs created in App Store Connect (even if not yet live)

**Required website pages (create these DAY 1):**
- /lode/support/ — contact method + bug report instructions
- /lode/pricing/ — tier names and prices
- /lode/privacy/ — especially Keychain usage, local-only processing, no telemetry
- /lode/terms/ — license type, refund policy, jurisdiction

**IAP setup order:**
1. App Store Connect → My Apps → Lode → In-App Purchases
2. Create Pro Yearly (auto-renewable subscription, $49.99)
3. Create Lifetime (non-consumable, $99.99)
4. Only THEN upload binary and submit"""),

dict(type="pitfall",
title="notarize rejected: hardenedRuntime missing or wrong cert type",
tags=["apple","notarize","hardened-runtime","certificate","codesign","entitlements"],
body="""\
**Symptom:** notarytool submit → Rejected with `Invalid Code Signing Entitlements` or \
`The signature does not include a secure timestamp`.

**Cause A:** hardenedRuntime: false in tauri.conf.json
Fix: `"hardenedRuntime": true` — mandatory for notarization.

**Cause B:** Using Mac App Distribution cert instead of Developer ID Application
Fix: `security find-identity -v -p codesigning | grep "Developer ID Application"` — \
must show this exact type.

**Cause C:** Entitlements file missing or malformed
Fix: verify path in tauri.conf.json points to existing .plist file.

**Quick local verify after build:**
```bash
spctl -a -t open --context context:primary-signature -vvv ~/releases/Lode.dmg
# Must show: "Notarized Developer ID"
```"""),

dict(type="pitfall",
title="Cloudflare Pages CAS corruption: layout change → all routes 500",
tags=["cloudflare","pages","500","deployment","jekyll","layout","CAS"],
body="""\
**Symptom:** Changed `_layouts/page.html`. CF Pages shows `Uploaded 2 files (30 already uploaded)`. \
All routes return 500 except static files (robots.txt etc). Local Jekyll build fine.

**Root cause:** Upload error during a commit corrupted CF's CAS (Content-Addressable Storage). \
Future deploys dedup ("already uploaded") but serve corrupted content. Layout changes touch many \
pages, amplifying corruption.

**Tried and failed:** Disable Build Cache / empty commits / moving functions / try-catch.

**Only fix:** Rebuild the CF Pages project (new project, same repo). See REBUILD_CF_PAGES_GUIDE.md.

**Prevention:** After any commit with upload warnings, verify all critical routes return 200 \
before merging more changes."""),

dict(type="pitfall",
title="CF Pages Worker 1MB limit → silent runtime 500 (not build failure)",
tags=["cloudflare","worker","bundle-size","500","images","base64","limit"],
body="""\
**Symptom:** Worker deploys successfully, build logs clean. But runtime returns 500 immediately.

**Root cause:** CF Pages Worker free plan: 1MB limit. Paid: 5MB. Base64 images add 33% overhead. \
Exceeding limit fails at RUNTIME, not build time.

**Safe formula:** `(total_image_kb × 1.33) < 750KB`

**Debug first:** When Worker suddenly 500s with no code change → check bundle size.

**Fix options (in order of preference):**
1. Compress images before embedding
2. Move images to Cloudflare R2, fetch via Worker (no size limit)
3. Use static assets instead of Worker

**Migration to R2:**
```bash
npx wrangler r2 bucket create lode-images
npx wrangler r2 object put lode-images/photo.png --file=./photo.png
```
Then in Worker: `const obj = await context.env.MY_BUCKET.get(filename)`"""),

dict(type="pitfall",
title="CF Pages: static assets take priority over Worker Functions at same path",
tags=["cloudflare","pages","worker","static","routing","priority"],
body="""\
**Symptom:** Worker deployed at `/lode/images/[[path]].js`. Requests to `/lode/images/photo.png` \
return wrong content-type. Worker never called.

**Root cause:** CF Pages serves static assets from manifest before invoking Workers. \
If file exists in manifest (even corrupted), Worker is bypassed.

**Fix:** `git rm` the static file → CF removes from manifest → Worker takes over.

**Routing priority (high to low):**
1. Static assets in manifest
2. Exact function file (`functions/lode/faq.js` beats `functions/lode/[[path]].js`)
3. Catch-all wildcard (`[[path]].js`)"""),

dict(type="pitfall",
title="venv symlink tracked by git → Cloudflare build crashes every deploy",
tags=["git","cloudflare","jekyll","venv","symlink","python","deployment"],
body="""\
**Symptom:** Every CF Pages deploy: `Errno::ENOENT - /opt/buildhome/repo/venv`. \
Jekyll dies immediately. Local works fine.

**Root cause:** `venv -> ../py/venv` symlink was accidentally `git add`-ed. \
CF build machine has no symlink target.

**Fix:**
```bash
git rm --cached venv
echo "venv" >> .gitignore
```
Also add to _config.yml exclude list.

**Prevention:** Any symlink pointing outside the repo → .gitignore on Day 1. \
If `git status` shows `?? venv` → immediately `git rm --cached` it."""),

dict(type="pitfall",
title="robots.txt Disallow: / silently blocks Googlebot → zero indexing",
tags=["seo","robots","googlebot","jekyll","google-search-console"],
body="""\
**Symptom:** Users can browse the site. GSC URL Inspection says page cannot be indexed.

**Root cause:** Copied robots.txt had `User-agent: * / Disallow: /`. Blocks everything.

**Fix:** Default to Allow. Block only known bad bots by name:
```
User-agent: *
Allow: /
Disallow: /03_todo_fectures/

User-agent: GPTBot
Disallow: /
```

**Important:** `dig A yourdomain.com @8.8.8.8` to verify from external resolver. \
"User can see it" ≠ "Google can crawl it"."""),

dict(type="pitfall",
title="jekyll-sitemap default false → sitemap.xml empty → Google can't index",
tags=["jekyll","seo","sitemap","google","cloudflare","config"],
body="""\
**Symptom:** sitemap.xml exists but contains only `<urlset></urlset>`. Pages not indexed.

**Root cause:** `_config.yml defaults: values: sitemap: false` globally. \
Every page must opt-in with `sitemap: true`.

**Fix:** Remove the default. Only exclude internal directories:
```yaml
exclude:
  - 03_todo_fectures
  - functions
  - venv
```

jekyll-sitemap default is true — actively setting false = actively blocking Google."""),

dict(type="pitfall",
title="kramdown ignores markdown inside HTML block tags",
tags=["jekyll","kramdown","markdown","html","rendering","section"],
body="""\
**Symptom:** `## Heading` inside `<section>` displays as raw `## Heading` text.

**Root cause:** kramdown doesn't process markdown inside HTML block elements.

**Fix A:** Add `markdown="1"` attribute to the HTML tag:
```html
<section markdown="1">
## This heading now works
</section>
```

**Fix B:** Write pure HTML inside block tags (more reliable):
```html
<section><h2>Heading</h2></section>
```

**Rule:** Inside `<details>`, `<section>`, `<div class="grid">` — \
either all HTML OR add `markdown="1"`. Never mix without the attribute."""),

# ── LORE ──────────────────────────────────────────────────────────────────

dict(type="lore",
title="macOS indie app launch checklist: create these BEFORE writing code",
tags=["apple","app-store","checklist","launch","macos","indie"],
body="""\
Based on 4 App Store rejection cycles. Create all of these before the first binary upload.

**Website pages (must exist before App Store submission):**
- /lode/support/ — contact info + bug report method
- /lode/pricing/ — all tiers with prices
- /lode/privacy/ — Keychain usage, no telemetry, local-only processing
- /lode/terms/ — license type, refund policy, jurisdiction

**App Store Connect (before uploading binary):**
- All IAPs created: Pro Yearly + Lifetime (or your tiers)
- Screenshots: 1280×800 + 2560×1600 minimum (5 required per size)
- App icon: 1024×1024 PNG, NO alpha channel
- Review Notes: step-by-step how to test every key feature

**Binary requirements:**
- hardenedRuntime: true
- Valid entitlements .plist
- Universal Binary (x86_64 + arm64)
- minimumSystemVersion: "12.0" (or whatever you support)
- No debug symbols in release build

**Timeline reality:** Plan 2-4 weeks from first submission to approval. \
Create all of the above BEFORE any App Store submission to avoid rejection delays."""),

dict(type="lore",
title="notarize verification commands: run these after every release build",
tags=["apple","notarize","codesign","spctl","verify","release","sop"],
body="""\
Run after every release build before distributing:

```bash
# 1. Verify .dmg notarization
spctl -a -t open --context context:primary-signature -vvv ~/releases/Lode.dmg
# Expected: "Notarized Developer ID"

# 2. Mount + verify .app
hdiutil attach ~/releases/Lode.dmg
spctl -a -t exec -vvv /Volumes/Lode/Lode.app
# Expected: "accepted / source=Notarized Developer ID"
hdiutil detach /Volumes/Lode

# 3. Detailed codesign check
codesign --verify --deep --strict --verbose=2 /Volumes/Lode/Lode.app
# Expected: "valid on disk / satisfies its Designated Requirement"
```

**If spctl says "Unnotarized Developer ID":** hardenedRuntime=false or wrong cert type.

**Ultimate test:** Fresh Mac that never ran Lode → double-click .dmg → opens without Gatekeeper warning. \
Use a friend's Mac or create a fresh iCloud user account on your machine."""),

dict(type="lore",
title="Cloudflare Pages: routing rules, debug patterns, and gotchas",
tags=["cloudflare","pages","routing","functions","worker","github","api","debugging"],
body="""\
**Routing priority:**
1. Static assets in CF manifest (Workers can't override)
2. Exact function file: `functions/lode/faq.js` handles `/lode/faq`
3. Catch-all: `functions/lode/[[path]].js` handles all other `/lode/*`

**Debug 500 checklist:**
1. Check if stuck-state: `Uploaded N files (but M should have changed)` → rebuild project
2. Check Worker bundle size → must be < 750KB (free) or < 5MB (paid)
3. Check if static asset at same path as Worker → `git rm` static file
4. Check env vars — don't auto-apply to existing deploys → must "Retry deployment" manually

**node --check limitation:** Does not catch ES module template literal boundary errors. \
Use `try { new Function(code) } catch(e) { console.error(e) }` to verify Workers.

**GitHub API:** 60 req/hr anon limit shared by ALL CF egress IPs → always use PAT. \
Fine-grained PAT with read-only Issues+Metadata is sufficient.

**DNS verify:** `dig A yourdomain.com @8.8.8.8` after domain setup. \
Browser DNS cache ≠ Google/CF resolver view."""),

]

written = 0
for e in ENTRIES:
    entry = Entry.make(
        type=e["type"],
        title=e["title"],
        body=e["body"],
        tags=e["tags"],
        source="lode-retrospective-2026",
    )
    path = store.write_entry(entry)
    print(f"  ✓ [{e['type']:8}] {e['title'][:65]}")
    written += 1

print(f"\n{written} entries written to {store.vein_dir}")
print("\nNext steps:")
print("  vein reindex   # build FTS search index")
print("  vein brief     # verify output")
print("  vein recall 'app store'   # test recall")
