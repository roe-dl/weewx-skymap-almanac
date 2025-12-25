# WeeWX Skymap almanac extension example

This is an example skin to create a web page including the tags provided
by this extension. Please use it as a starting point to include the
tags into your own skin.

## Usage

Primarily the template should serve as an example for you to create your
own templates. But you can also use it as a skin in WeeWX.

If you want to try this example you have to add the following section
to your `weewx.conf` file to the `[StdReport]` section:

```
    [[SkymapReport]]
        skin = Skymap
        enable = true
        lang = ISO_code_of_your_language_here
        HTML_ROOT = /var/www/html/skymap
```

Then create the directory `Skymap` in the skin directory of your WeeWX
installation and copy the content of this directory there. This has to
be done manually because it is an example only.

In case of the package installation method you create the directory
using the following command:

```shell
mkdir /etc/weewx/skins/Skymap
```

![Skymap](../../skymap-example.png)
