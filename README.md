# weewx-skymap-almanac
Sky map for WeeWX

![sky map](skymap.png)

## Contents

* [Prerequisites](#prerequisites)
* [Installation instructions](#installation-instructions)
* [Configuration instructions](#configuration-instructions)
* [Sky map](#sky-map)
* [Moon with moon phase](#moon-with-moon-phase)
* [Analemma](#analemma)
* [Dark mode of your web site](#dark-mode-of-your-website)
* [Changing visibility of elements by JavaScript](#changing-visibility-of-elements-by-javaScript)
* [Credits](#credits)
* [Links](#links)

## Prerequisites

WeeWX from version 5.2 on and weewx-skyfield-almanac

## Installation instructions

1) download

   ```shell
   wget -O weewx-skymap-almanac.zip https://github.com/roe-dl/weewx-skymap-almanac/archive/master.zip
   ```

2) run the installer

   WeeWX from version 5.2 on and WeeWX packet installation

   ```shell
   sudo weectl extension install weewx-skymap-almanac.zip
   ```

   WeeWX from version 5.2 on and WeeWX pip installation into an virtual environment

   ```shell
   source ~/weewx-venv/bin/activate
   weectl extension install weewx-skymap-almanac.zip
   ```
   
3) restart weewx

   for SysVinit systems:

   ```shell
   sudo /etc/init.d/weewx stop
   sudo /etc/init.d/weewx start
   ```

   for systemd systems:

   ```shell
   sudo systemctl stop weewx
   sudo systemctl start weewx
   ```

## Configuration instructions

There is no need to configure anything, but there are some tuning options
available if you have special requirements.

```
[Almanac]
    [[Skymap]]
        # use this almanac
        enable = true
        # list of heavenly bodies to include in the map
        bodies = ...
        # list of earth satellites to include in the map
        earth_satellites = ...
        # maximum star magnitude to include in the map
        max_magnitude = 6.0
        # flag whether to include stars in the map
        show_stars = true
        # flag whether to include the timestamp
        show_timestamp = true
        # flag whether to include the location
        show_location = true
        # flag whether to show the ecliptic as a dotted line
        show_ecliptic = true
        # flag whether to show the constellation lines between the stars
        show_constellations = true
        # format options
        [[[Formats]]]
            stars = mag, '#ff0'
            object_name = size, color, ...
```

* `enable`: Enable this almanac extension.
* `bodies`: List of heavenly bodies to include in the map. Optional.
  Default the sun, the moon, and the well-known planets.
  This can include all objects available in BSP files.
* `earth_satellites`: List of earth satellites to include in the map.
  Optional. Default no satellites.
  The ID to use here contains of the file name of the
  satellite data file (without file name extension) and
  the catalog number of the satellite, connected by an underscore.
* `max_magnitude`: Maximum star magnitude to include in the map.
  Optional. Default is 6.0. This is, how you would see the sky
  in a clear night in the middle of nowhere. Try 4.0 if that
  looks more the way you know the sky in the night to be.
  Please note, the larger the magnitude, the fainter the star.
* `star_tooltip_max_magnitude`: Stars get a tooltip if their magnitude
  is less than this value. Optional. Default is 2.5. 
* `show_stars`: Flag whether to include stars in the map. Optional.
  Default `True`.
* `show_timestamp`: Flag whether to include the timestamp. Optional.
  Default `True`. 
* `show_location`: Flag whether to include the location. Optional.
  Default `True`.
* `show_ecliptic`: Flag whether to show the ecliptic as a dotted line.
  Optional. Default `True`.
* `show_constellations`: Flag whether to show the constellation lines
  between the stars. Optional. Default `True`. Uses the 
  `constellationship.fab` file of Stellarium.
* `moon_colors`: Colors for `moon_symbol`. Optional. Default
  `['#bbb4ac19','#ffecd5']`. The first value is the color of the dark
  side, the second color that of the sunlit side. For the dark side
  an opacity value can be provided.
* `analemma_colors`: Colors for `analemma`. Optional. Default
  `['currentColor','#808080','#7cb5ec','#f7a35c']`
* `[[[Formats]]]`: Format options. Optional.
  There are reasonable defaults. So you do not need this section at all.
  But if you want to set up something special you can do it here.
  Each entry contains an object name and a list of options. For example
  the line `stars = mag, "#ff0"` says that the stars are to be drawn
  with a diameter according to their magnitude and a color of yellow.
  This is also the default if no option is specified. A line 
  `mars_barycenter = 0.85, "#ff8f5e"` would draw the planet Mars
  with a radius of 0.85 and a reddish color. This is the default, too.
  For earth satellites a third parameter is possible describing the
  shape of the representation of the object. For example it can be
  `round`, `triangle`, `square`, or `rhombus`.

All the configuration options can also be used as parameters to the
attributes described below.

## Sky map

### Usage

Add `$almanac.skymap` to your skin.

The map shows the sky as you would see it if you were lying on the ground, 
your legs to the south, and looking upwards. The size of the heavenly bodies 
on the map is not according to scale.

### Parameters

You can change the size of the map or other properties by setting parameters
like `$almanac.skymap(width=1200)`. All the options that are defined for the 
configuration file can also be used as parameters. Additionally there are the 
following parameters defined to adjust the layout:

* `width`: Width and height of the map. Default 800.
* `location`: Location as text (for example the city name). Appears in the
  lower left corner of the sky map if provided instead of pure geographic
  coordinates. An empty string switches it off.
* `credits`: Credits text in the lower right corner of the sky map. Default
  is the text of the option `location` in `weewx.conf` together with the
  copyright sign.
* `x` and `y`: In case you want to include the sky map into another SVG
  image, you can set position by the `x` and `y` parameters.

### Time

The sky map image contains different timestamps:

* **Solar time**: In the upper left corner you find the apparent solar time.
  That is the time a sundial would show. It represents the position of the
  sun in the sky.
* **Sidereal time**: In the upper right corner you find the apparent 
  sidereal time. 
* **Civil time**: Civil time you find in the lower right corner together
  with the date.

## Moon with moon phase

Add `$almanac.moon_symbol` to your skin.

You can change the size of the symbol by setting the parameter `width` like
`$almanac.moon_symbol(width=200)`.

To switch off moon tilt, use `$almanac.moon_symbol(with_tilt=False)`.

In case you want to include the moon symbol into another SVG image, you
can set the position by using the paraemters `x` and `y`.

## Analemma

### Usage

Add `$almanac.analemma` to your skin.

The analemma is calculated for the year and the time of day `$almanac` is 
bound to. You can change it by setting `almanac_time`.

### Parameters

All the options that are defined for the configuration file can also be
used as parameters. Additionally there are the following parameters
defined to adjust the layout:

* `width`: Width of the diagram. Default 280.
* `height`: Height of the diagram. Default 300.
* `location`: Location as text (for example the city name). Appears in the 
  caption of the analemma. An empty string switches it off.
* `tz`: Time in the caption of the analemma. Possible values are:
  * `LMT`: Local Mean Time. This differs from solar time by the equation 
    of time. Often an analemma is provided for 12:00:00 Local Mean Time.
  * `UTC`: UTC
  * `civil`: The local time as used by WeeWX. This is the default.

This is the analemma at the Royal Observatory Greenwich at high noon mean
time:

![analemma](analemma.png)

## Dark mode of your web site

If you insert the tags into your web page template as described above dark
mode is observed properly. The background and the text around the map and in
the diagram is colored as you configured it by CSS for your website in
general.

The sky color does not depend on light or dark mode but on the time of day.
It is dark at night and light at day, and in dawn it is in between.

But if you save the images created by the tags to separate files and
include them using the `<img>` tag (what we do NOT recommend), then you will 
have to set up colors appropriately by the `colors` parameter or
configuration option.

## Changing visibility of elements by JavaScript

If you want your users to be able to switch on and off some parts of the
map, for example the constellation lines, you can do so by JavaScript.
The elements have IDs for that. 

To switch off the constellations lines the script looks like this:
```JavaScript
let el = document.getElementById('constellations');
if (el)
  {
    el.style.display = "none";
  }
```

To switch on the constellation lines the script looks like this:
```JavaScript
<script>
let el = document.getElementById('constellations');
if (el)
  {
    el.removeProperty("display");
  }
</script>
```

You cannot only switch on and off elements, but also change the color to
highlight it. This script highlights Polaris by enlarging its diameter
and changing its color and reverts to the original values after a short
period of time:
```JavaScript
let el = document.getElementById('HIP11767');
if (el)
  {
    let r = el.getAttribute("r");
    let f = el.getAttribute("fill");
    el.setAttribute("r","3");
    el.setAttribute("fill","#00f");
    setTimeout(() => {
        el.setAttribute("r",r);
        el.setAttribute("fill",f);
    }, 1000);
  }
```

If you assign that script to a button, the user can easily find the star
on the map by pressing the button.

The following IDs are defined:
* `circle_of_right_ascension`: circle of right ascension and border of the
  circumpolar area
* `circle_of_ecliptic`: dotted line of the circle of the ecliptic
* `constellations`: constellation lines
* `constellation_`+constellation abbreviation: the lines of a specific 
  constellation, named by its international abbreviation
* planet name: a planet on the map (add `_barycenter` for the outer planets)
* Earth satellite ID: an Earth satellite
* `HIP`+Hipparcos catalogue number: a single star on the map

## Credits

* [Tom Keffer et al. (WeeWX)](https://github.com/weewx/weewx)
* [Brandon Rhodes (Skyfield)](https://github.com/skyfielders/python-skyfield)
* [Fabien Chéreau (Stellarium)](https://github.com/Stellarium/stellarium/discussions/790)

## Links

* [WeeWX](https://weewx.com)
* [weewx-skyfield-almanac](https://github.com/roe-dl/weewx-skyfield-almanac)
* [List of brightest stars](https://en.wikipedia.org/wiki/List_of_brightest_stars)
* [Liste der hellsten Sterne](https://de.wikipedia.org/wiki/Liste_der_hellsten_Sterne)
* [Andrea K. Myers-Beaghton et al.: The moon tilt illusion](https://www.seas.upenn.edu/~amyers/MoonPaperOnline.pdf)
* [Karlheinz Schott (&dagger;): "Falsche" Mondneigung - Wohin zeigt die Mondsichel?](https://falsche-mondneigung.jimdofree.com/b-geometrische-darstellung-und-berechnung/) (german)
* [Example page](https://www.woellsdorf-wetter.de/maps/skymap.html)
