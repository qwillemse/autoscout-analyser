# AutoScout24 Price Analyser — Plan

**Status:** 52 installs, 6 active users, 2 reviews (5★)
**Goal:** Reach 50-500 active users. Fix retention bugs, try new growth channels.

---

## Week 1 — Fix retention bugs

These directly affect the 6 current users' experience. Must-fix before more promotion.

### 1. Similar cars show sold / damaged cars
**Problem:**
- Even with 30-day DB purge, top 3 "best deals" often sold out (cars sell fast)
- Damaged cars get high predicted price (damage not visible on search page) so they look like "great deals"

**Fix:**
- For top 3 similar cars, only show listings scraped in last **7 days** (not 30)
- Add a `damaged_listing=exclude` filter to scraper URLs (AutoScout24 supports this — we're already using it for new scrapes, check older data)
- Consider: skip cars with extreme negative diff_pct (e.g. <-50%) — almost always damaged or mispriced

### 2. Badges don't load on first load
**Problem:** Content script races with page load, misses `__NEXT_DATA__` sometimes

**Fix:**
- Add retry logic with MutationObserver — if no listings found, watch DOM and retry
- Or increase initial delay / listen for `DOMContentLoaded` + 500ms

### 3. Data freshness
**Problem:** Scrape is manual, DB goes stale, similar cars become irrelevant

**Fix:**
- Set up a weekly automated scrape (cron on laptop, or GitHub Action)
- Include all current countries (NL, DE, BE) + retry BE which failed last time
- Consider: daily partial scrape (just new listings per make) instead of full weekly

---

## Week 2 — Growth experiments

Social media didn't work with 2 posts. Try different channels and more volume.

### 1. Get reviews from existing 6 users
**How:**
- Can't contact Chrome Web Store users directly
- Instead: add a small "Enjoying this? Leave a review" link in the sidebar footer after a user has seen predictions for 5+ cars
- Reviews matter most for Chrome Web Store SEO

### 2. Dutch/German Facebook groups
- "Occasions Nederland", "Auto's te koop", "Tweedehands auto's"
- "Gebrauchtwagen kaufen", "Auto kaufen Deutschland"
- Post same text as the forum draft — no karma requirements

### 3. Car YouTubers (DM approach)
- Dutch: Uncle of Trash, AutoVisie, AutoRAI, Auto Review
- German: Matthias Malmedie, JP Performance (too big probably)
- Smaller 10-50k subs creators more likely to respond
- DM: "Hey, I built a free Chrome extension that checks used car prices on AutoScout24.
  Trained on 670k listings. Thought you might find it interesting for one of your videos.
  Free to use, no affiliation."

### 4. More TikTok/Insta volume
- Post 1 video per week minimum
- Different angles:
  - "I found a car 40% below market value"
  - "POV: negotiating with a seller using AI data"
  - "This dealer is overpricing by €8,000"
- First 2 seconds matter most — hook before "here's what I built"

---

## Future — only if growth kicks in

### If 100+ users
- Build a proper "price trend" feature (needs months of data)
- Premium: LLM insight becomes paid, free users get just badges
- Full scrape for AT/FR/IT/ES/LU
- Add automated tests (XGBoost, API, extension)

### If 500+ users
- Upgrade Railway to handle load
- Start considering monetization seriously
- Consider other platforms (mobile.de, marktplaats, etc.)

### Not doing (feature creep)
- Sell to AutoScout — they have their own system, no interest likely
- Price history per listing — not useful for buyers
- Flyers — terrible ROI for Chrome extensions
- Owner count impact — niche feature

---

## Known bugs / tech debt

- [ ] Similar cars show sold/damaged cars
- [ ] Badges don't load on first page load sometimes
- [ ] BE scrape failed (DNS issues) — never retried fully
- [ ] DB has no duplicate check — should verify
- [ ] Chrome Web Store description says 300k listings (actually 670k)

---

## Metrics to track weekly

- Chrome Web Store installs (total + weekly delta)
- Active users (installs minus uninstalls)
- Reviews count + average rating
- TikTok/Insta views
- Railway API calls per day (hints at engagement)
