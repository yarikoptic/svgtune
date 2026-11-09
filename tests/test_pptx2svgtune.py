"""Tests for pptx2svgtune: a PowerPoint slide -> layered SVG with links + .svgtune

Most tests build a minimal .pptx from the XML of the shapes they need
(make_pptx below), so that each feature is tested on its own; the files in
tests/data/ (made by PowerPoint, see tests/data/README.rst) check that real
presentations convert as expected.
"""
import base64
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import zipfile

import pytest
from lxml import etree

pytest.importorskip("PIL", reason="pptx2svgtune lays out text with Pillow")

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(TOP, 'pptx2svgtune')
SVGTUNE = os.path.join(TOP, 'svgtune')
DATA = os.path.join(TOP, 'tests', 'data')
NSMAP = {'s': 'http://www.w3.org/2000/svg',
         'i': 'http://www.inkscape.org/namespaces/inkscape',
         'x': 'http://www.w3.org/1999/xlink'}


def _load():
    loader = importlib.machinery.SourceFileLoader('pptx2svgtune', SCRIPT)
    spec = importlib.util.spec_from_loader('pptx2svgtune', loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


p2s = _load()


def _have_font():
    try:
        p2s.font("Arial", False, False)
        return True
    except SystemExit:
        return False


pytestmark = pytest.mark.skipif(not _have_font(), reason="needs fc-match and a font for Arial")

# --------------------------------------------------------------- building a .pptx
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
RT = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
XMLNS = f'xmlns:a="{A}" xmlns:p="{P}" xmlns:r="{R}"'
EMU = 12700  # per point

THEME = f"""<a:theme {XMLNS} name="Test"><a:themeElements>
<a:clrScheme name="Test">
<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="1F497D"/></a:dk2><a:lt2><a:srgbClr val="EEECE1"/></a:lt2>
<a:accent1><a:srgbClr val="4F81BD"/></a:accent1><a:accent2><a:srgbClr val="C0504D"/></a:accent2>
<a:accent3><a:srgbClr val="9BBB59"/></a:accent3><a:accent4><a:srgbClr val="8064A2"/></a:accent4>
<a:accent5><a:srgbClr val="4BACC6"/></a:accent5><a:accent6><a:srgbClr val="F79646"/></a:accent6>
<a:hlink><a:srgbClr val="0000FF"/></a:hlink><a:folHlink><a:srgbClr val="800080"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="Test"><a:majorFont><a:latin typeface="Arial"/></a:majorFont>
<a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Test"><a:fillStyleLst/><a:lnStyleLst>
<a:ln w="9525"/><a:ln w="25400"/><a:ln w="38100"/></a:lnStyleLst></a:fmtScheme>
</a:themeElements></a:theme>"""

_ids = iter(range(2, 10 ** 6))


def rels(*items):
    """Relationships part: items are (rId, type, target[, external])."""
    out = [f'<Relationships xmlns="{PKG}">']
    for rid, typ, target, *ext in items:
        mode = ' TargetMode="External"' if ext and ext[0] else ''
        out.append(f'<Relationship Id="{rid}" Type="{RT}{typ}" Target="{target}"{mode}/>')
    return ''.join(out) + '</Relationships>'


def make_pptx(path, *slides, links=(), media=(), size=(720, 540), background=''):
    """Write a minimal .pptx with the given slides (the XML within each <p:spTree>).

    links are (rId, URL) of hyperlinks and media (rId, name, bytes) of
    pictures, available to every slide.
    """
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml',
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        ids = ''.join(f'<p:sldId id="{256 + i}" r:id="rIdS{i}"/>' for i in range(len(slides)))
        z.writestr('ppt/presentation.xml',
                   f'<p:presentation {XMLNS}><p:sldIdLst>{ids}</p:sldIdLst>'
                   f'<p:sldSz cx="{size[0] * EMU}" cy="{size[1] * EMU}"/></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels', rels(
            *[(f'rIdS{i}', 'slide', f'slides/slide{i + 1}.xml') for i in range(len(slides))],
            ('rIdT', 'theme', 'theme/theme1.xml')))
        z.writestr('ppt/theme/theme1.xml', THEME)
        z.writestr('ppt/slideMasters/slideMaster1.xml',
                   f'<p:sldMaster {XMLNS}><p:cSld><p:spTree/></p:cSld>'
                   '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
                   'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
                   'accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:sldMaster>')
        z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels',
                   rels(('rId1', 'theme', '../theme/theme1.xml')))
        z.writestr('ppt/slideLayouts/slideLayout1.xml',
                   f'<p:sldLayout {XMLNS}><p:cSld><p:spTree/></p:cSld></p:sldLayout>')
        z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels',
                   rels(('rId1', 'slideMaster', '../slideMasters/slideMaster1.xml')))
        for name, data in [(m[1], m[2]) for m in media]:
            z.writestr(f'ppt/media/{name}', data)
        for i, tree in enumerate(slides):
            z.writestr(f'ppt/slides/slide{i + 1}.xml',
                       f'<p:sld {XMLNS}><p:cSld>{background}<p:spTree>'
                       '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                       f'<p:grpSpPr/>{tree}</p:spTree></p:cSld></p:sld>')
            z.writestr(f'ppt/slides/_rels/slide{i + 1}.xml.rels', rels(
                ('rIdL', 'slideLayout', '../slideLayouts/slideLayout1.xml'),
                *[(rid, 'hyperlink', url, True) for rid, url in links],
                *[(m[0], 'image', f'../media/{m[1]}') for m in media]))
    return path


def xfrm(x, y, w, h, attrs=''):
    return (f'<a:xfrm{attrs}><a:off x="{round(x * EMU)}" y="{round(y * EMU)}"/>'
            f'<a:ext cx="{round(w * EMU)}" cy="{round(h * EMU)}"/></a:xfrm>')


def sp(name, x, y, w, h, prst='rect', fill='FFFFFF', line='', text='', style='',
       cnvpr='', attrs='', av='', tag='sp'):
    """A shape (or with tag='cxnSp' a connector); fill/line are DrawingML XML or RGB."""
    fill_xml = (f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill and '<' not in fill
                else fill or '')
    nv = 'nvSpPr' if tag == 'sp' else 'nvCxnSpPr'
    cnv = 'cNvSpPr' if tag == 'sp' else 'cNvCxnSpPr'
    return (f'<p:{tag}><p:{nv}><p:cNvPr id="{next(_ids)}" name="{name}">{cnvpr}</p:cNvPr>'
            f'<p:{cnv}/><p:nvPr/></p:{nv}><p:spPr>{xfrm(x, y, w, h, attrs)}'
            f'<a:prstGeom prst="{prst}"><a:avLst>{av}</a:avLst></a:prstGeom>{fill_xml}{line}</p:spPr>'
            f'{style}{text}</p:{tag}>')


def ln(rgb='000000', w=1, dash=None, head=False, tail=False):
    return (f'<a:ln w="{round(w * EMU)}"><a:solidFill><a:srgbClr val="{rgb}"/></a:solidFill>'
            + (f'<a:prstDash val="{dash}"/>' if dash else '')
            + ('<a:headEnd type="triangle"/>' if head else '')
            + ('<a:tailEnd type="triangle"/>' if tail else '') + '</a:ln>')


def run(text, sz=None, b=False, i=False, rgb=None, link=None, font=None):
    attrs = (f' sz="{sz * 100}"' if sz else '') + (' b="1"' if b else '') + (' i="1"' if i else '')
    inner = ((f'<a:solidFill><a:srgbClr val="{rgb}"/></a:solidFill>' if rgb else '')
             + (f'<a:latin typeface="{font}"/>' if font else '')
             + (f'<a:hlinkClick r:id="{link}"/>' if link else ''))
    return f'<a:r><a:rPr lang="en-US"{attrs}>{inner}</a:rPr><a:t>{text}</a:t></a:r>'


def txt(*paras, anchor=None, wrap=None, algn=None):
    bp = (f' anchor="{anchor}"' if anchor else '') + (f' wrap="{wrap}"' if wrap else '')
    ppr = f'<a:pPr algn="{algn}"/>' if algn else ''
    return (f'<p:txBody><a:bodyPr{bp}/><a:lstStyle/>'
            + ''.join(f'<a:p>{ppr}{p}</a:p>' for p in paras) + '</p:txBody>')


def convert(tmp_path, *slides, cfg=None, slide=1, name='fig', **kw):
    src = make_pptx(tmp_path / f'{name}.pptx', *slides, **{k: v for k, v in kw.items()
                                                           if k in ('links', 'media', 'background')})
    out = tmp_path / f'{name}.svg'
    p2s.convert(src, out, slide, cfg, **{k: v for k, v in kw.items()
                                          if k in ('link_target', 'write_svgtune')})
    return etree.parse(str(out)).getroot(), out


def shape(svg, label):
    found = svg.xpath(f'//s:g[@i:label="{label}"]', namespaces=NSMAP)
    assert len(found) == 1, f'{label}: {len(found)} found'
    return found[0]


def layers(svg):
    return [(g.get('id'), g.get(f'{{{NSMAP["i"]}}}label'))
            for g in svg.xpath('s:g[@i:groupmode="layer"]', namespaces=NSMAP)]


# --------------------------------------------------------------- shapes
def test_shapes(tmp_path, capsys):
    svg, out = convert(tmp_path,
        sp('Box', 10, 20, 100, 50, fill='<a:solidFill><a:srgbClr val="FF0000"><a:alpha val="50000"/>'
           '</a:srgbClr></a:solidFill>', line=ln('00FF00', 2, dash='dash')) +
        sp('Pill', 10, 100, 100, 40, prst='roundRect', av='<a:gd name="adj" fmla="val 25000"/>') +
        sp('Dot', 200, 20, 60, 40, prst='ellipse', fill='<a:noFill/>', line=ln()) +
        sp('Arrow', 300, 50, 100, 0, prst='line', fill='', line=ln('0000FF', 2, tail=True)))
    assert 'wrote' in capsys.readouterr().out
    assert svg.get('width') == '720pt' and svg.get('viewBox') == '0 0 720 540'
    assert svg.find('s:title', NSMAP).text == 'fig'
    assert svg.find('s:rect[@id="background"]', NSMAP).get('fill') == '#ffffff'
    rect = shape(svg, 'Box').find('s:rect', NSMAP)
    assert (rect.get('x'), rect.get('y'), rect.get('width'), rect.get('height')) == ('10', '20', '100', '50')
    assert (rect.get('fill'), rect.get('fill-opacity')) == ('#FF0000', '0.5')
    assert (rect.get('stroke'), rect.get('stroke-width'), rect.get('stroke-dasharray')) == \
        ('#00FF00', '2', '8,6')
    assert shape(svg, 'Pill').find('s:rect', NSMAP).get('rx') == '10'  # 25% of the shorter side
    ellipse = shape(svg, 'Dot').find('s:ellipse', NSMAP)
    assert (ellipse.get('cx'), ellipse.get('rx'), ellipse.get('ry'), ellipse.get('fill')) == \
        ('230', '30', '20', 'none')
    line = shape(svg, 'Arrow').find('s:line', NSMAP)
    assert line.get('marker-end') == 'url(#arrow-0000ff)'
    assert float(line.get('x2')) == pytest.approx(395)  # shortened under the arrow head
    assert svg.find('s:defs/s:marker[@id="arrow-0000ff"]', NSMAP) is not None
    assert '<!-- Generated by pptx2svgtune from fig.pptx: edit those' in out.read_text()


def test_rotation_and_flips(tmp_path):
    svg, _ = convert(tmp_path,
        sp('Turned', 100, 100, 100, 50, attrs=' rot="5400000"') +
        sp('Down', 300, 100, 100, 50, prst='line', fill='', line=ln(), attrs=' flipV="1"'))
    assert shape(svg, 'Turned').get('transform') == 'rotate(90 150 125)'
    line = shape(svg, 'Down').find('s:line', NSMAP)
    assert [line.get(k) for k in ('x1', 'y1', 'x2', 'y2')] == ['300', '150', '400', '100']


def test_connectors(tmp_path, capsys):
    svg, _ = convert(tmp_path,
        sp('Both ends', 10, 10, 100, 0, prst='straightConnector1', fill='', tag='cxnSp',
           line=ln('C0504D', 1, head=True, tail=True)) +
        sp('Elbow', 100, 100, 200, 100, prst='bentConnector3', fill='', tag='cxnSp',
           line=ln(), attrs=' flipV="1"') +
        sp('Curve', 100, 300, 200, 100, prst='curvedConnector3', fill='', tag='cxnSp', line=ln()))
    line = shape(svg, 'Both ends').find('s:line', NSMAP)
    assert line.get('marker-start') == line.get('marker-end') == 'url(#arrow-c0504d)'
    assert float(line.get('x1')) == pytest.approx(12.5) and float(line.get('x2')) == pytest.approx(107.5)
    poly = shape(svg, 'Elbow').find('s:polyline', NSMAP)
    assert poly.get('points') == '100,200 200,200 200,100 300,100'
    assert not svg.xpath('//s:g[@i:label="Curve"]', namespaces=NSMAP)
    assert "'Curve': geometry curvedConnector3 not supported" in capsys.readouterr().err


def test_groups(tmp_path):
    group = (f'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{next(_ids)}" name="Group 1"/><p:cNvGrpSpPr/>'
             f'<p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm rot="5400000">'
             f'<a:off x="{100 * EMU}" y="{100 * EMU}"/><a:ext cx="{200 * EMU}" cy="{100 * EMU}"/>'
             f'<a:chOff x="0" y="0"/><a:chExt cx="{100 * EMU}" cy="{50 * EMU}"/></a:xfrm></p:grpSpPr>'
             + sp('Inside', 10, 10, 20, 10) + sp('Also inside', 50, 20, 10, 10) + '</p:grpSp>')
    svg, _ = convert(tmp_path, group + sp('Outside', 0, 0, 10, 10),
                     cfg={'steps': [['grouped', '^Group'], ['also', '^Also']]})
    inside = shape(svg, 'Inside')
    rect = inside.find('s:rect', NSMAP)
    # the group doubles its children and is rotated about its center
    assert [rect.get(k) for k in ('x', 'y', 'width', 'height')] == ['120', '120', '40', '20']
    assert inside.get('transform') == 'rotate(90 200 150)'
    # shapes in a group fall back to the step of the group
    assert layers(svg) == [('layer-grouped', 'grouped'), ('layer-also', 'also'),
                           ('layer-base', 'base')]


def test_picture(tmp_path):
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
    pic = (f'<p:pic><p:nvPicPr><p:cNvPr id="{next(_ids)}" name="Logo"><a:hlinkClick r:id="rIdH1"/>'
           f'</p:cNvPr><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rIdM1"/>'
           f'<a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>{xfrm(10, 10, 50, 40)}'
           '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
    svg, out = convert(tmp_path, pic, links=[('rIdH1', 'https://example.org/logo')],
                       media=[('rIdM1', 'image1.png', png)])
    a = shape(svg, 'Logo').find('s:a', NSMAP)
    assert a.get('href') == 'https://example.org/logo'
    image = a.find('s:image', NSMAP)
    assert image.get(f'{{{NSMAP["x"]}}}href') == 'data:image/png;base64,' + base64.b64encode(png).decode()
    assert image.get('width') == '50'
    assert 'xmlns:xlink=' in out.read_text()


def test_unsupported_reported(tmp_path, capsys):
    frame = (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{next(_ids)}" name="Table 1"/>'
             '<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr></p:graphicFrame>')
    placeholder = (f'<p:sp><p:nvSpPr><p:cNvPr id="{next(_ids)}" name="Title 1"/><p:cNvSpPr/>'
                   '<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/>'
                   + txt(run('Title')) + '</p:sp>')
    svg, _ = convert(tmp_path, frame + placeholder + sp('Triangle', 0, 0, 10, 10, prst='triangle')
                     + sp('Kept', 0, 0, 10, 10))
    err = capsys.readouterr().err
    assert "'Table 1' (<graphicFrame>): not supported, skipped" in err
    assert "'Title 1': placeholder without a position of its own" in err
    assert "'Triangle': geometry triangle not supported, skipped" in err
    assert [g.get(f'{{{NSMAP["i"]}}}label') for g in svg.xpath('//s:g[not(@i:groupmode)]', namespaces=NSMAP)] \
        == ['Kept']


# --------------------------------------------------------------- colors
def test_theme_colors_and_styles(tmp_path):
    style = ('<p:style><a:lnRef idx="2"><a:schemeClr val="accent1"><a:shade val="50000"/></a:schemeClr>'
             '</a:lnRef><a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef>'
             '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
             '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style>')
    lighter = ('<a:solidFill><a:schemeClr val="accent1"><a:lumMod val="60000"/><a:lumOff val="40000"/>'
               '</a:schemeClr></a:solidFill>')
    svg, _ = convert(tmp_path,
        sp('Styled', 10, 10, 100, 50, fill='', style=style, text=txt(run('Hi'))) +
        sp('Lighter', 10, 100, 100, 50, fill=lighter) +
        sp('Text color', 10, 200, 100, 50, fill='',
           text=txt('<a:r><a:rPr><a:solidFill><a:schemeClr val="tx2"/></a:solidFill></a:rPr>'
                    '<a:t>tx2</a:t></a:r>' + '<a:r><a:rPr/><a:t> default</a:t></a:r>')),
        background='<p:bg><p:bgPr><a:solidFill><a:schemeClr val="accent6"/></a:solidFill></p:bgPr></p:bg>')
    rect = shape(svg, 'Styled').find('s:rect', NSMAP)
    assert rect.get('fill') == '#4F81BD'  # fillRef: accent1
    # lnRef 2: 2 pt wide, in accent1 shaded by 50% (in linear RGB, as PowerPoint shows it)
    assert rect.get('stroke') == '#385D8A' and rect.get('stroke-width') == '2'
    assert shape(svg, 'Styled').find('.//s:tspan', NSMAP).get('fill') == '#FFFFFF'  # fontRef: lt1
    assert shape(svg, 'Lighter').find('s:rect', NSMAP).get('fill') == '#95B3D7'  # as PowerPoint shows it
    assert [t.get('fill') for t in shape(svg, 'Text color').iter(f'{{{NSMAP["s"]}}}tspan')] == \
        ['#1F497D', '#000000']  # tx2 is dk2; no color is tx1, i.e. dk1
    assert svg.find('s:rect[@id="background"]', NSMAP).get('fill') == '#f79646'


# --------------------------------------------------------------- text
def test_text_layout(tmp_path):
    words = ' '.join(['word'] * 12)
    svg, _ = convert(tmp_path,
        sp('Wrapped', 10, 10, 120, 200, text=txt(run(words), algn='ctr')) +
        sp('Styles', 200, 10, 300, 100, text=txt(
            run('bold', b=True) + run(' and ') + run('italic', i=True) + '<a:br><a:rPr/></a:br>'
            + run('after a break', sz=12, font='Courier New'))) +
        sp('Bottom', 10, 300, 300, 100, text=txt(run('low'), anchor='b')) +
        sp('No wrap', 10, 420, 20, 40, text=txt(run(words), wrap='none')))
    lines = shape(svg, 'Wrapped').findall('s:text', NSMAP)
    assert len(lines) > 2 and {t.get('text-anchor') for t in lines} == {'middle'}
    assert all(t.get('x') == '70' for t in lines)  # center of the box
    assert ' '.join(''.join(t.itertext()) for t in lines) == words
    styled = shape(svg, 'Styles').findall('s:text', NSMAP)
    assert len(styled) == 2
    spans = styled[0].findall('s:tspan', NSMAP)
    assert [s.text for s in spans] == ['bold', ' and ', 'italic']
    assert spans[0].get('font-weight') == 'bold' and spans[2].get('font-style') == 'italic'
    after = styled[1].find('s:tspan', NSMAP)
    assert after.get('font-size') == '12'
    assert after.get('font-family') == "'Courier New', 'Liberation Mono', monospace"
    assert svg.get('font-family') == "Arial, 'Liberation Sans', Helvetica, sans-serif"
    low = shape(svg, 'Bottom').find('s:text', NSMAP)
    assert 380 < float(low.get('y')) < 400
    assert len(shape(svg, 'No wrap').findall('s:text', NSMAP)) == 1


# --------------------------------------------------------------- links
def test_links_from_slide(tmp_path, capsys):
    svg, _ = convert(tmp_path,
        sp('Linked box', 10, 10, 100, 50, cnvpr='<a:hlinkClick r:id="rIdH1"/>', text=txt(run('box'))) +
        sp('Linked word', 10, 100, 300, 50, text=txt(run('see ') + run('this', link='rIdH2'))) +
        sp('Jump', 10, 200, 100, 50, text=txt(run('next', link='rIdL'))),
        links=[('rIdH1', 'https://example.org/box'), ('rIdH2', 'https://example.org/word')])
    box = shape(svg, 'Linked box')
    assert box.find('s:a', NSMAP).get('href') == 'https://example.org/box'
    assert box.find('s:a', NSMAP).get('target') == '_blank'
    # the text of a linked shape is linked too
    assert box.find('s:text/s:a', NSMAP).get('href') == 'https://example.org/box'
    word = shape(svg, 'Linked word').findall('.//s:a', NSMAP)
    assert [(a.get('href'), ''.join(a.itertext())) for a in word] == [('https://example.org/word', 'this')]
    assert not shape(svg, 'Jump').findall('.//s:a', NSMAP)  # rIdL is the slide layout
    assert 'is not to a URL: ignored' in capsys.readouterr().err


def test_links_from_config(tmp_path):
    cfg = {'links': {'Formats': {'HDF5': 'https://hdf', 'Zarr v3': 'https://zarr', '_': 'https://all'},
                     'Plain': 'https://plain'}}
    svg, _ = convert(tmp_path,
        sp('Formats', 10, 10, 300, 50, text=txt(run('HDF5 (files) · Zarr v3'))) +
        sp('Plain', 10, 100, 100, 50), cfg=cfg, link_target='')
    links = [(a.get('href'), ''.join(a.itertext())) for a in shape(svg, 'Formats').iter(f'{{{NSMAP["s"]}}}a')]
    assert links == [('https://all', ''), ('https://hdf', 'HDF5'), ('https://all', ' (files) · '),
                     ('https://zarr', 'Zarr v3')]
    plain = shape(svg, 'Plain').find('s:a', NSMAP)
    assert plain.get('href') == 'https://plain' and plain.get('target') is None
    with pytest.raises(SystemExit, match='link phrases not found'):
        convert(tmp_path, sp('Formats', 10, 10, 300, 50, text=txt(run('HDF5'))),
                cfg={'links': {'Formats': {'NetCDF': 'https://x'}}})
    with pytest.raises(SystemExit, match='links for shapes not in the slide'):
        convert(tmp_path, sp('Formats', 10, 10, 300, 50), cfg={'links': {'Missing': 'https://x'}})


# --------------------------------------------------------------- steps
def test_steps_layers_and_svgtune(tmp_path):
    cfg = {'steps': [['b', '^B'], ['a', '^A']], 'walkthrough': ['a', 'b'],
           'split': {'Path': {'at': [150], 'steps': ['a', 'b']}}}
    svg, out = convert(tmp_path,
        sp('Title', 0, 0, 100, 20) + sp('A1', 0, 50, 10, 10) + sp('B1', 50, 50, 10, 10)
        + sp('A2', 100, 50, 10, 10)
        + sp('Path', 100, 100, 100, 0, prst='line', fill='', line=ln(tail=True)), cfg=cfg)
    # the z-order of the slide is kept, so step "a" has two layers
    assert layers(svg) == [('layer-base', 'base'), ('layer-a', 'a'), ('layer-b', 'b'),
                           ('layer-a-2', 'a'), ('layer-b-2', 'b')]
    segments = svg.xpath('//s:g[@i:label="Path"]', namespaces=NSMAP)
    assert [g.get('id') for g in segments] == ['path-1', 'path-2']
    assert segments[0].find('s:line', NSMAP).get('marker-end') is None
    assert segments[1].find('s:line', NSMAP).get('marker-end') == 'url(#arrow-000000)'
    tune = out.with_suffix('.svgtune').read_text().splitlines()
    assert tune[0].startswith('# Generated by pptx2svgtune')
    assert [t for t in tune if t.startswith('%save')] == ['%save base', '%save a', '%save b']
    assert 'layer label:re=^a$ style=display:inline' in tune
    # svgtune makes one SVG per step, each with the steps so far
    subprocess.run([sys.executable, SVGTUNE, out.with_suffix('.svgtune').name], cwd=tmp_path,
                   check=True, capture_output=True)
    tuned = tmp_path / 'fig_tuned'
    assert sorted(os.listdir(tuned)) == ['a.svg', 'b.svg', 'base.svg']
    shown = etree.parse(str(tuned / 'a.svg')).getroot()
    visible = [g.get(f'{{{NSMAP["i"]}}}label') for g in shown.xpath('s:g[@i:groupmode="layer"]', namespaces=NSMAP)
               if 'display:inline' in g.get('style')]
    assert visible == ['base', 'a', 'a']


def test_svgtune_kept_when_edited(tmp_path, capsys):
    convert(tmp_path, sp('Box', 0, 0, 10, 10))
    tune = tmp_path / 'fig.svgtune'
    tune.write_text('%file fig.svg\n# my edits\n')
    convert(tmp_path, sp('Box', 0, 0, 10, 10))
    assert tune.read_text() == '%file fig.svg\n# my edits\n'
    assert 'kept' in capsys.readouterr().out
    convert(tmp_path, sp('Box', 0, 0, 10, 10), name='other', write_svgtune=False)
    assert (tmp_path / 'other.svg').exists() and not (tmp_path / 'other.svgtune').exists()


# --------------------------------------------------------------- command line
def test_command_line(tmp_path):
    yaml = pytest.importorskip('yaml')
    make_pptx(tmp_path / 'deck.pptx', sp('One', 0, 0, 10, 10), sp('Two', 0, 0, 10, 10) + sp('Second', 20, 0, 10, 10))
    cfg = tmp_path / 'deck.yaml'
    cfg.write_text(yaml.safe_dump({'source': 'deck.pptx', 'slide': 2, 'title': 'Deck: slide 2',
                                   'steps': [['later', '^Second$']]}))
    res = subprocess.run([sys.executable, SCRIPT, '-c', str(cfg)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert 'wrote' in res.stdout
    svg = etree.parse(str(tmp_path / 'deck-slide2.svg')).getroot()
    assert svg.find('s:title', NSMAP).text == 'Deck: slide 2'
    assert layers(svg) == [('layer-base', 'base'), ('layer-later', 'later')]
    assert (tmp_path / 'deck-slide2.svgtune').exists()
    # without a configuration, to a given file, without .svgtune
    res = subprocess.run([sys.executable, SCRIPT, str(tmp_path / 'deck.pptx'), '-o',
                          str(tmp_path / 'one.svg'), '--no-svgtune'], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert (tmp_path / 'one.svg').exists() and not (tmp_path / 'one.svgtune').exists()
    res = subprocess.run([sys.executable, SCRIPT, str(tmp_path / 'deck.pptx'), '--slide', '3'],
                         capture_output=True, text=True)
    assert res.returncode != 0 and 'no slide 3 (it has 2)' in res.stderr
    res = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True)
    assert res.returncode == 2 and 'give a .pptx file' in res.stderr


# --------------------------------------------------------------- files made by PowerPoint
def real(tmp_path, name, slide=1):
    out = tmp_path / f'{name}-{slide}.svg'
    p2s.convert(os.path.join(DATA, f'{name}.pptx'), out, slide, write_svgtune=False)
    return etree.parse(str(out)).getroot()


def test_real_font_colors(tmp_path):
    svg = real(tmp_path, 'font-color')
    fills = [t.get('fill') for t in svg.iter(f'{{{NSMAP["s"]}}}tspan')]
    assert fills[:3] == ['#000000', '#FF6600', '#4F81BD']  # none, RGB, theme accent1
    assert fills[4] == '#95B3D7'  # accent1, 40% lighter, as PowerPoint shows it
    # accent4, 25% darker: PowerPoint shows 5F497A; within rounding
    darker = [int(fills[3][i:i + 2], 16) for i in (1, 3, 5)]
    assert all(abs(c - e) <= 1 for c, e in zip(darker, (0x5F, 0x49, 0x7A)))
    assert svg.get('font-family') == 'Calibri, Carlito, sans-serif'  # the theme's font


def test_real_connector_and_picture(tmp_path):
    svg = real(tmp_path, 'shp-connector-props')
    line = shape(svg, 'Straight Arrow Connector 2').find('s:line', NSMAP)
    assert (line.get('stroke'), line.get('stroke-width')) == ('#4F81BD', '2')  # from the theme
    assert line.get('marker-end') == 'url(#arrow-4f81bd)'
    svg = real(tmp_path, 'shp-connector-props', slide=2)
    image = shape(svg, 'Picture 1').find('s:image', NSMAP)
    assert image.get(f'{{{NSMAP["x"]}}}href').startswith('data:image/jpeg;base64,')


def test_real_group(tmp_path, capsys):
    svg = real(tmp_path, 'shp-groupshape')
    assert shape(svg, 'Rounded Rectangle 1').find('s:rect', NSMAP).get('fill') == '#4F81BD'
    assert shape(svg, 'Oval 2').find('s:ellipse', NSMAP) is not None
    assert "'Isosceles Triangle 3': geometry triangle not supported" in capsys.readouterr().err


def test_real_text_and_link(tmp_path, capsys):
    svg = real(tmp_path, 'txt-text')
    box = shape(svg, 'TextBox 1')
    assert [''.join(t.itertext()) for t in box.findall('s:text', NSMAP)] == \
        ['Foo Bar', 'Baz Zoo', '1', 'yahoo.com']  # line breaks, a field (slide number), a link
    assert box.find('.//s:a', NSMAP).get('href') == 'http://yahoo.com'
    assert len(shape(svg, 'TextBox 2').findall('s:text', NSMAP)) == 4  # abc / a / b / c
    real(tmp_path, 'txt-text', slide=2)
    assert "'Table 1' (<graphicFrame>): not supported, skipped" in capsys.readouterr().err
