"""End-to-end tests for svgtune: run it on small documents, inspect results"""
import os
import shutil
import subprocess
import sys

import pytest
from lxml import etree

SVGTUNE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'svgtune')
INKSCAPE = os.environ.get('INKSCAPE', 'inkscape')
SVG_NS = 'http://www.w3.org/2000/svg'
INK_NS = 'http://www.inkscape.org/namespaces/inkscape'

needs_inkscape = pytest.mark.skipif(
    not shutil.which(INKSCAPE), reason="needs inkscape")

SVG = """\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
   xmlns:xlink="http://www.w3.org/1999/xlink"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="200mm" height="100mm" viewBox="0 0 200 100" id="svg1">
  <defs id="defs1">
    <linearGradient id="grad1"><stop offset="0" style="stop-color:red"/></linearGradient>
    <linearGradient id="grad2" xlink:href="#grad1"/>
    <linearGradient id="grad3"><stop offset="0" style="stop-color:blue"/></linearGradient>
    <style id="style1">*{stroke-linecap:square;}</style>
  </defs>
  <g id="layer1" inkscape:groupmode="layer" inkscape:label="Layer 1"
     transform="translate(10,5)">
    <g id="g-top" inkscape:label="TOP">
      <rect id="r1" x="10" y="10" width="20" height="10" style="fill:url(#grad2)"/>
    </g>
    <g id="g-top-extra" inkscape:label="TOP-EXTRA">
      <rect id="r2" x="40" y="10" width="20" height="10" style="fill:green"/>
    </g>
    <g id="g-bottom" inkscape:label="BOTTOM">
      <rect id="r3" x="100" y="60" width="40" height="20" style="fill:blue"/>
      <rect id="r4" x="150" y="60" width="10" height="10" style="fill:url(#grad3)"/>
    </g>
  </g>
  <g id="layer2" inkscape:groupmode="layer" inkscape:label="Hidden"
     style="display:none">
    <rect id="r5" x="0" y="0" width="5" height="5"/>
  </g>
  <text id="text1" xml:space="preserve" x="5" y="95"><tspan id="ts1">A</tspan><tspan
    id="ts2" style="font-weight:bold">B</tspan> tail</text>
  <use id="clone1" xlink:href="#r5" x="50" y="50"/>
</svg>
"""


@pytest.fixture
def run(tmp_path):
    """Run svgtune on given instructions; return function to load results"""
    svgfile = tmp_path / 'fig.svg'
    svgfile.write_text(SVG)

    def _run(instructions, expect_fail=False, args=(), env=None):
        tunefile = tmp_path / 'fig.svgtune'
        tunefile.write_text(instructions)
        res = subprocess.run([sys.executable, SVGTUNE] + list(args)
                             + [str(tunefile)],
                             cwd=str(tmp_path), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True,
                             env=dict(os.environ, **(env or {})))
        if expect_fail:
            assert res.returncode != 0
            return res.stderr
        assert res.returncode == 0, res.stderr
        return lambda name: etree.parse(
            str(tmp_path / 'fig_tuned' / (name + '.svg'))).getroot()
    return _run


def by_id(root, id_):
    found = root.xpath('//*[@id=$id]', id=id_)
    return found[0] if found else None


def style(root, id_):
    return by_id(root, id_).get('style') or ''


def test_save_preserves_text(run, tmp_path):
    load = run("%save same\n")
    out = (tmp_path / 'fig_tuned' / 'same.svg').read_bytes()
    assert out.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    # no whitespace injected between tspans
    assert b'>A</tspan><tspan' in out
    assert etree.tostring(load('same')) == etree.tostring(
        etree.fromstring(SVG.encode()))


def test_legacy_commands(run):
    load = run("""\
# comment
layers style=display:none
%save 0
layer label=Hidden style=display:inline;opacity:0.5
g id=g-top style=display:none
g label:re=^TOP style=fill:red
any label=BOTTOM style=opacity:0.3
%save 1
""")
    r = load('0')
    assert 'display:none' in style(r, 'layer1')
    assert 'display:none' in style(r, 'layer2')
    r = load('1')
    assert 'display:none' in style(r, 'layer1')
    assert style(r, 'layer2') == 'display:inline;opacity:0.5'
    assert style(r, 'g-top') == 'display:none;fill:red'
    assert style(r, 'g-top-extra') == 'fill:red'
    assert style(r, 'g-bottom') == 'opacity:0.3'


