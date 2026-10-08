---
name: export-to-svgtuned-svg
description: Export HTML slides (e.g. a Claude Slides deck) with click/build steps into one editable, layered SVG per slide plus svgtune instructions, and from them one SVG per build step with stable semantic names. Use when asked for editable/vector SVG exports of slides or figures, or for per-step SVGs.
---

# Export slides to svgtune-ready SVGs

Turns a deck of HTML slides into:

- `<slide>.svg`: one editable SVG per slide (text stays text, links stay links and open in a new tab, also when embedded with `<object>`), with one Inkscape layer per build step, named after the step;
- `<slide>.svgtune`: svgtune instructions which recreate every build step;
- `<slide>_tuned/<step>.svg`: one SVG per build step, after running svgtune.

The tools are `slides2svgtune` and `svgtune` from https://github.com/yarikoptic/svgtune.

## 1. Get the deck files

The deck layout is `deck.json` (with `order`: the slide ids) and `slides/<id>.html` (one 1920x1080 `<section>` per slide).

- **Claude Slides artifact:** read `project/deck.json` and every `project/slides/<id>.html` listed in `order` with the Artifact tool (`action: "read"`, `paths: [...]`). They are saved under one folder; its `project/` subfolder is the deck directory.
- **Files from the user:** a folder (or zip) with the same layout.

## 2. Set up the tools

```sh
git clone --depth 1 https://github.com/yarikoptic/svgtune   # or update an existing clone
pip install --break-system-packages lxml playwright         # if not installed yet
python3 -m playwright install chromium                      # skip if Chromium is preinstalled
```

**Fonts matter.** Text positions are measured with the fonts Chromium uses. The same fonts must be installed for anything that later renders the SVGs (Inkscape, browsers), or the text will overlap.

- Find the families in `deck.json` `faces` and in the slides' `font-family`.
- Debian/Ubuntu: `apt install fonts-ibm-plex` (for IBM Plex), or similar packages.
- Without apt: `npm i @ibm/plex-sans @ibm/plex-mono`. Pass `--fonts node_modules/@ibm` to `slides2svgtune`. For system-wide use (e.g. to render the SVGs for checking), convert the `.woff` files to TTF into `~/.fonts` with fontTools, then run `fc-cache -f`:
  ```python
  from fontTools.ttLib import TTFont
  t = TTFont(src); t.flavor = None; t.save(dst_ttf)
  ```
- `--web-fonts` loads the deck's Google Fonts directly. This needs network access, and only covers Chromium, not later viewers.
- If the slides do not set a font themselves, pass the deck's main family via `--font "'IBM Plex Sans', sans-serif"`.

## 3. Convert and tune

```sh
svgtune/slides2svgtune <deck dir> out --fonts <dir>      # optionally: slide ids to limit
cd out && for t in *.svgtune; do ../svgtune/svgtune "$t"; done
```

The converter prints the steps of each slide, e.g. `base participants nwb ... stamped`. Steps named `build-<N>` are unnamed; see section 5.

## 4. Check before delivering

- Render every `out/<slide>_tuned/*.svg` with Playwright (open the file, take a screenshot) and combine them into a contact sheet in step order, the order of the `%save` lines. Look at it: each step should add exactly what the deck's click adds, and elements with `data-build-out` should disappear on their step.
- Count links: `grep -o '<a ' out/<slide>.svg | wc -l` should match the slide's `<a href>` count.
- Garbled or overlapping text almost always means fonts are missing in the renderer, not a conversion bug.

Deliver `out/` as a zip (SVGs, `.svgtune`, `_tuned/`). Mention that the same fonts must be installed to view or edit the SVGs.

## 5. Naming steps (when making or editing slides)

Build steps are `data-build-in="fade N"` / `data-build-out="fade N"` on a slide's top-level elements. To get stable output names:

- Give **one** element of each build step an id `<step>--<part>`, e.g. `id="hed--chip"`. Other elements of the same step inherit the name. Step names: short, lowercase, `[a-z0-9-]`.
- Elements without build attributes form the `base` layer.
- Elements that leave before the rest of their step (`data-build-out`) automatically get their own layer `<step>~<later-step>`. No need to name them.
- Unnamed steps fall back to `build-<N>`, which changes when steps are inserted. Name them instead.
- When the user adds a step, add the id in the deck (not in the SVG or the `.svgtune`), because both are regenerated from the deck.

Hand-editing: the generated `.svgtune` is plain svgtune. Copy it, or `%include` it when svgtune supports that, to add extracts with `%only`, `%prune` and `%crop`.
