"""Tests for slides2svgtune: HTML slides -> layered SVG + .svgtune"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys

import pytest
from lxml import etree

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(TOP, 'slides2svgtune')
SVGTUNE = os.path.join(TOP, 'svgtune')
SVG_NS = 'http://www.w3.org/2000/svg'
INK_NS = 'http://www.inkscape.org/namespaces/inkscape'
XLINK_NS = 'http://www.w3.org/1999/xlink'


def _load():
    loader = importlib.machinery.SourceFileLoader('slides2svgtune', SCRIPT)
    spec = importlib.util.spec_from_loader('slides2svgtune', loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


s2s = _load()


def _have_chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


needs_chromium = pytest.mark.skipif(
    not _have_chromium(), reason="needs Playwright with Chromium")


# A slide exercising: base content, named steps, a step named only via
# inheritance, an unnamed step, an element leaving early, a connector,
# links, a rotated label, collapsed whitespace and speaker notes.
SLIDE = """\
<section id="s1" style="background:transparent; font-family:sans-serif">
  <div style="position:absolute; top:0; left:0; width:1920px; height:200px; background:#eeeeee"></div>
  <p style="position:absolute; top:40px; left:40px; width:600px; height:40px; font-size:30px">Base  ·  <a href="https://example.org/base"><span style="color:#123456">linked</span></a></p>
  <p style="position:absolute; top:400px; left:20px; width:200px; height:40px; font-size:24px; transform:rotate(-90deg)">Rotated</p>
  <div id="alpha--box" data-build-in="fade 1" style="position:absolute; top:300px; left:300px; width:200px; height:100px; background:#ffffff; border:2px solid #333333; border-radius:12px">
    <p style="font-size:24px">Alpha</p>
  </div>
  <x-connector data-build-in="fade 1" x1="500" y1="350" x2="700" y2="350" style="color:#2f5d9e; border-width:3px"></x-connector>
  <p id="beta--chip" data-build-in="fade 2" style="position:absolute; top:300px; left:700px; width:200px; height:40px; font-size:24px"><a href="https://example.org/beta"><span style="color:#000000">Beta</span></a></p>
  <p data-build-in="fade 2" data-build-out="fade 3" style="position:absolute; top:600px; left:700px; width:200px; height:40px; font-size:24px">Temporary</p>
  <p id="gamma--x" data-build-in="fade 3" style="position:absolute; top:300px; left:1000px; width:200px; height:40px; font-size:24px">Gamma</p>
  <p data-build-in="fade 4" style="position:absolute; top:300px; left:1300px; width:200px; height:40px; font-size:24px">Unnamed</p>
  <aside>Speaker notes must not show up</aside>
</section>
"""

PLAIN = """\
<section id="s2" style="background:transparent">
  <p style="position:absolute; top:40px; left:40px; width:600px; height:40px; font-size:30px">No steps here</p>