def test_transform(run):
    load = run("""\
g label=TOP transform=translate(1,2)
layer id=layer1 transform=scale(2)
%save moved
""")
    r = load('moved')
    assert by_id(r, 'g-top').get('transform') == 'translate(1,2)'
    assert by_id(r, 'layer1').get('transform') == 'scale(2) translate(10,5)'


def test_save_first_without_file(run):
    # used to not save at all if %save was the first command
    load = run("%save first\n")
    assert load('first') is not None


def test_reset(run):
    load = run("""\
g id=g-top style=display:none
%save hidden
%reset
%save restored
""")
    assert 'display:none' in style(load('hidden'), 'g-top')
    assert 'display:none' not in style(load('restored'), 'g-top')


def test_only(run):
    load = run("""\
%only label:re=^TOP
%save top
%reset
%only id=r3 label=Hidden
%save r3
""")
    r = load('top')
    assert 'display:inline' in style(r, 'layer1')
    assert 'display:inline' in style(r, 'g-top')
    assert 'display:inline' in style(r, 'g-top-extra')
    assert 'display:none' in style(r, 'g-bottom')
    assert 'display:none' in style(r, 'layer2')
    assert 'display:none' in style(r, 'text1')
    assert 'display:none' in style(r, 'clone1')
    # children of what is kept are not touched
    assert style(r, 'r1') == 'fill:url(#grad2)'
    # non-rendered elements are not touched
    assert by_id(r, 'defs1').get('style') is None

    r = load('r3')
    assert 'display:inline' in style(r, 'g-bottom')
    assert 'display:none' in style(r, 'r4')
    assert 'display:none' in style(r, 'g-top')
    # hidden layer got shown
    assert 'display:inline' in style(r, 'layer2')


def test_selection_failures(run, tmp_path):
    assert 'Cannot find any victim' in run(
        "%only id=nonexistent\n", expect_fail=True)
    assert 'Unknown identifier' in run(
        "%only class=foo\n", expect_fail=True)
    (tmp_path / 'fig.svg').write_text(SVG.replace('"TOP-EXTRA"', '"TOP"'))
    assert 'single victim' in run("%only label=TOP\n", expect_fail=True)
    # but fine with a regular expression
    run("%only label:re=^TOP$\n")


def test_prune(run):
    load = run("""\
%only label=TOP
%prune
%save pruned
""")
    r = load('pruned')
    for id_ in ('r2', 'r3', 'r4', 'g-bottom', 'text1', 'ts1', 'grad3'):
        assert by_id(r, id_) is None, id_
    # still used directly or indirectly
    for id_ in ('r1', 'grad1', 'grad2', 'style1'):
        assert by_id(r, id_) is not None, id_
    # hidden but referenced by a clone, which got pruned itself, so
    # eventually removed as well
    assert by_id(r, 'layer2') is None


def test_prune_keeps_referenced(run):
    load = run("""\
%prune
%save pruned
""")
    r = load('pruned')
    # hidden layer is referenced by the visible clone
    assert by_id(r, 'layer2') is not None
    assert by_id(r, 'r5') is not None
    assert by_id(r, 'grad3') is not None


def test_prune_keeps_text_tail(run):
    load = run("""\
any id=ts2 style=display:none
%prune
%save pruned
""")
    r = load('pruned')
    assert by_id(r, 'ts2') is None
    assert ''.join(by_id(r, 'text1').itertext()) == 'A tail'


def test_crop_box(run):
    load = run("""\
%crop box=10,20,30,40
%save box
%crop box=10,20,30,40 margin=5
%save box_margin
""")
    r = load('box')
    assert r.get('viewBox') == '10 20 30 40'
    assert r.get('width') == '30mm'
    assert r.get('height') == '40mm'
    r = load('box_margin')
    assert r.get('viewBox') == '5 15 40 50'
    assert r.get('width') == '40mm'


def bbox(root):
    return [float(x) for x in root.get('viewBox').split()]


@needs_inkscape
def test_crop_elements(run):
    load = run("""\
%crop id=r1
%save r1
%crop label=TOP label=BOTTOM margin=1
%save union
%only label=BOTTOM
%crop
%save visible
%crop id=r4
%save r4
""")
    assert bbox(load('r1')) == pytest.approx([20, 15, 20, 10], abs=1e-3)
    r = load('r1')
    assert r.get('width') == '20mm'
    assert r.get('height') == '10mm'
    assert bbox(load('union')) == pytest.approx([19, 14, 152, 72], abs=1e-3)
    # cropping to visible drawing (and cropping again from an already
    # cropped document with non-0 viewBox origin)
    assert bbox(load('visible')) == pytest.approx([110, 65, 60, 20], abs=1e-3)
    assert bbox(load('r4')) == pytest.approx([160, 65, 10, 10], abs=1e-3)


