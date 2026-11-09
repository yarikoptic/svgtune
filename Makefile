MANPAGE=svgtune.1

all: $(MANPAGE)

%.1: %
	help2man -n "Tune and generate multiple SVGs out of source SVG" \
		-s 1 -N -o $@ ./$<

# TODO: before the Debian package ships slides2svgtune and pptx2svgtune
# (installed below), they need manpages (help2man needs a --version option,
# and the -n text of the %.1 rule above is svgtune's), and as Recommends:
# python3-playwright (only in sid) for slides2svgtune; python3-pil,
# python3-yaml, and fonts-liberation for pptx2svgtune.
# See https://github.com/yarikoptic/svgtune/pull/9
install: $(MANPAGE)
	mkdir -p  $(PREFIX)/usr/bin
	mkdir -p  $(PREFIX)/usr/share/man/man1
	install -t $(PREFIX)/usr/bin/ svgtune slides2svgtune pptx2svgtune
	install -t $(PREFIX)/usr/share/man/man1/ $(MANPAGE)

clean:
	rm -f $(MANPAGE)
