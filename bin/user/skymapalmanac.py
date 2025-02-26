#!/usr/bin/python3
# Almanac extension to WeeWX using Skyfield
# Copyright (C) 2025 Johanna Roedenbeck

"""

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

VERSION="0.1"

import configobj

import weewx
from weewx.engine import StdService
import weewx.almanac
import weeutil.weeutil
import user.skyfieldalmanac

import numpy
from skyfield.api import N, S, E, W, wgs84
from skyfield.constants import DAY_S, DEG2RAD, RAD2DEG
import skyfield.almanac

# Logging
import weeutil.logger
import logging
log = logging.getLogger("user.skymapdalmanac")

def logdbg(msg):
    log.debug(msg)

def loginf(msg):
    log.info(msg)

def logerr(msg):
    log.error(msg)

def _get_config(config_dict):
    return {'enable':True}

class SkymapAlmanacType(weewx.almanac.AlmanacType):

    SVG_START = '''<svg
  width="800" height="800" 
  viewBox="-100 -100 200 200"
  xmlns="http://www.w3.org/2000/svg">
'''
    SVG_END = '''</svg>
'''

    def __init__(self, config_dict, path):
        self.config_dict = config_dict
        self.path = path
        self.bodies = ['sun','moon','venus','mars_barycenter','jupiter_barycenter','saturn_barycenter','uranus_barycenter','neptune_barycenter','pluto_barycenter']

    def get_almanac_data(self, almanac_obj, attr):
        """ calculate attribute """
        if (user.skyfieldalmanac.ts is None or 
            user.skyfieldalmanac.ephemerides is None):
            raise weewx.UnknownType(attr)
        
        if attr=='skymap':
            return self.skymap(almanac_obj)

        raise weewx.UnknownType(attr)
    
    @staticmethod
    def get_observer(almanac_obj):
        observer = user.skyfieldalmanac.ephemerides['earth'] + wgs84.latlon(almanac_obj.lat,almanac_obj.lon,elevation_m=almanac_obj.altitude)
        return observer
    
    @staticmethod
    def to_xy(alt, az):
        alt = 90-alt
        return -alt*numpy.sin(az),-alt*numpy.cos(az)

    def skymap(self, almanac_obj):
        time_ti = user.skyfieldalmanac.timestamp_to_skyfield_time(almanac_obj.time_ts)
        observer = SkymapAlmanacType.get_observer(almanac_obj)
        s = SkymapAlmanacType.SVG_START
        # background
        alt, _, _ = observer.at(time_ti).observe(user.skyfieldalmanac.ephemerides['sun']).apparent().altaz()
        background_color = "#000040" if alt.degrees<(-0.27) else "#AdAdff"
        s += '<circle cx="0" cy="0" r="90" fill="%s" stroke="currentColor" stroke-width="0.4" />\n' % background_color
        # altitude scale
        s += '<path fill="none" stroke="#808080" stroke-width="0.2" d="M-90,0h180M0,-90v180'
        for i in range(11):
            if i!=5:
                s += 'M%s,-1.5v3M-1.5,%sh3' % (i*15-75,i*15-75)
        s += '" />\n'
        for i in range(11):
            if i!=5:
                s += '<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="middle" dominant-baseline="text-top">%s&deg;</text>' % (i*15-75,6,i*15+15 if i<5 else 165-i*15)
                s += '<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="left" dominant-baseline="middle">%s&deg;</text>' % (2.5,i*15-75,i*15+15 if i<5 else 165-i*15)
        # bodies
        dots = []
        for body in self.bodies:
            body_eph = user.skyfieldalmanac.ephemerides[body.lower()]
            alt, az, distance = observer.at(time_ti).observe(body_eph).apparent().altaz()
            if alt.degrees>=0:
                x,y = SkymapAlmanacType.to_xy(alt.degrees,az.radians)
                if body=='sun':
                    r = 16.0/60.0
                    r = 3
                elif body=='moon':
                    r = skyfield.almanac._moon_radius_m/distance.m*RAD2DEG
                    r = 2
                elif body in ('mercury','venus','mars_barycenter','jupiter_barycenter','saturn_barycenter'):
                    r = 0.75
                else:
                    r = 0.5
                dots.append(('%s\nh=%.1f&deg; a=%.1f&deg;' % (body,alt.degrees,az.degrees),x,y,r,distance))
        dots.sort(key=lambda x:-x[4].km)
        for dot in dots:
            s += '<circle cx="%s" cy="%s" r="%s" fill="#fff" stroke="none"><title>%s</title></circle>\n' % (dot[1],dot[2],dot[3],dot[0])
        # azimuth scale
        s += '<path fill="none" stroke="currentColor" stroke-width="0.4" d="'
        for i in range(24):
            azh = i*15*DEG2RAD
            x1,y1 = SkymapAlmanacType.to_xy(0,azh)
            x2,y2 = SkymapAlmanacType.to_xy(-3,azh)
            s += "M%s,%sL%s,%s" % (x1,y1,x2,y2)
        s += '" />\n'
        for i in range(24):
            azh = i*15*DEG2RAD
            x,y = SkymapAlmanacType.to_xy(-8,azh)
            if i==0:
                txt = 'N'
            elif i==6:
                txt = 'O'
            elif i==12:
                txt = 'S'
            elif i==18:
                txt = 'W'
            else:
                txt = "%d°" % (i*15)
            s += '<text x="%s" y="%s" style="font-size:5px" fill="currentColor" text-anchor="middle" dominant-baseline="middle">%s</text>\n' % (x,y,txt)
        s += SkymapAlmanacType.SVG_END
        return s


class SkymapService(StdService):
    """ Service to initialize the Skymap almanac extension """

    def __init__(self, engine, config_dict):
        """ init this extension """
        super(SkymapService,self).__init__(engine, config_dict)
        # directory to save ephemeris and IERS files
        self.path = config_dict.get('DatabaseTypes',configobj.ConfigObj()).get('SQLite',configobj.ConfigObj()).get('SQLITE_ROOT','.')
        # configuration
        alm_conf_dict = _get_config(config_dict)
        if alm_conf_dict['enable']:
            # instantiate the Skymap almanac
            self.skymap_almanac = SkymapAlmanacType(config_dict, self.path)
            # add to the list of almanacs
            weewx.almanac.almanacs.insert(0,self.skymap_almanac)
            logdbg("%s started" % self.__class__.__name__)
        else:
            loginf("Skyfield almanac not enabled. Skipped.")

    def shutDown(self):
        """ remove this extension from the almanacs list
        """
        # find the Skyfield almanac in the list of almanacs
        idx = weewx.alamanc.almanacs.index(self.skymap_almanac)
        # remove it from the list
        del weewx.almanac.almanacs[idx]
        # stop thread
        logdbg("%s stopped" % self.__class__.__name__)
