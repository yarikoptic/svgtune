.. -*- mode: rst; fill-column: 78; indent-tabs-mode: nil -*-
.. ex: set sts=4 ts=4 sw=4 et tw=79:

===========
DESCRIPTION
===========

svgtune is just a little helper to generate a set of .svg files out of
a single .svg file, by tuning respective groups/layers visibility,
transparency or anything else.

It might come very handy for generation of incremental figures to be
embedded into the presentation.  For the input, this takes a single
command line parameter -- file with instructions, which might look
like::

  # Load the file we should use
  %file somefigure.svg

  # Make all layers invisible
  layers style=display:none
  # Store current state into 0_blank file
  %save 0_blank

  layer label=elements style=display:inline
  %save 1

  layer id=layer2 style=display:inline
  %save 1_3

  # Lets make some group visible
  g id=g14546 style=display:inline
  %save 1_3

You can match elements either by 'id', 'label' (inkscape:label), or 'href',
or use python regular expressions to match sets of those::

  layer label:re=^base.* style=display:inline

Besides 'layers', 'layer' and 'g', 'text' and 'any' (any element) can be
used to select elements.  Without a regular expression, a single element must
match.  Since parameters are separated by spaces, values cannot contain
spaces: use a regular expression to match e.g. ``label:re=^Layer.1$``, and
commas in transforms, e.g. ``transform=translate(10,20)``.

Changes could be done to

style
  values (e.g. ``style=display:none;opacity:0.5``) are merged into the
  element's style.
transform
  the value is prepended to the element's transform, so e.g.
  ``transform=translate(10,20)`` moves the element by 10,20 in the
  coordinates of its parent.

=====================================
EXTRACTING PARTS OF A (LARGE) FIGURE
=====================================

Following directives help to produce "extracts" (e.g. a single panel without
the rest of a poster), which get regenerated whenever the original figure
changes::

  %file poster.svg

  # Leave visible only these (and their ancestors), hide everything else
  %only label=PANEL-A label:re=^arrows-
  # Remove all hidden elements and then definitions nothing refers to
  %prune
  # Fit the page to the visible drawing, with a margin of 5 (user units)
  %crop margin=5
  %save panel-a

  # Start again from the original poster
  %reset
  ...

%reset
  reload the figure, discarding all the changes done so far.
%only <identifier> [<identifier> ...]
  leave visible only the matching elements: all their siblings, and siblings
  of their ancestors, get hidden (display:none), while they and their
  ancestors get shown (display:inline).  Hidden elements which are referenced
  (e.g. originals of clones) are moved into <defs> instead, so references
  keep working.  Anything within the matching elements is left untouched.
  Matching elements which are not rendered directly (e.g. within <defs>) are
  ignored.
%prune
  remove hidden (display:none) elements, unless they (or any of their
  descendants) are referenced from elsewhere (e.g. by a clone), and then
  unused definitions (gradients, markers, etc).  <style>, <script>, <font>,
  and <color-profile> elements are kept.
%crop [<identifier> ...] [margin=<m>]
  crop the page to the bounding box of the matching elements or, if none
  given, of the visible drawing.  Matching elements are used even if hidden,
  so e.g. a rectangle on a hidden layer could serve as a frame to crop to
  (crop before ``%prune``, which would remove it).
  Bounding boxes are computed by Inkscape (``inkscape --query-all``), so
  text is accounted for properly.  Only the viewBox, width and height of the
  document change (and Inkscape pages, if any, are removed).
%crop box=<x>,<y>,<width>,<height> [margin=<m>]
  crop the page to the given area (in user units).


============
COMMAND LINE
============

See ./svgtune --help for more information on command line parameters.

======
OUTPUT
======

For the results, look under somefigure_tuned/ directory.

============
REQUIREMENTS
============

Python 3 with lxml.  Inkscape (1.x) is needed only for previews and
``%crop`` (unless ``box=`` is given).  The INKSCAPE environment variable can
point to the Inkscape executable to use.

Tests (in tests/) can be run with ``python3 -m pytest tests``.

=======
Helpers
=======

You might make advantage of having following in your Makefile, so you get
automatic 'tuning' and rendering of 'pdf' and 'eps' of your .svg's for easy
embedding them into your publications::

  all:: pics

  # For every .svg we must have a pdf
  PICS=$(shell find . -iname \*svg | sed -e 's/svg/pdf/g')
  SVGIS=$(shell /bin/ls *.svgtune | sed -e 's/.svgtune/_tuned/g')

  FMAKE := $(MAKE) -s -f $(lastword $(MAKEFILE_LIST))

  pics: $(SVGIS) $(PICS)

  clean::
  	for p in *.svg; do rm -f $${p%*.svg}.{pdf,eps}; done

  ignore-%:
  	@grep -q "^$*$$" .gitignore || { \
  	  echo "$*" >> .gitignore; echo "Ignore $@"; }

  %_tuned: %.svgtune %.svg ignore-%_tuned
  	@echo "Tuning SVG using $<"
  	@svgtune $<
  	@touch "$@"

  %.pdf: %.svg ignore-%.pdf
  	@echo "Rendering $@"
  	@inkscape --export-type=pdf --export-filename="$@" "$<"

  %.eps: %.svg ignore-%.eps
  	@echo "Rendering $@"
  	@inkscape --export-type=eps --export-text-to-path --export-filename="$@" "$<"
