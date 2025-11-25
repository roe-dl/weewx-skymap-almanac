# installer almanac extension
# Copyright 2025 Johanna Roedenbeck
# Distributed under the terms of the GNU Public License (GPLv3)

from weecfg.extension import ExtensionInstaller

def loader():
    return SkymapInstaller()

class SkymapInstaller(ExtensionInstaller):
    def __init__(self):
        super(SkymapInstaller, self).__init__(
            version="0.3",
            name='Skymap almanac',
            description='almanac extension using Skyfield mdule',
            author="Johanna Roedenbeck",
            author_email="",
            prep_services='user.skymapalmanac.SkymapService',
            config={
                'Almanac': {
                    'Skymap': {
                        'enable':'true',
                    }
                }
            },
            files=[('bin/user', ['bin/user/skymapalmanac.py','bin/user/constellationship.fab'])]
        )