@needs_inkscape
def test_crop_no_viewbox(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100">'
        '<rect id="r1" x="60" y="30" width="20" height="10"/>'
        '<rect id="r2" x="100" y="50" width="20" height="10"/></svg>')
    load = run("%crop id=r2 margin=2\n%save r2\n")
    r = load('r2')
    assert bbox(r) == pytest.approx([98, 48, 24, 14], abs=1e-3)
    assert r.get('width') == '24'
    assert r.get('height') == '14'


def test_any_does_not_match_root(run):
    load = run("any id:re=. style=opacity:0.5\n%save all\n")
    r = load('all')
    assert r.get('style') is None
    assert style(r, 'layer1') == 'opacity:0.5'


def test_only_ignores_not_rendered(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<linearGradient id="grad3">',
        '<linearGradient id="grad3" inkscape:label="BOTTOM-gradient">'))
    load = run("%only label:re=^BOTTOM\n%save bottom\n")
    r = load('bottom')
    assert by_id(r, 'defs1').get('style') is None
    assert by_id(r, 'grad3').get('style') is None
    assert 'display:inline' in style(r, 'g-bottom')
    assert 'display:none' in style(r, 'g-top')
    assert 'None of the selected elements is rendered' in run(
        "%only label=BOTTOM-gradient\n", expect_fail=True)


def test_prune_self_references(run, tmp_path):
    # hidden subtree referencing only itself (e.g. clone, textPath within)
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<rect id="r4"', '<use id="clone2" xlink:href="#r3"/><rect id="r4"'))
    load = run("g id=g-bottom style=display:none\n%prune\n%save pruned\n")
    r = load('pruned')
    for id_ in ('g-bottom', 'r3', 'clone2', 'grad3'):
        assert by_id(r, id_) is None, id_


def test_prune_keeps_style(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<rect id="r4"', '<style id="style2">.x{fill:red}</style><rect id="r4"'))
    load = run("g id=g-bottom style=display:none\n%prune\n%save pruned\n")
    r = load('pruned')
    assert by_id(r, 'g-bottom') is None
    style2 = by_id(r, 'style2')
    assert style2.text == '.x{fill:red}'
    # took the place of the removed group
    assert style2.getparent().get('id') == 'layer1'
    assert style2.getprevious().get('id') == 'g-top-extra'


def test_crop_percentage_size(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        'viewBox="10 0 100 50"><rect id="r1" x="20" y="10" width="30" '
        'height="10"/></svg>')
    load = run("%crop box=1,2,3,4\n%save box\n")
    r = load('box')
    assert r.get('viewBox') == '1 2 3 4'
    assert r.get('width') == '100%'
    if shutil.which(INKSCAPE):
        load = run("%crop id=r1\n%save r1\n")
        assert bbox(load('r1')) == pytest.approx([20, 10, 30, 10], abs=1e-3)


@needs_inkscape
def test_crop_nonuniform_scale(run, tmp_path):
    # aspect ratio of width/height differs from the one of viewBox
    (tmp_path / 'fig.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100" '
        'viewBox="0 0 100 100"><rect id="r1" x="10" y="10" width="20" '
        'height="10"/></svg>')
    r = run("%crop id=r1\n%save r1\n")('r1')
    assert bbox(r) == pytest.approx([10, 10, 20, 10], abs=1e-3)
    assert (r.get('width'), r.get('height')) == ('80', '10')


@needs_inkscape
def test_crop_repeatedly(run, tmp_path):
    # used to fail due to rounding of width/height in other units
    (tmp_path / 'fig.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="2in" height="1in" '
        'viewBox="0 0 192 96"><rect id="r" x="10" y="10" width="20" '
        'height="10"/></svg>')
    load = run("%crop box=0,0,50.3,30.7\n%crop id=r margin=1\n%save r\n")
    r = load('r')
    assert bbox(r) == pytest.approx([9, 9, 22, 12], abs=1e-3)
    assert r.get('width') == fmt_in(22 / 96)
    assert r.get('height') == fmt_in(12 / 96)


def fmt_in(v):
    return ('%.6f' % v).rstrip('0') + 'in'


@needs_inkscape
def test_crop_cleans_up(run, tmp_path):
    # elements without id get temporary ids, and Inkscape pages get removed
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<g id="g-top" ', '<g ').replace(
        '<defs id="defs1">',
        '<sodipodi:namedview xmlns:sodipodi="http://sodipodi.sourceforge.net/'
        'DTD/sodipodi-0.dtd" id="nv"><inkscape:page x="0" y="0" width="200" '
        'height="100" id="page1"/></sodipodi:namedview><defs id="defs1">'))
    load = run("%crop label=TOP\n%save top\n")
    out = (tmp_path / 'fig_tuned' / 'top.svg').read_text()
    assert 'svgtune-tmp' not in out
    assert 'inkscape:page' not in out
    assert bbox(load('top')) == pytest.approx([20, 15, 20, 10], abs=1e-3)


