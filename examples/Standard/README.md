# Additional almanac page

This example adds another page to the Standard skin. It shows almanac
data and diagrams.

## Usage

Copy the file `almanac.html.tmpl` to the directory of the Standard skin.
Then open `skin.conf` and add the following lines before the `[[[RSS]]]`
line:

```
        [[[almanac]]]
            template = almanac.html.tmpl

```

Edit all the other `.tmpl` files and add one line at the end after the
other buttons:

```
        <input type="button" value=$pgettext("Buttons","Almanac") onclick="openURL('almanac.html')" />
```

![Almanac](../../doc-images/Standard-example.png)

## Localization

To adapt the labels to your language look for the appropriate language
file in the `lang` subdirectory of the Seasons skin. For example, if you 
are french, look for `fr.conf`. There you can add the words you need to 
translate. 

In section `[Texts]`:

Key = English | French    | German   | Dutch      | Czech    | Norwegian
--------------|-----------|----------|------------|----------|-----------
Perihelion    | Périhélie | Perihel  | Perihelium | Perihel  | Perihel
Aphelion      | Aphélie   | Aphel    | Aphelium   | Afel     | Aphel
Perigee       | Périgée   | Perigäum | Perigeum   | Perigeum | Perigeum
Apogee        | Apogée    | Apogäum  | Apogeum    | Apogeum  | Apogeum
Equation of Time | Équation du temps | Zeitgleichung | Tijdsvereffening | Časová rovnice |

In section `[Almanac]`, subsection `[[TZ]]`:

Key        | English       | French        | German     | Dutch       | Czech        | Norwegian
-----------|---------------|---------------|------------|-------------|--------------|----------
name(LAT)  | Solar time    | Temps solaire | Sonnenzeit | Zonnetijd   | Sluneční čas | Soltid
name(LAST) | Sidereal time | Temps sidéral | Sternzeit  | Sterrentijd | Hvězdný čas  | Stjernetid

Add the name of your local timezone, too.

In section `[Texts]`, subsection `[[Astronomical]]`:

Key = English | French        | German     | Dutch       | Czech        | Norwegian
--------------|---------------|------------|-------------|--------------|----------
Magnitude     | Magnitude     | Magnitude  | Magnitude   | Hvězdná velikost | Magnitude
First point of Aries | Point Vernal | Frühlingspunkt | Lentepunt | Jarní bod | Værens punkt
Apparent size | Taille apparente | Scheinbare Größe | | Úhlová velikost | Tilsynelatende størrelse
Moon tilt     | Inclinaison   | Neigung    | | | Månetilt
Distance      | Distance      | Entfernung | Afstand     | Vzdálenost | fra et himmellegeme
