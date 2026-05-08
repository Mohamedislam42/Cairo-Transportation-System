# CSE112 bonus (10 marks) — evidence checklist

Fill in **your** deadlines, links, and screenshots. The PDF splits marks across submission timing, tooling story, visuals, deployment, and GitHub/demo/LinkedIn.

## 1) Early submission — Week 13 (2 marks)

- [ ] Confirm your instructor’s **exact Week 13 cut-off** (day/time/LMS timezone).
- [ ] Submit **before** that deadline — keep a screenshot of the LMS receipt or Git tag date.

## 2) AI tools & technologies (2 marks)

Prepare a short **honest appendix** for the PDF/report (half a page is enough):

- **Which tools**: e.g. Cursor, ChatGPT, Copilot, Stack Overflow — list what you **actually** used.
- **How**: e.g. “debugging Flask/static paths”, “Drafting README”, **not** replacing your algorithm logic without understanding.
- **Evidence**: 1–2 screenshots of chat or editor with **student-edited code** beside it.

## 3) Enhanced visualization & UI (2 marks)

Demonstrate **in video or annotated screenshots**:

- **Leaflet** map with Cairo network, metro / heat toggles, basemap switch.
- **Routing**: optional **animated** single route (`Animate routes`).
- **Bonus visualizer**: `Compare Dijkstra vs A*` with **Animate routes** ON → parallel **race** draw (solid green vs dashed red).
- **Algorithm race modal** timings + hops (`/compare_algorithms`).

## 4) Deployment & engineering (3 marks)

Aligned to the assignment wording:

| Item | Repo implementation | Evidence to capture |
|------|-----------------------|---------------------|
| **ML congestion forecast** | `traffic_predictor.py` — sklearn **RandomForest** trained on **`TRAFFIC_PATTERNS`** temporal flows | Screenshot Optimize → **ML congestion** + cite file in report |
| **Dijkstra vs A\* comparison / race viz** | Map compare overlay + modal race + **animated dual draw** when “Animate routes” is on | Short screen recording |
| **Live web app URL** | Deploy (Render recommended with Docker). GitHub Pages is static-only — poor fit for Flask. | Paste **HTTPS** URL in README + demo slides |
| **Docker** | `project/Dockerfile` + repo `docker-compose.yml` | Terminal screenshot `docker compose up`, or Render “Docker build succeeded” |

## 5) GitHub + README + demo + LinkedIn (1 mark)

- [ ] **Public** GitHub repo (or whatever your syllabus allows).
- [ ] README at repo root: quick start + **bonus mapping** + **deploy URL**.
- [ ] Screen recording (**2–4 min**) showing: routing → ML predict → compare/race animation → Optimize tab.
- [ ] LinkedIn post (adapt `LINKEDIN_POST_DRAFT.md` below) with **demo link**.

---

### LinkedIn post draft (`LINKEDIN_POST_DRAFT.md`)

Create this file locally or paste into LinkedIn:

> Built Cairo Transport Lab (CSE112): Flask API + Leaflet map, Dijkstra / time-dependent / A\* EMS routing, MST + DP optimization tools, greedy signals, sklearn traffic forecast, Docker + \[Render/Vercel\]. Repo: \[URL\] · Live demo: \[URL\]  
> \[1 line on what you learned\]

Replace bracketed parts.
