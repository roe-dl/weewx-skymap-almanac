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

import time
import configobj

import weewx
from weewx.engine import StdService
from weewx.units import ValueTuple, ValueHelper
import weewx.almanac
import weeutil.weeutil
import user.skyfieldalmanac

import numpy
from skyfield.api import N, S, E, W, wgs84
from skyfield.constants import DAY_S, DEG2RAD, RAD2DEG
import skyfield.almanac
import skyfield.units

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
    """ get almanac configuration """
    conf_dict = config_dict.get('Almanac',configobj.ConfigObj()).get('Skymap',configobj.ConfigObj())
    alm_conf_dict = weeutil.config.accumulateLeaves(conf_dict)
    alm_conf_dict['enable'] = weeutil.weeutil.to_bool(conf_dict.get('enable',True))
    alm_conf_dict['log_success'] = weeutil.weeutil.to_bool(alm_conf_dict.get('log_success',True))
    alm_conf_dict['log_failure'] = weeutil.weeutil.to_bool(alm_conf_dict.get('log_failure',True))
    return alm_conf_dict

class SkymapAlmanacType(weewx.almanac.AlmanacType):

    SVG_START = '''<svg
  width="%s" height="%s" 
  viewBox="-100 -100 200 200"
  xmlns="http://www.w3.org/2000/svg">
'''
    SVG_END = '''</svg>
'''

    def __init__(self, config_dict, path):
        self.config_dict = config_dict
        self.path = path
        self.bodies = config_dict.get('bodies',['sun','moon','venus','mars_barycenter','jupiter_barycenter','saturn_barycenter','uranus_barycenter','neptune_barycenter','pluto_barycenter'])
        self.show_timestamp = weeutil.weeutil.to_bool(config_dict.get('show_timestamp',True))
        self.show_location = weeutil.weeutil.to_bool(config_dict.get('show_location',True))
        self.width = 800
    
    def __call__(self, width=800, show_timestamp=None, show_location=None, bodies=None):
        self.width = width
        if show_timestamp is not None:
            self.show_timestamp = weeutil.weeutil.to_bool(show_timestamp)
        if show_location is not None:
            self.show_location = weeutil.weeutil.to_bool(show_location)
        if bodies is not None:
            self.bodies = list(bodies)
        return self

    def get_almanac_data(self, almanac_obj, attr):
        """ calculate attribute """
        if (user.skyfieldalmanac.ts is None or 
            user.skyfieldalmanac.ephemerides is None):
            raise weewx.UnknownType(attr)
        
        # TODO: get this from the skin
        labels = {'sun':'Sonne','moon':'Mond','venus':'Venus','mars_barycenter':'Mars','jupiter_barycenter':'Jupiter','saturn_barycenter':'Saturn','neptune_barycenter':'Neptun','pluto_barycenter':'Pluto'}

        if attr=='skymap':
            return self.skymap(almanac_obj, labels)

        raise weewx.UnknownType(attr)
    
    @staticmethod
    def get_observer(almanac_obj):
        observer = user.skyfieldalmanac.ephemerides['earth'] + wgs84.latlon(almanac_obj.lat,almanac_obj.lon,elevation_m=almanac_obj.altitude)
        return observer
    
    @staticmethod
    def to_xy(alt, az):
        """ convert altitude and azimuth to map coordinates
        
            Args:
                alt(float): altitude in degrees
                az(float): azimuth in radians
            
            Returns
                tuple: svg coordinates
        """
        alt = 90-alt
        return -alt*numpy.sin(az),-alt*numpy.cos(az)

    def skymap(self, almanac_obj, labels):
        ordinates = almanac_obj.formatter.ordinate_names
        time_ti = user.skyfieldalmanac.timestamp_to_skyfield_time(almanac_obj.time_ts)
        observer = SkymapAlmanacType.get_observer(almanac_obj)
        s = SkymapAlmanacType.SVG_START % (self.width,self.width)
        s += '<defs><clipPath id="weewxskymapbackgroundclippath"><circle cx="0" cy="0" r="89.8" /></clipPath></defs>\n'
        # background
        alt, _, _ = observer.at(time_ti).observe(user.skyfieldalmanac.ephemerides['sun']).apparent().altaz()
        background_color = "#000040" if alt.degrees<(-0.27) else "#C0C0FF" # "#AdAdff"
        s += '<circle cx="0" cy="0" r="90" fill="%s" stroke="currentColor" stroke-width="0.4" />\n' % background_color
        # start clipping
        s += '<g clip-path="url(#weewxskymapbackgroundclippath)">\n'
        # altitude scale
        s += '<path fill="none" stroke="#808080" stroke-width="0.2" d="M-90,0h180M0,-90v180'
        for i in range(11):
            if i!=5:
                s += 'M%s,-1.5v3M-1.5,%sh3' % (i*15-75,i*15-75)
        s += '" />\n'
        for i in range(11):
            if i!=5:
                s += '<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="middle" dominant-baseline="text-top">%s&deg;</text>' % (i*15-75,6,i*15+15 if i<5 else 165-i*15)
                s += '<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="start" dominant-baseline="middle">%s&deg;</text>' % (2.5,i*15-75,i*15+15 if i<5 else 165-i*15)
        # celestial pole and equator
        # displayed for latitude more than 5 degrees north or south only
        if abs(almanac_obj.lat)>5.0:
            y1 = almanac_obj.lat-90 if almanac_obj.lat>=0 else 90+almanac_obj.lat
            y2 = 0 if almanac_obj.lat>=0 else 1
            txt = ordinates[0 if almanac_obj.lat>=0 else 8]
            #s += '<path fill="none" stroke="#808080" stroke-width="0.2" d="M-2.5,%sh5M-90,0A90,%s 0 0 %s 90,0" />\n' % (y1,almanac_obj.lat,y2)
            s += '<path fill="none" stroke="#808080" stroke-width="0.2" d="M-2.5,%sh5M-90,0A%s,90 0 0 %s 90,0" />\n' % (y1,90.0/numpy.cos(numpy.arcsin((90.0-abs(almanac_obj.lat))/90.0)),y2)
            s += '<text x="-3.5" y="%s" style="font-size:5px" fill="#808080" text-anchor="end" dominant-baseline="middle">%s</text>\n' % (y1,txt)
        # bodies
        dots = []
        for body in self.bodies:
            body_eph = user.skyfieldalmanac.ephemerides[body.lower()]
            apparent = observer.at(time_ti).observe(body_eph).apparent()
            alt, az, distance = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
            if alt.degrees>=0:
                ra, dec, _ = apparent.radec('date')
                x,y = SkymapAlmanacType.to_xy(alt.degrees,az.radians)
                dir = int(round(az.degrees/22.5,0))
                if dir==16: dir = 0
                txt = '%s\nh=%.1f&deg; a=%.1f&deg; %s\nra=%.1fh dec=%.1f&deg;' % (labels.get(body,body),alt.degrees,az.degrees,ordinates[dir],ra.hours,dec.degrees)
                phase = None
                if body=='sun':
                    radius = 16.0/60.0
                    r = 3
                elif body=='moon':
                    radius = skyfield.almanac._moon_radius_m/distance.m*RAD2DEG
                    r = 2
                    phase = skyfield.almanac.moon_phase(user.skyfieldalmanac.sun_and_planets,time_ti)
                    moon_index = int((phase.degrees/360.0 * 8) + 0.5) & 7
                    ptext = almanac_obj.moon_phases[moon_index]
                    txt += '\n%s: %.0f&deg; %s' % ('Phase',phase.degrees,ptext)
                elif body in ('mercury','venus','mars_barycenter','jupiter_barycenter','saturn_barycenter'):
                    radius = None
                    r = 0.75
                else:
                    radius = None
                    r = 0.5
                if body in ('mars','mars_barycenter'):
                    col = '#ff8f5e'
                elif body=='moon':
                    col = ['rgba(255,243,228,0.3)','#ffecd5']
                else:
                    col = '#ffffff'
                txt += '\n%s: %.0f km' % ('Entfernung',distance.km)
                dots.append((txt,x,y,r,distance,col,radius,phase))
        dots.sort(key=lambda x:-x[4].km)
        for dot in dots:
            if dot[7] is not None:
                s += self.moon(*dot)
                """
                s += '<g><title>%s</title>' % dot[0]
                s += '<circle cx="%.4f" cy="%.4f" r="%s" fill="%s" stroke="none" />\n' % (dot[1],dot[2],dot[3],dot[5][0])
                phase = dot[7].degrees
                desc = 0 if phase>180.0 else 1
                quarter = 0 if 90<phase<270 else 1
                s += '<path fill="%s" stroke="none" d="M%.4f,%.4fa%.4f,%.4f 0 %s 0 %.4f,%.4f' % (dot[5][1],dot[1],dot[2]-dot[3],dot[3],dot[3],desc,0,2*dot[3])
                if round(phase,1)!=90.0 and round(phase,1)!=270.0:
                    s += 'a%.4f,%.4f 0 %s 0 %.4f %.4f' % (0.5*dot[3],dot[3],quarter,0,-2*dot[3])
                s += 'z" />\n'
                s += '</g>'
                """
            else:
                s += '<circle cx="%.4f" cy="%.4f" r="%s" fill="%s" stroke="none"><title>%s</title></circle>\n' % (dot[1],dot[2],dot[3],dot[5],dot[0])
        # end clipping
        s += '</g>\n'
        # azimuth scale
        s += '<path fill="none" stroke="currentColor" stroke-width="0.4" d="'
        for i in range(24):
            azh = i*15*DEG2RAD
            x1,y1 = SkymapAlmanacType.to_xy(0,azh)
            x2,y2 = SkymapAlmanacType.to_xy(-3,azh)
            s += "M%.4f,%.4fL%.4f,%.4f" % (x1,y1,x2,y2)
        s += '" />\n'
        for i in range(24):
            azh = i*15*DEG2RAD
            x,y = SkymapAlmanacType.to_xy(-8,azh)
            if i==0:
                txt = ordinates[0] # north
            elif i==6:
                txt = ordinates[4] # east
            elif i==12:
                txt = ordinates[8] # south
            elif i==18:
                txt = ordinates[12] # west
            else:
                txt = "%d°" % (i*15)
            s += '<text x="%.4f" y="%.4f" style="font-size:5px" fill="currentColor" text-anchor="middle" dominant-baseline="middle">%s</text>\n' % (x,y,txt)
        if self.show_timestamp:
            time_vt = ValueHelper(ValueTuple(almanac_obj.time_ts,'unix_epoch','group_time'),'ephem_year',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            time_s = str(time_vt).split(' ')
            s += '<text x="97" y="85" style="font-size:5px" fill="currentColor" text-anchor="end" dy="0">\n'
            s += '<tspan x="97" dy="1.2em">%s</tspan>\n' % time_s[0]
            if len(time_s)>1 and time_s[1]:
                s += '<tspan x="97" dy="1.2em">%s</tspan>\n' % time_s[1]
            s += '</text>\n'
        if self.show_location:
            lat_vt = ValueHelper(ValueTuple(almanac_obj.lat,'degree_compass','group_direction'),'current',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            lon_vt = ValueHelper(ValueTuple(almanac_obj.lon,'degree_compass','group_direction'),'current',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            lat_s = lat_vt.format("%8.4f").replace(' ','&numsp;')
            lon_s = lon_vt.format("%08.4f")
            s += '<text x="-97" y="85" style="font-size:5px" fill="currentColor" text-anchor="start" dy="0">\n'
            s += '<tspan x="-97" dy="1.2em">%s %s</tspan>\n' % (lat_s,ordinates[0 if almanac_obj.lat>=0 else 8])
            s += '<tspan x="-97" dy="1.2em">%s %s</tspan>\n' % (lon_s,ordinates[4 if almanac_obj.lon>=0 else 12])
            s += '</text>\n'
        #s += self.moonphasetest()
        s += SkymapAlmanacType.SVG_END
        return s
    
    def moon(self, txt, x, y, r, distance, col, radius, phase):
        phase = round(phase.degrees,1)%360
        full_moon = phase==180.0
        new_moon = phase==0.0
        s = ""
        s += '<g><title>%s</title>\n' % txt
        s += '<circle cx="%.4f" cy="%.4f" r="%s" fill="%s" stroke="none" />\n' % (x,y,r,col[1] if full_moon else col[0])
        if not full_moon and not new_moon:
            desc = 0 if phase>180.0 else 1
            phase180 = phase%180
            quarter = 0 if phase180<90 else 1
            fullness = (phase180-90.0 if phase180>90.0 else 90.0-phase180)/90.0
            s += '<path fill="%s" stroke="none" d="M%.4f,%.4fa%.4f,%.4f 0 0 %s %.4f,%.4f' % (col[1],x,y-r,r,r,desc,0,2*r)
            if phase!=90.0 and phase!=270.0:
                s += 'a%.4f,%.4f 0 0 %s %.4f %.4f' % (fullness*r,r,quarter,0,-2*r)
            s += 'z" />\n'
        s += '</g>\n'
        return s
    
    def moonphasetest(self):
        s = ""
        s+=self.moon('30',-50,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=30))
        s+=self.moon('60',-30,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=60))
        s+=self.moon('90',-10,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=90))
        s+=self.moon('120',10,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=120))
        s+=self.moon('150',30,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=150))
        s+=self.moon('180',50,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=180))
        s+=self.moon('210',-50,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=210))
        s+=self.moon('240',-30,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=240))
        s+=self.moon('270',-10,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=270))
        s+=self.moon('300',10,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=300))
        s+=self.moon('330',30,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=330))
        s+=self.moon('360',50,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=360))
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
            self.skymap_almanac = SkymapAlmanacType(alm_conf_dict, self.path)
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