def test_only_nested_matches(run, tmp_path):
    # matches within other matches are left untouched along with the rest
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<rect id="r1"',
        '<g id="nested" inkscape:label="TOP-nested" style="display:none"/>'
        '<rect id="r1"'))
    r = run("%only label:re=^TOP\n%save top\n")('top')
    assert style(r, 'r1') == 'fill:url(#grad2)'
    assert style(r, 'nested') == 'display:none'
    assert 'display:none' in style(r, 'g-bottom')


def test_only_keeps_clone_original(run, tmp_path):
    # original of a clone is a sibling of the selected group
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<g id="g-bottom"',
        '<use id="clone2" xlink:href="#g-top-extra"/><g id="g-bottom"'
    ).replace('<g id="g-top-extra"', '<g id="g-top-extra" '
              'style="opacity:0.5"'))
    load = run("""\
%only id=clone2
%save only
%prune
%save pruned
""")
    for name in ('only', 'pruned'):
        r = load(name)
        extra = by_id(r, 'g-top-extra')
        assert extra.getparent().tag == '{%s}defs' % SVG_NS
        assert 'display:none' not in style(r, 'g-top-extra')
        assert 'display:none' not in style(r, 'r2')
    assert 'display:none' in style(load('only'), 'g-top')
    assert by_id(load('pruned'), 'g-top') is None
    # not referenced anymore once clone is hidden and pruned
    r = run("%only id=r1\n%prune\n%save r1\n")('r1')
    assert by_id(r, 'g-top-extra') is None


def test_errors_report_line(run):
    err = run("# comment\n\n%only id=nonexistent\n", expect_fail=True)
    assert 'fig.svgtune:3: Cannot find any victim' in err
    assert 'Traceback' not in err
    err = run("%crop margin=5mm\n", expect_fail=True)
    assert 'fig.svgtune:1: ' in err
    assert 'Traceback' not in err
    err = run("%only id=r1\n%crop\n", expect_fail=True,
              env={'INKSCAPE': 'nonexistent-inkscape'})
    assert 'fig.svgtune:2: ' in err and 'nonexistent-inkscape' in err
    assert 'Traceback' not in err


def test_no_parameters_expected(run):
    assert 'takes no parameters' in run("%reset all\n", expect_fail=True)
    assert 'takes no parameters' in run("%prune all\n", expect_fail=True)


def test_regex_matches_missing_attribute(run):
    # as in 0.3.1: a regular expression matching an empty string selects
    # also elements without the attribute
    r = run("text label:re=^ style=opacity:0.5\n%save x\n")('x')
    assert style(r, 'text1') == 'opacity:0.5'


def test_layer_is_not_any_group(run):
    assert 'Cannot find any victim' in run(
        "layer label=TOP style=opacity:0.5\n", expect_fail=True)


def test_href_identifiers(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<use id="clone1"', '<use id="clone-plain" href="#r1"/><use id="clone1"'))
    r = run("any href=#r5 style=opacity:0.1\n"
            "any href=#r1 style=opacity:0.2\n%save x\n")('x')
    assert style(r, 'clone1') == 'opacity:0.1'
    assert style(r, 'clone-plain') == 'opacity:0.2'


def test_prune_hidden_attribute_and_css_refs(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<rect id="r2"', '<rect id="r2" display="none"').replace(
        '*{stroke-linecap:square;}', '.x{fill:url(#grad3)}').replace(
        ' style="fill:url(#grad3)"', ' class="x"'))
    r = run("%prune\n%save pruned\n")('pruned')
    assert by_id(r, 'r2') is None
    assert by_id(r, 'grad3') is not None


