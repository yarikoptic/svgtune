MANPAGE=svgtune.1

all: $(MANPAGE)

%.1: %
	help2man -n "Tune and generate multiple SVGs out of source SVG" \
		-s 1 -N -o $@ ./$<

install: $(MANPAGE)
	mkdir -p  $(PREFIX)/usr/bin
	mkdir -p  $(PREFIX)/usr/share/man/man1
	install -t $(PREFIX)/usr/bin/ svgtune
	install -t $(PREFIX)/usr/share/man/man1/ $(MANPAGE)

clean:
	rm -f $(MANPAGE)
