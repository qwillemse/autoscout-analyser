# AutoScout24 Price Analyser — Plan

**Status:** 52 installs, 6 active users, 2 reviews (5★)
**Model:** XGBoost, MAE €2,100, 670k listings (NL + DE + BE)
**API:** Railway (`/data/` volume for pipeline.joblib, cars.db, range_lookup.json)

---

## ✅ Done recently

- Model-residual-based price ranges (per trim/make+model)
- Live-check for similar cars (top 30 → filter sold → show up to 3 active)
- Damaged listing filter in scraper (`damaged_listing=exclude`)
- Badges retry on first page load (race conditions fixed)
- pushState SPA nav detection (homepage → search)
- Fixed duplicate `_lastUrl` that silently broke the whole content script
- GitHub Action: weekly scrape + retrain + auto-upload to Railway
- Scraper: request timeout (10s/30s) + 1 retry — prevents hung requests from eating the GH Actions budget
- GH Action: parallelized per-country (NL/DE/BE matrix) — each gets its own 6h budget, then a final merge+retrain+upload job
- Multi-country support (NL, DE, BE + manifest entries for AT/FR/IT/ES/LU)

---

## 🔄 In progress

- GitHub Action running manually (first test run) — should finish in ~2h

---

## 📋 Next up

### Growth (top priority — product is solid, need users)

1. **Get reviews from existing 6 users** ✅ — "Leave a review" prompt after 5 analyses implemented
2. ~~**Dutch/German Facebook groups**~~ — blocked (Facebook account disabled)
3. **More TikTok/Insta volume** — post 1+ per week
   - Different angles: "Found a car 40% below market value", "Negotiating with AI", "This dealer overpriced by €8k"
4. **Car YouTubers DM** — in progress
   - Dutch: Uncle of Trash, AutoVisie, AutoRAI, Auto Review
   - German: Matthias Malmedie, smaller 10-50k subs more likely to respond
5. **Direct outreach** — friends car shopping, ask them to try + review
6. **Add usage analytics** — deferred until ~100 users (not needed at current scale)

### Optional polish (if bored waiting)

- Full scrape for AT / FR / IT / ES / LU once NL/DE/BE stable
- Small UI: "Last updated X days ago" in sidebar footer

---

## 🧠 Future (when user count > 100)

- Premium tier — gate LLM insight + similar cars ranking
- Price alerts (when AutoScout's own isn't enough)
- Equipment/description parsing for richer predictions (needs per-listing scrape)
- Other marketplaces — mobile.de, marktplaats, AutoTrader UK

### Not doing (feature creep / low ROI)

- Sell to AutoScout — they have their own price check
- Price history per listing — not useful for buyers
- Owner count impact — niche
- Flyers — terrible ROI for Chrome extensions
- Multi-site right now — need to nail AutoScout first

---

## 🐛 Known bugs / tech debt

- [ ] Chrome Web Store description still says "300,000+ listings" (now 670k)
- [ ] Verify next weekly Action run completes (per-country parallel; each ≤6h budget, train-deploy joins after)
- [ ] DB has no duplicate check — minor, but should verify once
- [ ] No automated tests

---

## 📊 Metrics to track weekly

- Chrome Web Store installs (total + weekly delta)
- Active users (installs minus uninstalls)
- Reviews count + average rating
- TikTok / Instagram views per video
- Railway daily API calls (proxy for engagement)
- GitHub Action: did it run + MAE from train_results.json