def test_prune_keeps_whitespace_in_text(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<tspan\n    id="ts2" style="font-weight:bold">B</tspan> tail',
        '<tspan id="ts2" style="display:none">B</tspan> <tspan>C</tspan>'))
    r = run("%prune\n%save pruned\n")('pruned')
    assert ''.join(by_id(r, 'text1').itertext()) == 'A C'


def test_options(run, tmp_path):
    # fake Inkscape which just creates the file to export to
    fake = tmp_path / 'fake-inkscape'
    fake.write_text('#!/bin/sh\nfor a; do case "$a" in --export-filename=*) '
                    'touch "${a#--export-filename=}";; esac; done\n')
    fake.chmod(0o755)
    run("%save first\n%exit\n%save never\n", args=['-p'],
        env={'INKSCAPE': str(fake)})
    out = sorted(os.listdir(str(tmp_path / 'fig_tuned')))
    assert out == ['first.svg', 'first_preview.png']
    shutil.rmtree(str(tmp_path / 'fig_tuned'))
    run("%options previews\n%save first\n", args=['--no-svgs'],
        env={'INKSCAPE': str(fake)})
    assert os.listdir(str(tmp_path / 'fig_tuned')) == ['first_preview.png']
    # .svg within a directory name
    os.mkdir(str(tmp_path / 'a.svg.d'))
    shutil.copy(str(tmp_path / 'fig.svg'), str(tmp_path / 'a.svg.d'))
    run("%file a.svg.d/fig.svg\n%save first\n", args=['-p'],
        env={'INKSCAPE': str(fake)})
    assert sorted(os.listdir(str(tmp_path / 'a.svg.d' / 'fig_tuned'))) == \
        ['first.svg', 'first_preview.png']


def test_errors_file_level(tmp_path):
    res = subprocess.run([sys.executable, SVGTUNE, 'nonexistent.svgtune'],
                         cwd=str(tmp_path), stderr=subprocess.PIPE,
                         universal_newlines=True)
    assert res.returncode
    assert res.stderr.startswith('nonexistent.svgtune: ')


def test_invalid_viewbox(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        'viewBox="0 0 200 100"', 'viewBox="0 0 200"'))
    err = run("%crop box=1,2,3,4\n", expect_fail=True)
    assert 'fig.svgtune:1: Cannot handle viewBox' in err


def test_only_moves_only_originals_of_visible_clones(run, tmp_path):
    # clone2 (of g-top-extra) gets hidden as well, and r2 is referenced
    # only by something which is not a clone, so nothing gets moved
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<g id="g-bottom"',
        '<use id="clone2" xlink:href="#g-top-extra"/>'
        '<path id="connector" inkscape:connection-start="#r3" d="M0,0"/>'
        '<g id="g-bottom"'))
    r = run("%only id=r1\n%save r1\n")('r1')
    assert by_id(r, 'g-top-extra').getparent().get('id') == 'layer1'
    assert 'display:none' in style(r, 'g-top-extra')
    assert by_id(r, 'g-bottom').getparent().get('id') == 'layer1'
    assert 'display:none' in style(r, 'g-bottom')


def test_only_moves_in_document_order(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<text id="text1"',
        '<use id="c1" xlink:href="#g-bottom"/>'
        '<use id="c2" xlink:href="#g-top-extra"/>'
        '<use id="c3" xlink:href="#layer2"/><text id="text1"'))
    r = run("%only id=g-top id=c1 id=c2 id=c3\n%save x\n")('x')
    defs = by_id(r, 'defs1')
    assert [e.get('id') for e in defs][-3:] == \
        ['g-top-extra', 'g-bottom', 'layer2']


def test_prune_keeps_nested_fonts(run, tmp_path):
    (tmp_path / 'fig.svg').write_text(SVG.replace(
        '<rect id="r4"',
        '<font id="font1"><font-face id="ff1" font-family="F"/></font>'
        '<rect id="r4"'))
    r = run("g id=g-bottom style=display:none\n%prune\n%save x\n")('x')
    assert by_id(r, 'g-bottom') is None
    assert by_id(r, 'ff1').getparent().get('id') == 'font1'


@needs_inkscape
def test_crop_small_units(run, tmp_path):
    # precision is relative to the size of the document
    (tmp_path / 'fig.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10cm" height="10cm" '
        'viewBox="0 0 1 1"><rect id="r" x="0.12345" y="0.23456" '
        'width="0.2" height="0.1"/></svg>')
    r = run("%crop id=r\n%save r\n")('r')
    assert r.get('viewBox') == '0.12345 0.23456 0.2 0.1'
    assert r.get('width') == '2cm'
