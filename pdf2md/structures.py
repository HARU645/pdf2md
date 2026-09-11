# -*- coding: utf-8 -*-
"""What the converter has been shown, so it can say when it meets something new.

Every mistake this converter has made was the same mistake: a piece of the page
it had never been taught about went past without a word.  A bullet list, a
speech example's number, a table used to draw a box -- each one read as nothing
and left no trace, because the converter only reports on what it recognises.

So it keeps a list of what it recognises.  Anything outside the list is said
out loud, and the answer is either 'that is fine, add it' or 'that is a hole'.
The point is not that the list is right; it is that a page can no longer
introduce something in silence.

To add to the list, convert the documents and read what it complains about.
"""
from __future__ import annotations

#: Elements the converted output accounts for.
KNOWN_TAGS = frozenset("""
a b div em h2 h4 h6 img li ol p span sub sup table tbody td thead tr u ul
h1 h3 h5 strong i br
""".split())

#: What the VISK pages call the parts of a section.  Grouped the way the
#: converter treats them, not the way the page's stylesheet lists them.
KNOWN_CLASSES = frozenset("""
pykala murupolku pykotsikko pupupykotsikko pupupykalainfo heading

kappale kappale_noindent maaritelma sisus spacer katkos

huom huomkappale huomnumero

esimerkkiryhma esim_sisalto esim_marginaali puhe-esim_marginaali
esimerkki esimnum esimkomm otsikko_esim otsikko_esimryhma tekstiesimerkki
puhe_esimerkki puherivi puhuja vuoro aines num

asetelma asetelma_iso taulukko taulukkokommentti kuviokommentti palstoitus
solu soluu rivi tausta tausta2 tekstisolu otsikko_tekstisolu apu meta
sanalista lista

kielenaines kielenaines_eikap kasite korostus korostus_anaf lihavointi paino
indeksitermi kielindeksitermi ipa unicode ylaindeksi alaindeksi

kuva kuvio lahde kirjallisuusviite nolink
""".split())


def unfamiliar(parts) -> list:
    """Everything in `parts` that this converter has never been shown.

    `parts` is (tag, classes) for each element in the body.  Reported rather
    than guessed at: a name it does not know may be a synonym for something it
    already handles, or a part of the page it drops on the floor, and only a
    person reading that page can tell which.
    """
    tags, classes = set(), set()
    for tag, cls in parts:
        if tag not in KNOWN_TAGS:
            tags.add(tag)
        classes |= set(cls) - KNOWN_CLASSES
    return ["<%s>" % t for t in sorted(tags)] + sorted(classes)
