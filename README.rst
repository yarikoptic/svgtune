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

You can match elements either by 'id' or 'label', or use python
regular expressions to match sets of those::

  layer label:re=^base.* style=display:inline


============
COMMAND LINE
============

See ./svgtune --help for more information on command line parameters.

======
OUTPUT
======

For the results, look under somefigure_tuned/ directory.

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

  %_tuned: %.svgtune ignore-%_tuned
  	@echo "Tuning SVG using $<"
  	@svgtune $<

  %.pdf: %.svg ignore-%.pdf
  	@echo "Rendering $@"
  	@inkscape -z -f "$<" -A "$@"

  %.eps: %.svg ignore-%.eps
  	@echo "Rendering $@"
  	@inkscape -z -T -f "$<" -E "$@"

