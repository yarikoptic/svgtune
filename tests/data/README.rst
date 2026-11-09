Test data
=========

``*.pptx`` here are PowerPoint files from the test suite of python-pptx
(https://github.com/scanny/python-pptx, ``features/steps/test_files/`` at
commit 278b47b1, 2024-08-07),
used unchanged to test ``pptx2svgtune`` on files made by PowerPoint itself:

``font-color.pptx``
  text without a color, in an RGB color, and in theme colors (also darker
  and lighter)
``shp-connector-props.pptx``
  a straight arrow connector styled by the theme; slide 2: a picture
``shp-groupshape.pptx``
  a group of shapes styled by the theme, one of them a triangle (not
  supported)
``txt-text.pptx``
  text with line breaks, a field (slide number), and a hyperlink; slide 2: a
  table (not supported)

They are distributed under the license of python-pptx:

  The MIT License (MIT)
  Copyright (c) 2013 Steve Canny, https://github.com/scanny

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
