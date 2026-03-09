// Runs in the PAGE'S main world (not the isolated content script context).
// Intercepts Next.js /_next/data/ fetches and relays listing data to the
// content script via a DOM CustomEvent (which crosses the isolation boundary).
(function () {
  const _orig = window.fetch.bind(window);

  window.fetch = function (url, ...args) {
    const p = _orig(url, ...args);

    if (typeof url === "string" && url.includes("/_next/data/")) {
      p.then((r) => r.clone().json())
        .then((data) => {
          const listings = data?.pageProps?.listings;
          if (Array.isArray(listings) && listings.length) {
            document.dispatchEvent(
              new CustomEvent("__as24_spa_listings__", { detail: listings })
            );
          }
        })
        .catch(() => {});
    }

    return p;
  };
})();
