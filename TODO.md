# TODO

## Task: Fix UI stylings of cards on `/dashboard/`

### Step 1 — Gather context
- [x] Inspect existing dashboard template(s): `dashboard.html`, `base_dashboard.html`, `dashboard_teacher.html`
- [x] Inspect current dashboard stylesheet: `static/pabasa_app/dashboard.css`
- [x] Identify which card styles are applied to dashboard cards (`.class-card`, etc.)

### Step 2 — Propose and confirm edit plan
- [ ] Fix/align card CSS so `.class-card` looks consistent (height/aspect ratio, spacing, hover, pseudo-element header stripe)
- [ ] Prevent conflicting duplicate/overridden CSS rules coming from template inline `<style>` vs shared CSS

### Step 3 — Implement changes
- [ ] Update `pabasa_app/static/pabasa_app/dashboard.css` *or* override in `dashboard.html` inline CSS (preferred: shared CSS)
- [ ] Ensure responsive layout doesn’t break card grid

### Step 4 — Validate
- [ ] Run server and manually check `http://127.0.0.1:8000/dashboard/`
- [ ] Verify expanded details don’t overflow/crop incorrectly

