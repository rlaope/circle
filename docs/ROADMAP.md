# circlelib — Roadmap

> Strategic context: see [STRATEGY.md](STRATEGY.md).
> Architecture overview: see [ARCHITECTURE.md](ARCHITECTURE.md).

Each milestone targets **one concrete user pain or one new audience**.
Resist mixing them.

## v0.2 — "OpenSCAD migrants don't bounce off in the first hour"

Target: existing OpenSCAD users who hit the language wall.

- [ ] Variables and arithmetic expressions (`size = 5; Cube(width=size*2, ...)`)
- [ ] `Plane` primitive
- [ ] `Cone` primitive
- [ ] Extra color formats: `rgba`, `rgb(r, g, b)`, named CSS-style colors
- [ ] `--export-png <path>` headless offscreen render (offscreen FBO)
- [ ] CI workflow on GitHub Actions: pytest + headless render of every example, attach a preview PNG to PR comments
- [ ] VSCode extension scaffolding (syntax highlighting + snippets)

## v0.3 — "Animations as first-class citizens"

Target: manim-adjacent educators and explainer-video creators.

- [ ] AST `animate { ... }` block + grammar rule
- [ ] Time variable `t` and tween functions: `linear`, `ease_in`, `ease_out`, `ease_in_out`, `bounce`
- [ ] Keyframe interpolation: `anim(t, from, to, duration)`
- [ ] CLI `circlelib record scene.crl --duration 5 --out clip.mp4` (ffmpeg pipe)
- [ ] Gallery of 6 demos (planet orbit, sorting visualization, matrix rotation, signal waveform, …)

## v0.4 — "Share scenes anywhere on the web"

Target: creative coders, educators, and content authors.

- [ ] Three.js export: `circlelib export scene.crl --target=threejs --out=site/`
- [ ] glTF export
- [ ] Static-site bundler that emits an `<iframe>`-able HTML page per scene
- [ ] mkdocs project documentation site

## v0.5 — "Live coding"

Target: live coders, lecturers demoing in real time.

- [ ] File watcher with auto re-evaluation
- [ ] Camera state preserved across reloads
- [ ] Helpful error overlays inside the window

## v0.6 — "Reusable assets"

Target: returning users who want to compose with prior work.

- [ ] Standard library `stdlib/` (furniture, vehicles, data-structures, geometry helpers)
- [ ] `circlelib install <pkg>` from GitHub URLs (no central registry yet)

## v1.0 — "Stable, packaged, marketed"

- [ ] Freeze grammar + Python API
- [ ] PyPI release
- [ ] Homebrew tap
- [ ] 60-second tour video

## Beyond v1.0 (decided after market signal)

- Collider / simple physics for game prototyping
- Node-based GUI editor (optional companion)
- Custom GLSL shader slots
- WebAssembly build (Pyodide or partial Rust port)

---

## 90-day execution plan (S-tier)

| Week | Output |
|------|--------|
| 1–2  | Ship v0.2 (variables/arithmetic, Plane, Cone, named colors, `--export-png`, CI) |
| 3–6  | Ship v0.3 (animate block, record CLI, gallery of 6) |
| 7    | Launch posts on HN + 4 Reddit subs + manim Discord |
| 8–11 | Ship v0.4 (Three.js export + docs site) |
| 12   | Second launch wave (explainer creators) |
| 13   | Retrospective: stars, contributors, external use cases |

### 90-day success metrics
- ≥ 200 GitHub stars
- ≥ 3 external contributors with merged non-trivial PRs
- ≥ 5 outside-authored "Made with circlelib" posts/videos
- v0.4 shipped on time
