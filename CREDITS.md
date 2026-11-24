# Credits

readmefetch's code is MIT licensed. The art it bundles was made by other people and
keeps its own licence. Every SVG readmefetch writes names the artist and licence of
each logo it uses (as XML comments and in the image description), so the credit
travels with the picture. Please keep it if you share an SVG.

| Logos | Artist / authors | Source | Licence | Changes made by readmefetch |
| --- | --- | --- | --- | --- |
| `drone`, `pot` | readmefetch | this repository | MIT | (original art) |
| `linux`, `arch`, `debian`, `ubuntu`, `fedora`, `macos`, `windows`, `nixos`, `raspbian`, `android`, `mint`, `pop`, `kali`, `gentoo`, `manjaro`, `freebsd`, `alpine`, `opensuse` | the fastfetch contributors; much of it originally by the neofetch contributors | [fastfetch](https://github.com/fastfetch-cli/fastfetch/tree/e09925d303dfc1d3cb35b977017d65c9c1704366/src/logo/ascii) © 2021-2023 Linus Dierheimer, © 2022-2026 Carter Li; [neofetch](https://github.com/dylanaraps/neofetch) © 2015-2021 Dylan Araps | MIT ([fastfetch](src/readmefetch/art/fastfetch/LICENSE), [neofetch](src/readmefetch/art/fastfetch/LICENSE.neofetch)) | colours mapped to the chosen theme |
| `tux` | as `linux` above | as above | MIT | blinking eyes |
| `python`, `javascript`, `typescript`, `php`, `java`, `lua`, `rust`, `go`, `html`, `css`, `sass`, `vue`, `c`, `cpp`, `csharp`, `ruby`, `kotlin`, `swift`, `dart`, `bash`, `docker` | the onefetch contributors | [onefetch `languages.yaml`](https://github.com/o2sh/onefetch/blob/8b63584a505a3225ff85dc7144c910eb48f5c12a/languages.yaml) © 2018 Ossama Hjaji | MIT ([licence](src/readmefetch/art/onefetch/LICENSE)) | none |
| `cauldron` | **dixsept** | [Candy Box 2](https://github.com/candybox2/candybox2.github.io/blob/35301d438aa2c1e58e8cb3ea215b0af323bddf9b/ascii/places/cauldron/cauldron.txt) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) ([notice](src/readmefetch/art/candybox2/LICENSE.md)) | colours, bubbles and fire animation |
| `computer` | **aniwey** | [Candy Box 2](https://github.com/candybox2/candybox2.github.io/blob/35301d438aa2c1e58e8cb3ea215b0af323bddf9b/ascii/general/theComputer/computer.txt) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) ([notice](src/readmefetch/art/candybox2/LICENSE.md)) | cropped to the monitor, coloured, animated screen |
| `banner` fonts `standard`, `slant`, `small`, `smslant`, `big` | **Glenn Chappell** (all five) and **Ian Chai** (standard); later edits by John Cowan, Paul Burton and Bruce Jakeway, as each font's header records | [FIGlet](https://github.com/cmatsuoka/figlet/tree/202a0a8110650a943f1125f536b3bb455cf72ee1/fonts) © 1991-1994 Glenn Chappell & Ian Chai, © 1996-2001 John Cowan, © 2002 Christiaan Keet, © 2011 Claudio Matsuoka | BSD-3-Clause ([licence](src/readmefetch/art/figlet/LICENSE)) | none (fonts copied unmodified) |
| `banner` font `tubes` | **Phantomwise** | [Phantomwise/ascii](https://github.com/Phantomwise/ascii/blob/c0a4c06e6477f1fbedfa186a1c66f575b08dac74/figfonts/Tubes-Regular.flf) | CC0 1.0 ([licence](src/readmefetch/art/figlet/LICENSE.tubes)) | none |

Third-party files are copied byte for byte from the pinned commits above by
[`tools/vendor_art.py`](tools/vendor_art.py), so anyone can check them against upstream.

## Badges

The badge icons (`globe`, `mail`, `game`, `cards`, `tree` and the rest) are original
drawings made for readmefetch, under its MIT licence. The badge shapes follow the common
shields.io styles. The gradients of `flat` and `plastic` use the same stop values as
[shields.io's badge-maker](https://github.com/badges/shields/tree/master/badge-maker)
(CC0-1.0). Text widths come from Verdana's advance widths at 11 px.

## Icons

The `:icons:` in info lines and badges are drawn as SVG shapes copied from free icon
sets, the same sets Nerd Fonts patches into its fonts. They are pinned to the releases
below and refreshed by [`tools/vendor_icons.py`](tools/vendor_icons.py). Shapes are
copied as they are, except that colours are dropped (an icon takes the colour of its
text) and coordinates are rounded to one or two decimals. Every SVG that uses an icon
names its set and licence in a comment.

| Icons | Source | Licence |
| --- | --- | --- |
| GitHub's own icons (`repo`, `star`, `git-pull-request`, `flame`, ...) | [Octicons](https://github.com/primer/octicons) 19.42.0 © GitHub Inc. | MIT ([licence](src/readmefetch/art/icons/LICENSE.octicons)) |
| Brand logos (`python`, `docker`, `archlinux`, ...) | [Simple Icons](https://github.com/simple-icons/simple-icons) 16.38.1 | CC0 1.0 ([licence](src/readmefetch/art/icons/LICENSE.simple-icons), [disclaimer](src/readmefetch/art/icons/DISCLAIMER.simple-icons)) |
| Logos Simple Icons lacks, or licenses separately (`rust`, `php`, `vuejs`, `bash`, `csharp`, `java`, ...) | [Devicon](https://github.com/devicons/devicon) 2.18.0 © konpa and the Devicon contributors | MIT ([licence](src/readmefetch/art/icons/LICENSE.devicon)) |
| Linux distributions and desktops (`archlinux`, `debian`, `gnome`, ...) | [font-logos](https://github.com/lukas-w/font-logos) v1.4.0 | the Unlicense ([licence](src/readmefetch/art/icons/LICENSE.font-logos)) |
| `nf-*` names and codepoints (for `:nf-dev-python:` and `print --nerd-font`) | [Nerd Fonts](https://github.com/ryanoasis/nerd-fonts) v3.5.1 `glyphnames.json` | MIT ([licence](src/readmefetch/art/icons/LICENSE.nerd-fonts)); no font files are included |

Simple Icons is CC0, but some of its logos carry their owners' own licence (CC BY-SA,
GPL, non-commercial and others), as its data file records. readmefetch bundles none of
those: it uses Devicon's drawing of the same logo, or leaves the logo out.

## Share-alike art

The Candy Box 2 pieces are CC BY-SA 3.0, not MIT. An SVG or GIF that shows `cauldron`
or `computer` is an adaptation of that art, so it is shared under CC BY-SA 3.0 too, with
the artist credited. readmefetch writes that notice into the SVG for you.

## Trademarks

The operating-system, programming-language and brand logos (ASCII art and icons alike)
are trademarks of their owners. They are included, as in fastfetch, onefetch and Nerd
Fonts, so people can show the tools they use.
Their use here does not mean those owners endorse readmefetch.

## Finding more art

If you add your own logo (see [Custom logos](README.md#custom-logos)), credit its artist
in the logo's `credit` field. readmefetch keeps that credit in the SVG. Some places to
look, with the terms that apply:

- **fastfetch**, about 500 OS logos: [src/logo/ascii](https://github.com/fastfetch-cli/fastfetch/tree/dev/src/logo/ascii). MIT, and the files already use readmefetch's `$1`..`$9` colour syntax.
- **onefetch**, about 100 language logos: [languages.yaml](https://github.com/o2sh/onefetch/blob/main/languages.yaml). MIT; change `{0}` to `$1`, `{1}` to `$2`, and so on.
- **Candy Box 2**, about 300 pieces: the [ascii art page](https://candybox2.github.io/ascii_art.html) and [files](https://github.com/candybox2/candybox2.github.io/tree/master/ascii). CC BY-SA 3.0; credit the `@author` named at the top of each file.
- **CC0 collections**, free to use without conditions: [Phantomwise/ascii](https://github.com/Phantomwise/ascii) and [lordbuffcloud/ascii-collection](https://github.com/lordbuffcloud/ascii-collection).
- **ASCII Art Archive** (asciiart.eu): its [terms of use](https://www.asciiart.eu/terms-of-use) allow user-submitted art only for personal, non-commercial use. A profile README may be fine, but keep the artist's initials or signature in the art and credit them, which is the long-standing ASCII-art custom ([archives](https://www.asciiart.eu/archives)).
- **Your own images**: [chafa](https://hpjansson.org/chafa/) and [jp2a](https://github.com/Talinx/jp2a) turn pictures into text art you own.
