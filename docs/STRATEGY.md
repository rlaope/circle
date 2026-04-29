# circlelib — Strategy & Market Analysis

> Last updated: 2026-04-29

This document captures the market analysis behind circlelib's direction.
Operational task lists and milestones live in
[ROADMAP.md](ROADMAP.md). Technical-architecture context for contributors
lives in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Market diagnosis

### Direct competitors (declarative 3D DSLs)

| Project | Strengths | What users complain about |
|---|---|---|
| **OpenSCAD** | The de-facto standard for declarative 3D in the 3D-printing community. Huge install base. | "Doesn't feel like a programming language" — no real functions, no dictionaries, awkward scoping; manual coordinate math; fillets/chamfers are painful (Minkowski is slow); blurred preview; no STEP export; older renderer is slow. (CHI 2024 study, openscad/openscad#4301, HN threads) |
| **CadQuery / build123d** | Python + OpenCascade, accurate parametric CAD. | Heavy OCCT dependency, steep learning curve. Aimed at precision CAD, not interactive scenes. |
| **OpenJSCAD** | JS port of OpenSCAD, browser preview. | Smaller community than OpenSCAD. |
| **DeclaraCAD / ImplicitCAD / Antimony** | Niche academic alternatives. | Tiny user pools, low maintenance velocity. |
| **POV-Ray** | Declarative ray-tracing DSL with deep history. | Aging ecosystem, heavy syntax, niche use cases. |

### Adjacent / complementary markets

- **Manim** (3Blue1Brown / Manim Community) — Python library for math animations, exploding in STEM education and YouTube explainers. Weak at general 3D scene graphs; primarily a 2D/expression engine with some 3D affordances.
- **p5.js / Processing** — imperative creative coding. In 2025, **Spatial p5** (SIGGRAPH 2025) extended into live-coding mixed reality. The "declarative + module system" axis is still empty here.
- **Three.js / Babylon.js** — imperative JS libraries. Powerful, but no compact "scene as code" surface.
- **Hydra / TouchDesigner** — node and stream based live visuals. Text-DSL slot is empty.

### Key insight

The empty intersection is:

> **OpenSCAD-fans whose pain is the language**
> ∩ **manim-style declarative authors who want true 3D scene graphs**
> ∩ **creative coders who want to share short 3D snippets like p5 sketches**.

circlelib's current shape — a modern small DSL with imports/components,
plus an animation roadmap and a renderer that's already interactive — sits
exactly in that intersection.

---

## 2. Positioning

### One-line positioning
> **3D scenes as code — modules, components, and animations in a small modern language.**

### Four differentiation axes
1. **Modern language design.** Real imports, components, scoped arguments, hex colors, tuples — fixes the #1 complaint OpenSCAD users have today.
2. **Interactive-grade renderer by default.** OpenSCAD/CadQuery render *previews*; circlelib opens an orbit-camera window with a Matrix-style grid out of the box. Better fit for live demos and education.
3. **Animation as a first-class citizen.** Manim's declarative spirit applied to 3D scenes. The evaluator is already designed to split into static + frame passes.
4. **Readable codebase.** Parser → AST → evaluator → OpenGL pipeline shipped in a single small package. A defensible niche as a *teaching reference* for compilers/graphics students.

### Positioning matrix

```
                         imperative
                            |
              three.js  ●   |   ● p5.js / Processing
                            |
    parametric ───────────┼─────→ instantly interactive
                            |
              OpenSCAD  ●   |   ◎ circlelib  ← target
              CadQuery  ●   |
                            |
                         declarative
```

---

## 3. Target users

### S-tier (build for these first)
1. **OpenSCAD users frustrated with the language.** Migration motive: familiar functions/modules/scopes.
2. **STEM educators / explainer-video creators (manim adjacency).** Motive: short code → polished 3D + animation.
3. **Compilers / graphics students.** Motive: a complete reference implementation under ~10 KLoC.

### B-tier (after v1.0)
4. Live coders (after hot-reload + web export).
5. Indie game prototypers (after animation + collision stubs).

### Explicitly *not* targeting
- Precision CAD / manufacturing (CadQuery / Fusion territory; pulling in OCCT would be self-defeating).
- Full PBR / film rendering (Blender / USD territory).

---

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Toy DSL only the author uses | medium | severe | Force three external use cases (lecture, blog demo, peer project) within first 90 days. |
| OpenSCAD adopts modules/scopes | low | medium | Already locked in animation + interactivity as the second moat in v0.3. |
| Manim adds proper 3D scene graphs | medium | medium | Imperative API is their identity; declarative imports/components remain ours. |
| OpenGL deprecation pressure on macOS | medium | medium | Plan a wgpu / Vulkan back-end abstraction around v0.4; consider wgpu-py or MoltenVK. |
| Solo maintainer bottleneck | high | high | Aggressive `good first issue` labelling from day one; promote 2–3 outside contributors by v0.4. |

---

## 5. Distribution playbook (community)

### 0 → 100 stars
- HN / Lobsters Show post — hook: "OpenSCAD got me, but the language wore me out, so I wrote a tiny DSL with a Lark grammar and an OpenGL renderer." Hero image + 30s GIF (static → animated).
- Reddit: r/openscad, r/proceduralgeneration, r/learnprogramming, r/compsci — different angles per sub.
- Manim Discord and education Slacks — "manim, but in 3D" angle.

### 100 → 1000 stars
- Ship v0.3 animation; release a 6-GIF Twitter thread.
- "Recreate this in circlelib" challenge format.
- Course-pack for university lecturers (slides + 5 assignments).
- Promote first external contributors to maintainer status after their second non-trivial PR.

### 1000+
- Public gallery site with embeddable scenes.
- Workshop tracks (CHI Late-Breaking, JsConf visual tracks, PyCon KR).

---

## 6. Bottom line

The defensible position is *"OpenSCAD's spirit, with a sane language,
animation, and shareability."* Hold that line, ship the v0.2 → v0.3 →
v0.4 sequence in [ROADMAP.md](ROADMAP.md), and market on exactly two
angles (OpenSCAD migrant + manim cousin) until v1.0.