</section>
"""


@pytest.fixture
def deck(tmp_path):
    d = tmp_path / 'deck'
    (d / 'slides').mkdir(parents=True)
    (d / 'deck.json').write_text(json.dumps({"v": 4, "order": ["s1", "s2"]}))
    (d / 'slides' / 's1.html').write_text(SLIDE)
    (d / 'slides' / 's2.html').write_text(PLAIN)
    return d


def _layers(svgfile):
    doc = etree.parse(str(svgfile))
    return [(g.get('{%s}label' % INK_NS), g)
            for g in doc.getroot().iter('{%s}g' % SVG_NS)
            if g.get('{%s}groupmode' % INK_NS) == 'layer']


def _shown(svgfile):
    """Labels of layers which are not hidden"""
    return {lab for lab, g in _layers(svgfile)
            if 'display:none' not in (g.get('style') or '')}


# --- pure logic, no browser needed ---

def _items(*specs):
    return [dict(name=n, inn=i, out=o, svg='', bbox=b)
            for n, i, o, b in specs]


def test_name_steps_inherit_fallback_and_early_out():
    items = _items(
        (None, None, None, (0, 0, 1, 1)),        # base
        ('alpha', 1, None, (0, 0, 1, 1)),
        (None, 1, None, (0, 0, 1, 1)),           # inherits "alpha"
        (None, 2, None, (0, 0, 1, 1)),           # unnamed -> build-2
        (None, 2, 3, (0, 0, 1, 1)),              # leaves early -> build-2~gamma
        ('gamma', 3, None, (0, 0, 1, 1)),
    )
    plan = s2s.name_steps(items)
    assert [it['name'] for it in items] == [
        'base', 'alpha', 'alpha', 'build-2', 'build-2~gamma', 'gamma']
    assert plan == [
        (1, ['alpha'], []),
        (2, ['build-2', 'build-2~gamma'], []),
        (3, ['gamma'], ['build-2~gamma']),
    ]
    assert [s2s.step_label(s, h) for _, s, h in plan] == [
        'alpha', 'build-2', 'gamma']


def test_name_steps_whole_step_leaving_keeps_its_name():
    items = _items(('sync', 1, 2, (0, 0, 1, 1)), (None, 1, 2, (0, 0, 1, 1)),
                   ('next', 2, None, (0, 0, 1, 1)))
    plan = s2s.name_steps(items)
    assert [it['name'] for it in items] == ['sync', 'sync', 'next']
    assert plan == [(1, ['sync'], []), (2, ['next'], ['sync'])]


def test_regroup_respects_overlaps():
    a1 = dict(name='a', bbox=(0, 0, 10, 10))
    b = dict(name='b', bbox=(20, 0, 30, 10))       # does not overlap a2
    c = dict(name='c', bbox=(40, 0, 60, 10))       # overlaps a2
    a2 = dict(name='a', bbox=(50, 0, 55, 10))
    a3 = dict(name='a', bbox=(100, 0, 110, 10))    # overlaps nothing
    # a2 cannot jump over c (they overlap), so it stays after it
    assert [i['name'] for i in s2s.regroup([a1, b, c, a2])] == ['a', 'b', 'c', 'a']
    # a3 can join a1
    assert [i['name'] for i in s2s.regroup([a1, b, c, a3])] == ['a', 'a', 'b', 'c']


def test_build_svgtune_without_base():
    items = _items(('alpha', 1, None, (0, 0, 1, 1)))
    plan = s2s.name_steps(items)
    tune = s2s.build_svgtune('x', items, plan)
    assert 'base' not in tune
    assert '%save alpha' in tune


def test_font_faces(tmp_path):
    for n in ('IBMPlexSans-Regular.woff2', 'IBMPlexSans-BoldItalic.ttf',
              'IBMPlexMono-SemiBold.woff', 'README.txt', 'odd.woff2'):
        (tmp_path / n).write_text('')
    css = s2s.font_faces(tmp_path)
    assert css.count('@font-face') == 3
    assert "font-family:'IBM Plex Sans'" in css
    assert "font-weight:700;font-style:italic" in css
    assert "font-family:'IBM Plex Mono'" in css and "font-weight:600" in css


# --- end to end, with Chromium ---

@needs_chromium
def test_convert(deck, tmp_path):
    out = tmp_path / 'out'
    res = subprocess.run([sys.executable, SCRIPT, str(deck), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert (out / 's1.svg').exists() and (out / 's1.svgtune').exists()
    # a slide without build steps: an SVG only
    assert (out / 's2.svg').exists() and not (out / 's2.svgtune').exists()
    assert not list(out.glob('.*.html'))

    labels = [lab for lab, _ in _layers(out / 's1.svg')]
    assert set(labels) == {'base', 'alpha', 'beta', 'beta~gamma', 'gamma',
                           'build-4'}

    doc = etree.parse(str(out / 's1.svg')).getroot()
    texts = ''.join(t.text or '' for t in doc.iter('{%s}text' % SVG_NS))
    for word in ('Base', 'linked', 'Alpha', 'Beta', 'Gamma', 'Rotated'):
        assert word in texts
    assert 'Speaker notes' not in texts
    assert '  ' not in texts            # HTML-collapsed whitespace
    hrefs = {a.get('{%s}href' % XLINK_NS) for a in doc.iter('{%s}a' % SVG_NS)}
    assert hrefs == {'https://example.org/base', 'https://example.org/beta'}
    # the rotated label keeps a rotation
    assert any('matrix' in (g.get('transform') or '')
               for g in doc.iter('{%s}g' % SVG_NS))
    # the connector became a polyline with an arrow head
    assert doc.find('.//{%s}polyline' % SVG_NS) is not None

    tune = (out / 's1.svgtune').read_text()
    saves = [line.split()[1] for line in tune.splitlines()
             if line.startswith('%save')]
    assert saves == ['base', 'alpha', 'beta', 'gamma', 'build-4']


@needs_chromium
def test_convert_then_svgtune(deck, tmp_path):
    out = tmp_path / 'out'
    s2s.convert(deck, out, slides=['s1'], log=lambda *a: None)
    assert not (out / 's2.svg').exists()
    res = subprocess.run([sys.executable, SVGTUNE, 's1.svgtune'], cwd=str(out),
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    tuned = out / 's1_tuned'
    assert sorted(p.stem for p in tuned.glob('*.svg')) == sorted(
        ['base', 'alpha', 'beta', 'gamma', 'build-4'])
    assert _shown(tuned / 'base.svg') == {'base'}
    assert _shown(tuned / 'alpha.svg') == {'base', 'alpha'}
    assert _shown(tuned / 'beta.svg') == {'base', 'alpha', 'beta', 'beta~gamma'}
    # the temporary element left at "gamma"
    assert _shown(tuned / 'gamma.svg') == {'base', 'alpha', 'beta', 'gamma'}
    assert _shown(tuned / 'build-4.svg') == {'base', 'alpha', 'beta', 'gamma',
                                             'build-4'}
