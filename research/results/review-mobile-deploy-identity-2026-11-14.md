# Deployment version proof on mobile (review branch; 2026-11-14)

The user previously saw an old public UI despite GitHub changes. The Render
review demo had auto-deploy disabled, and private-coordinator and production
run independently. The new public **review-only** version indicator reads
Render's documented built-in RENDER_GIT_COMMIT, RENDER_GIT_BRANCH,
RENDER_SERVICE_NAME and RENDER flags (see render.com/docs/environment-variables).
The server accepts a valid 40-character SHA and the exact review service and
branch before labeling it verified; otherwise displays UNVERIFIED, never a
guessed commit number.

Only demo endpoint GET /api/v3/review/version is added; no provider, Render
private coordinator, SDK, broker token, data access or live trading. The
phone fetches metadata from its own host on page load and via a button,
so the displayed revision corresponds to the currently running server,
not the latest GitHub commit nor browser cache. UI provides offline
fallback. This endpoint is not available on production.

GitHub Actions adds unit/HTTP/UI tests for correct commit, wrong branch,
wrong service, secret-free response, status WAIT and trading disabled.
No automatic production or private deployment is requested.
