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
import os.path
import configobj

import weewx
from weewx.engine import StdService
from weewx.units import ValueTuple, ValueHelper
import weewx.almanac
import weeutil.weeutil
import user.skyfieldalmanac

import numpy
from skyfield.api import N, S, E, W, wgs84, EarthSatellite, Star
from skyfield.constants import DAY_S, DEG2RAD, RAD2DEG
from skyfield.magnitudelib import planetary_magnitude
from skyfield.positionlib import position_of_radec
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
    conf_dict = config_dict.get('Almanac',configobj.ConfigObj())
    enable_skyfield = weeutil.weeutil.to_bool(conf_dict.get('Skyfield',configobj.ConfigObj()).get('enable',True))
    conf_dict = conf_dict.get('Skymap',configobj.ConfigObj())
    alm_conf_dict = weeutil.config.accumulateLeaves(conf_dict)
    alm_conf_dict['enable'] = weeutil.weeutil.to_bool(conf_dict.get('enable',True)) and enable_skyfield
    alm_conf_dict['log_success'] = weeutil.weeutil.to_bool(alm_conf_dict.get('log_success',True))
    alm_conf_dict['log_failure'] = weeutil.weeutil.to_bool(alm_conf_dict.get('log_failure',True))
    alm_conf_dict['Formats'] = conf_dict.get('Formats',configobj.ConfigObj())
    return alm_conf_dict


class SkymapAlmanacType(weewx.almanac.AlmanacType):

    SVG_START = '''<svg
  width="%s" height="%s" 
  viewBox="-100 -100 200 200"
  xmlns="http://www.w3.org/2000/svg">
'''
    SVG_END = '''</svg>
'''

    def __init__(self, config_dict, path, station_location):
        self.config_dict = config_dict
        self.path = path
        self.station_location = station_location
    
    def get_almanac_data(self, almanac_obj, attr):
        """ calculate attribute """
        if (user.skyfieldalmanac.ts is None or 
            user.skyfieldalmanac.ephemerides is None):
            raise weewx.UnknownType(attr)
        
        if attr=='skymap':
            return SkymapBinder(self.config_dict, self.station_location, almanac_obj, self.get_labels(almanac_obj))
        if attr=='moon_symbol':
            return MoonSymbolBinder(almanac_obj, self.get_labels(almanac_obj), self.config_dict.get('moon_colors',['rgba(255,243,228,0.5)','#ffecd5']))
        if attr=='analemma':
            return AnalemmaBinder(self.config_dict, self.station_location, almanac_obj, self.get_labels(almanac_obj))

        raise weewx.UnknownType(attr)

    def get_labels(self, almanac_obj):
        # TODO: get this from the skin
        labels = {'sun':'Sun','moon':'Moon','mercury':'Mercury','venus':'Venus','mars_barycenter':'Mars','jupiter_barycenter':'Jupiter','saturn_barycenter':'Saturn','neptune_barycenter':'Neptune','pluto_barycenter':'Pluto'}
        new_moon = almanac_obj.moon_phases[0]
        for lang, val in self.config_dict['Texts'].items():
            if val['moon_phase_new_moon']==new_moon:
                labels.update(val)
                break
        return labels

class SkymapBinder:
    """ SVG map of the sky showing the position of heavenly bodies """

    def __init__(self, config_dict, station_location, almanac_obj, labels):
        self.config_dict = config_dict
        self.credits = '&copy; '+station_location
        self.location = ''
        self.almanac_obj = almanac_obj
        self.labels = labels
        self.log_failure = config_dict['log_failure']
        self.bodies = config_dict.get('bodies',['sun','moon','mercury','venus','mars_barycenter','jupiter_barycenter','saturn_barycenter','uranus_barycenter','neptune_barycenter','pluto_barycenter'])
        self.earthsatellites = config_dict.get('earth_satellites',[])
        self.show_stars = weeutil.weeutil.to_bool(config_dict.get('show_stars',True))
        self.show_timestamp = weeutil.weeutil.to_bool(config_dict.get('show_timestamp',True))
        self.show_location = weeutil.weeutil.to_bool(config_dict.get('show_location',True))
        self.show_ecliptic = weeutil.weeutil.to_bool(config_dict.get('show_ecliptic',True))
        self.formats = config_dict['Formats']
        self.night_color = (0,0,64) # #000040
        self.day_color = (192,192,240) # #C0C0F0 # "#AdAdff"
        self.inout = -1.0
        self.width = 800
        self.max_magnitude = weeutil.weeutil.to_float(config_dict.get('max_magnitude',6.0))
        self.star_tooltip_max_magnitude = weeutil.weeutil.to_float(config_dict.get('star_tooltip_max_magnitude',2.5))
    
    def __call__(self, **kwargs):
        """ optional parameters
        
            Args:
                width(int): width of the image
                show_timestamp(bool): include timestamp in the map
                show_location(bool): include location in the map
                bodies(list): heavenly bodies to include in the map
                fromoutside(bool): reverse east-west
        """
        for key in kwargs:
            if key=='width':
                self.width = weeutil.weeutil.to_int(kwargs[key])
            elif key in {'show_stars','show_timestamp','show_location','show_ecliptic'}:
                setattr(self,key,weeutil.weeutil.to_bool(kwargs[key]))
            elif key=='fromoutside':
                self.inout = 1.0 if kwargs[key] else -1.0
            elif key=='bodies':
                self.bodies = list(kwargs[key])
            elif key in {'max_magnitude','star_tooltip_max_magnitude'}:
                setattr(self,key,weeutil.weeutil.to_float(kwargs[key]))
            else:
                setattr(self,key,kwargs[key])
        return self

    def __str__(self):
        try:
            return self.skymap(self.almanac_obj)
        except Exception as e:
            if self.log_failure:
                logerr("cannot create sky map: %s - %s" % (e.__class__.__name__,e))
            raise
    
    @staticmethod
    def get_observer(almanac_obj):
        observer = user.skyfieldalmanac.ephemerides['earth'] + wgs84.latlon(almanac_obj.lat,almanac_obj.lon,elevation_m=almanac_obj.altitude)
        return observer
    
    def to_xy(self, alt, az):
        """ convert altitude and azimuth to map coordinates
        
            Args:
                alt(float): altitude in degrees
                az(float): azimuth in radians
            
            Returns:
                tuple: SVG coordinates
            
            self.inout(float): Is the point of view inside or outside the
                celestial globe?
        """
        alt = 90-alt
        return self.inout*alt*numpy.sin(az),-alt*numpy.cos(az)
    
    @staticmethod
    def magnitude_to_r(magnitude):
        """ get radius to draw out of magnitude """
        r = (6.0-magnitude)*0.1
        if r<0.1: r = 0.1
        return r
    
    @staticmethod
    def four_pointed_star(x,y,r,color):
        """ draw four pointed star """
        return  '<path fill="%s" stroke="none" d="M%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f,%.4fz" />' % (
            color,x-r,y,0.7*r,0.3*r,0.3*r,0.7*r,0.3*r,-0.7*r,0.7*r,-0.3*r,-0.7*r,-0.3*r,-0.3*r,-0.7*r,-0.3*r,0.7*r)

    def circle_of_right_ascension(self, observer, almanac_obj, time_ti, color='#808080'):
        """ draw circle of that declination that touches the horizon 
        
            It is not really a circle, not even an ellipse. But it is near.
            The hours are the current right ascension. Stars move very
            very slowly only in respect of right ascension and declination.
        """
        s = ['<g id="circle_of_right_ascension" fill="%s">\n' % color]
        # hours of right ascension (one star day)
        hours = numpy.arange(24)
        # set declination according to the latitude the map is drawn for
        dec = numpy.array([(90-abs(almanac_obj.lat))*(1 if almanac_obj.lat>=0 else -1)]*24)
        # Below 20° of latitude the circle is too small for text marks
        above20 = abs(almanac_obj.lat)>20
        # create fictive stars holding the positions according to the 
        # coordinates defined before
        body = Star(ra_hours=hours,dec_degrees=dec,epoch=time_ti)
        # get the current altitudes and azimuths for those positions
        apparent = observer.at(time_ti).observe(body).apparent()
        alts, azs, _ = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
        # draw the circle
        for alt, az, hour in zip(alts.degrees,azs.radians,hours):
            x,y = self.to_xy(alt,az)
            #dir = numpy.arctan2(x,y+90-almanac_obj.lat)
            #r = 1 if hour!=0 else 2
            #s += SkymapBinder.four_pointed_star(x,y,r,color)
            #s += '<path fill="none" stroke="#808080" stroke-width="0.2" d="M%.4f,%.4fl%.4f,%.4fM%.4f,%.4fl%.4f,%.4f" />\n' % ()
            if above20:
                s.append('<text x="%.4f" y="%.4f" font-size="3" text-anchor="middle" dominant-baseline="middle">%dh</text>\n' % (x,y,hour))
            else:
                s.append('<circle cx="%.4f" cy="%.4f" r="%s"><title>alt=%.4f az=%.4f</title></circle>\n' % (x,y,0.5 if hour!=0 else 1,alt,az*RAD2DEG))
        s.append('</g>\n')
        return ''.join(s)
    
    def circle_of_ecliptic(self, observer, almanac_obj, time_ti, color='#C000C0'):
        """ draw circle of ecliptic 
        
            This draws a dotted line with each dot 1 day apart from the other
            one.
        """
        time0_ts = time.thread_time_ns()*0.000001
        s =['<g id="circle_of_ecliptic" fill="%s" stroke="none">\n' % color]
        # list of the days of a year, starting 1/2 year before the current day
        days = user.skyfieldalmanac.ts.ut1_jd([time_ti.ut1+i-182 for i in range(365)])
        # calculating right ascension and declination of the sun for all those
        # dates.
        ra, dec, _ = observer.at(days).observe(user.skyfieldalmanac.ephemerides['sun']).apparent().radec('date')
        time1_ts = time.thread_time_ns()*0.000001
        # create fictive stars holding those positions in sky
        dots = Star(ra_hours=ra.hours,dec_degrees=dec.degrees,epoch=time_ti)
        # calculate the positions of those objects for the current date and time
        apparent = observer.at(time_ti).observe(dots).apparent()
        time2_ts = time.thread_time_ns()*0.000001
        # calculate altitude and azimuth for those positions
        alts, azs, _ = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
        time3_ts = time.thread_time_ns()*0.000001
        # draw dots of the circle of the ecliptic
        for alt, az, day in zip(alts.degrees,azs.radians,days):
            if alt>=0:
                x,y = self.to_xy(alt,az)
                s.append('<circle cx="%.4f" cy="%.4f" r="%s" />\n' % (x,y,0.2))
        time4_ts = time.thread_time_ns()*0.000001
        # mark first point of Aries (March equinox, in northern hemisphere
        # spring equinox)
        # Note: The first point of Aries is the origin of right ascension.
        #       That is the reason this equinox is marked and the other one
        #       is not. 
        #       The difference between the words "first point of Aries" and
        #       "equinox" is that the former refers to the position on the
        #       celestial globe and the latter to the date and time of the
        #       event.
        dot = Star(ra_hours=0,dec_degrees=0,epoch=time_ti)
        apparent = observer.at(time_ti).observe(dot).apparent()
        alt, az, _ = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
        x,y = self.to_xy(alt.degrees,az.radians)
        s.append('<circle cx="%.4f" cy="%.4f" r="%s"><title>%s</title></circle>\n' % (x,y,0.5,self.get_text('First point of Aries')))
        logdbg("ecliptic elapsed CPU time %.3fms %.3fms %.3fms %.3fms" % (time1_ts-time0_ts,time2_ts-time1_ts,time3_ts-time2_ts,time4_ts-time3_ts))
        s.append('</g>\n')
        return ''.join(s)

    def get_text(self, text):
        """ get localized text """
        return self.labels.get(text,text)

    def skymap(self, almanac_obj):
        """ create SVG image of the sky with heavenly bodies
        
            Despite they are not visible due to the light of the day, the 
            planets are included in the map all day long. The diameter
            of the bodies is not according to scale.
        """
        log_start_ts = time.time()
        time0_ts = time.thread_time_ns()*0.000001
        ordinates = almanac_obj.formatter.ordinate_names
        time_ti = user.skyfieldalmanac.timestamp_to_skyfield_time(almanac_obj.time_ts)
        observer = SkymapBinder.get_observer(almanac_obj)
        station = wgs84.latlon(almanac_obj.lat,almanac_obj.lon,elevation_m=almanac_obj.altitude)
        width = self.width if self.width else 800
        s = [
            SkymapAlmanacType.SVG_START % (width,width),
            # SVG description (always in English, not presented to the user)
            '<desc>Sky map for %.4f&deg; %s, %08.4f&deg; %s on %s</desc>\n' % (
                abs(self.almanac_obj.lat),
                'N' if self.almanac_obj.lat>=0 else 'S',
                abs(self.almanac_obj.lon),
               'E' if self.almanac_obj.lon>=0 else 'W',
                time.strftime("%Y-%m-%dT%H:%M:%S %Z",time.localtime(self.almanac_obj.time_ts))
            ),
            '<defs><clipPath id="weewxskymapbackgroundclippath"><circle cx="0" cy="0" r="89.8" /></clipPath></defs>\n'
        ]
        # background
        alt, _, _ = observer.at(time_ti).observe(user.skyfieldalmanac.ephemerides['sun']).apparent().altaz()
        if alt.degrees>(-0.27):
            # light day (sun above horizon)
            background_color = self.day_color
            moon_background_color = '#cfcfe6'
        elif alt.degrees<(-18):
            # dark night (sun below 18 degrees below the horizon)
            background_color = self.night_color
            moon_background_color = '#2a2927'
        else:
            # dawn (sun between 18 degrees and 0.27 degrees below the horizon)
            dawn = 3.0-abs(alt.degrees)/6.0
            background_color = tuple([int(n+dawn*dawn*(d-n)/9.0) for n,d in zip(self.night_color,self.day_color)])
            moon_background_color = "#%02X%02X%02X" % tuple([int(n+dawn*dawn*(d-n)/9.0) for n,d in zip((42,41,39),(207,207,230))])
        background_color = "#%02X%02X%02X" % background_color
        s.append('<circle cx="0" cy="0" r="90" fill="%s" stroke="currentColor" stroke-width="0.4" />\n' % background_color)
        # start clipping
        s.append('<g clip-path="url(#weewxskymapbackgroundclippath)">\n')
        # altitude scale
        s.append('<path fill="none" stroke="#808080" stroke-width="0.2" d="M-90,0h180M0,-90v180')
        for i in range(11):
            if i!=5:
                s.append('M%s,-1.5v3M-1.5,%sh3' % (i*15-75,i*15-75))
        s.append('" />\n')
        for i in range(11):
            if i!=5:
                s.append('<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="middle" dominant-baseline="text-top">%s&deg;</text>' % (i*15-75,6,i*15+15 if i<5 else 165-i*15))
                s.append( '<text x="%s" y="%s" style="font-size:5px" fill="#808080" text-anchor="start" dominant-baseline="middle">%s&deg;</text>' % (2.5,i*15-75,i*15+15 if i<5 else 165-i*15))
        # celestial pole and equator
        # displayed for latitude more than 5 degrees north or south only
        if abs(almanac_obj.lat)>5.0:
            # coordinate of celestial pole in the diagram
            y1 = almanac_obj.lat-90 if almanac_obj.lat>=0 else 90+almanac_obj.lat
            # northern or southern hemisphere
            y2 = 0 if almanac_obj.lat>=0 else 1
            # semi-major axis
            x1 = 90.0/numpy.cos(numpy.arcsin((90.0-abs(almanac_obj.lat))/90.0))
            # name of the celestial pole
            txt = ordinates[0 if almanac_obj.lat>=0 else 8]
            # mark of celestial pole and line of celestial equator
            s.append(
                '<path fill="none" stroke="#808080" stroke-width="0.2" d="M-2.5,%.4fh5M-90,0A%s,90 0 0 %s 90,0" />\n' % (
                y1,x1,y2))
            # label of the celestial pole
            s.append( 
                '<text x="-3.5" y="%s" style="font-size:5px" fill="#808080" text-anchor="end" dominant-baseline="middle">%s</text>\n' % (
                y1,txt))
            # circle of right ascension
            s.append(self.circle_of_right_ascension(observer, almanac_obj, time_ti))
        time1_ts = time.thread_time_ns()*0.000001
        # ecliptic
        if self.show_ecliptic:
            s.append(self.circle_of_ecliptic(observer, almanac_obj, time_ti))
        time2_ts = time.thread_time_ns()*0.000001
        # stars
        df = user.skyfieldalmanac.stars
        logdbg("stars: user.skyfieldalmanac.stars %s, self.show_stars %s" % (df is not None,self.show_stars))
        if df is not None and self.show_stars:
            # format
            format = self.formats.get('stars',('mag','#ff0'))
            varsize = format[0].lower()=='mag'
            if not varsize:
                r = weeutil.weeutil.to_float(format[0])
            col = format[1]
            s.append('<g fill="%s" stroke="none">\n' % col)
            # filter
            df = df[df['magnitude'] <= self.max_magnitude]
            # create Star instance
            selected_stars = Star.from_dataframe(df)
            # calculate all the positions in the sky
            apparent = observer.at(time_ti).observe(selected_stars).apparent()
            alts, azs, distances = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
            for alt, az, distance, mag, hip in zip(alts.degrees,azs.radians,distances.light_seconds()/31557600,df['magnitude'],df.index):
                if alt>=0:
                    x,y = self.to_xy(alt,az)
                    if varsize: r = SkymapBinder.magnitude_to_r(mag)
                    if mag<=self.star_tooltip_max_magnitude:
                        txt = user.skyfieldalmanac.hip_to_starname(hip,'')
                        if txt: txt += '\n'
                        txt += 'HIP%s\n' % hip
                        if distance:
                            txt += '%s: %.0f %s\n' % (self.get_text('Distance'),distance,'Lj')
                        txt = '><title>%s%s: %.2f</title></circle>' % (txt,self.get_text('Magnitude'),mag)
                    else:
                        txt = ' />'
                    s.append('<circle id="HIP%s" cx="%.4f" cy="%.4f" r="%.2f"%s\n' % (hip,x,y,r,txt))
            s.append('</g>\n')
        time3_ts = time.thread_time_ns()*0.000001
        # bodies
        dots = []
        for body in (self.bodies+self.earthsatellites):
            format = self.formats.get(body,self.formats.get('%s_*' % body.split('_')[0]))
            body_eph = user.skyfieldalmanac.ephemerides[body.lower()]
            if isinstance(body_eph,EarthSatellite):
                apparent = (body_eph-station).at(time_ti)
                label = '%s (#%s)' % (self.labels.get(body,body_eph.name),body_eph.model.satnum)
                short_label = body_eph.name
                if body_eph.name.startswith('GPS ') and '(PRN' in body_eph.name:
                    i = body_eph.name.index('(PRN')
                    if i>=0:
                        short_label = body_eph.name[i+4:].split(')')[0].strip()
                elif '(GALILEO' in body_eph.name:
                    i = body_eph.name.index('(GALILEO')
                    if body_eph.name[i+8]=='-': i += 1
                    short_label = body_eph.name[i+8:].split(')')[0].strip()
                elif body_eph.name.startswith('METEOSAT-'):
                    i = body_eph.name.index('(MSG-')
                    short_label = body_eph.name[i+5:].split(')')[0].strip()
                magnitude = None
            else:
                apparent = observer.at(time_ti).observe(body_eph).apparent()
                label = self.get_text(body)
                short_label = label
                try:
                    magnitude = planetary_magnitude(apparent)
                except (AttributeError,ArithmeticError,ValueError,TypeError):
                    magnitude = None
            alt, az, distance = apparent.altaz(temperature_C=almanac_obj.temperature,pressure_mbar=almanac_obj.pressure)
            if alt.degrees>=0:
                ra, dec, _ = apparent.radec('date')
                x,y = self.to_xy(alt.degrees,az.radians)
                dir = int(round(az.degrees/22.5,0))
                if dir==16: dir = 0
                # horizontal coordinate system: altitude, azimuth
                # rotierendes äquatoriales Koordinatensystem: ra dec
                # ortsfestes äquatoriales Koordindatensystem: ha dec
                txt = '%s\n%s=%.1f&deg; %s=%.1f&deg; %s\nra=%.1fh dec=%.1f&deg;' % (
                    label,
                    self.get_text('Altitude'),alt.degrees,
                    self.get_text('Azimuth'),az.degrees,ordinates[dir],
                    ra.hours,dec.degrees)
                phase = None
                if body=='sun':
                    # sun (radius about 16/60°)
                    radius = user.skyfieldalmanac.SUN_RADIUS_KM/distance.km*RAD2DEG
                    r = 4
                elif body=='moon':
                    # earth moon
                    #radius = _moon_radius_m/distance.m*RAD2DEG
                    radius = user.skyfieldalmanac.MEAN_MOON_RADIUS_KM/distance.km*RAD2DEG
                    r = 2
                    phase = skyfield.almanac.moon_phase(user.skyfieldalmanac.sun_and_planets,time_ti)
                    moon_index = int((phase.degrees/360.0 * 8) + 0.5) & 7
                    ptext = almanac_obj.moon_phases[moon_index]
                    txt += '\n%s: %.0f&deg; %s' % (self.get_text('Phase').capitalize(),phase.degrees,ptext)
                elif body in user.skyfieldalmanac.planets_list and magnitude is not None:
                    # planets other than earth
                    radius = user.skyfieldalmanac.SIZES[body.split('_')[0]][0]/distance.km*RAD2DEG
                    r = SkymapBinder.magnitude_to_r(magnitude)
                    """
                    r = (6.0-magnitude)*0.1
                    if r<0.2: r = 0.2
                    """
                else:
                    # other heavenly objects including Pluto
                    radius = None
                    r = 0.2
                if body in {'mars','mars_barycenter'}:
                    col = '#ff8f5e'
                elif body=='moon':
                    #col = ['rgba(255,243,228,0.3)','#ffecd5']
                    col = [moon_background_color,'#ffecd5']
                else:
                    col = '#ffffff'
                shape = None
                if format:
                    if format[0] and format[0]!='mag': 
                        r = weeutil.weeutil.to_float(format[0])
                    if format[1] and format[1][0]=='#': 
                        col = format[1]
                    if len(format)>=3 and format[2]:
                        shape = format[2]
                else:
                    short_label = None
                if radius:
                    dm, ds = divmod(radius*2.0*3600,60)
                    if dm>0:
                        txt += '\n%s: %.0f&prime;%.1f&Prime;' % (self.get_text('Apparent size'),dm,ds)
                    else:
                        txt += '\n%s: %.1f&Prime;' % (self.get_text('Apparent size'),ds)
                # According to ISO 31 the thousand separator is a thin space
                # independent of language.
                unit = almanac_obj.formatter.get_label_string("km")
                if not unit: unit = " km"
                txt += '\n{:}: {:_.0f}{:}'.format(self.get_text('Distance').capitalize(),distance.km,unit).replace('_','&#8239;')
                if magnitude:
                    txt += '\n%s: %.2f' % (self.get_text('Magnitude'),magnitude)
                if isinstance(body_eph,EarthSatellite):
                    point = wgs84.geographic_position_of(body_eph.at(time_ti))
                    txt += '\n{:}: {:.4f}&deg; {:}, {:.4f}&deg; {:}, {:_.0f}{:}'.format(
                        self.get_text('Position'),
                        abs(point.latitude.degrees),
                        ordinates[0 if point.latitude.degrees>=0.0 else 8],
                        abs(point.longitude.degrees),
                        ordinates[4 if point.longitude.degrees>=0.0 else 12],
                        point.elevation.km,
                        unit).replace('_','&#8239;')
                dots.append((body,txt,x,y,r,distance,col,radius,phase,short_label,shape))
        time4_ts = time.thread_time_ns()*0.000001
        dots.sort(key=lambda x:-x[5].km)
        for dot in dots:
            if dot[0]=='moon':
                s.append(moon(*dot))
            else:
                s.append('<g id="%s"><title>%s</title>\n' % (dot[0],dot[1]))
                if dot[10]=='square':
                    s.append('<rect x="%.4f" y="%.4f" width="%.4f" height="%.4f" fill="%s" stroke="none" />\n' % (dot[2]-dot[4],dot[3]-dot[4],2*dot[4],2*dot[4],dot[6]))
                elif dot[10]=='rhombus':
                    a2 = 1.414213562373095*dot[4]
                    s.append('<path fill="%s" stroke="none" d="M%.4f,%.4fl%.4f,%.4fl%.4f,%.4fl%.4f%.4fz" />\n' % (dot[6],dot[2],dot[3]-a2,a2,a2,-a2,a2,-a2,-a2))
                elif dot[10]=='triangle':
                    a2 = 0.866025403784439*dot[4]
                    s.append('<path fill="%s" stroke="none" d="M%.4f,%.4fh%.4fl%.4f,%.4fz" />\n' % (dot[6],dot[2]-a2,dot[3]+0.5*dot[4],2*a2,-a2,-1.5*dot[4]))
                else:
                    s.append( '<circle cx="%.4f" cy="%.4f" r="%.2f" fill="%s" stroke="none" />\n' % (dot[2],dot[3],dot[4],dot[6]))
                if dot[9] and len(dot[9])<=2:
                    s.append('<text x="%.4f" y="%.4f" font-size="%s" fill="#fff" text-anchor="middle" dominant-baseline="middle">%s</text>' % (dot[2],dot[3],dot[4]*1.2,dot[9]))
                s.append('</g>\n')
        time5_ts = time.thread_time_ns()*0.000001
        # end clipping
        s.append('</g>\n')
        # azimuth scale
        s.append('<path fill="none" stroke="currentColor" stroke-width="0.4" d="')
        for i in range(24):
            azh = i*15*DEG2RAD
            x1,y1 = self.to_xy(0,azh)
            x2,y2 = self.to_xy(-3,azh)
            s.append("M%.4f,%.4fL%.4f,%.4f" % (x1,y1,x2,y2))
        s.append('" />\n')
        for i in range(24):
            azh = i*15*DEG2RAD
            if i==19 or i==7:
                azh += 1.5*DEG2RAD
            elif i==17:
                azh -= 1.5*DEG2RAD
            #x,y = self.to_xy(-8,azh)
            x,y = self.inout*99*numpy.sin(azh),-97*numpy.cos(azh)
            if i==0:
                txt = ordinates[0] # north
            elif i==6:
                txt = ordinates[4] # east
                x -= 3*self.inout
            elif i==12:
                txt = ordinates[8] # south
            elif i==18:
                txt = ordinates[12] # west
                x += 2*self.inout
            else:
                txt = "%d°" % (i*15)
            s.append('<text x="%.4f" y="%.4f" style="font-size:5px" fill="currentColor" text-anchor="middle" dominant-baseline="middle">%s</text>\n' % (x,y,txt))
        if self.show_timestamp:
            # sidereal time
            sidereal_time = station.lst_hours_at(time_ti)*3600
            sd = time.strftime("%H:%M:%S",time.gmtime(sidereal_time))
            s.append('<text x="97" y="-93" font-size="5" fill="currentColor" text-anchor="end">%s</text>\n' % self.get_text('Sidereal time'))
            s.append('<text x="97" y="-87" font-size="5" fill="currentColor" text-anchor="end">%s</text>\n' % sd)
            # solar time
            ha, _, _ = observer.at(time_ti).observe(user.skyfieldalmanac.ephemerides['sun']).apparent().hadec()
            solar_time = (ha.hours-12.0)*3600
            sd = time.strftime("%H:%M:%S",time.gmtime(solar_time))
            s.append('<text x="-97" y="-93" font-size="5" fill="currentColor" text-anchor="start">%s</text>\n' % self.get_text('Solar time'))
            s.append('<text x="-97" y="-87" font-size="5" fill="currentColor" text-anchor="start">%s</text>\n' % sd)
            # civil time
            time_vt = ValueHelper(ValueTuple(almanac_obj.time_ts,'unix_epoch','group_time'),'ephem_year',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            time_s = str(time_vt).split(' ')
            s.append('<text x="97" dy="87" font-size="5" fill="currentColor" text-anchor="end">%s</text>\n' % time_s[0])
            if len(time_s)>1 and time_s[1]:
                s.append('<text x="97" y="93" font-size="5" fill="currentColor" text-anchor="end">%s</text>\n' % time_s[1])
        if self.show_location:
            lat_vt = ValueHelper(ValueTuple(abs(almanac_obj.lat),'degree_compass','group_direction'),'current',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            lon_vt = ValueHelper(ValueTuple(abs(almanac_obj.lon),'degree_compass','group_direction'),'current',formatter=almanac_obj.formatter,converter=almanac_obj.converter)
            lat_s = lat_vt.format("%8.4f")
            lon_s = lon_vt.format("%08.4f")
            if self.location:
                s.append('<text x="-97" y="87" font-size="5" fill="currentColor" text-anchor="start">%s</text>\n' % self.location)
                s.append('<text x="-97" y="92" font-size="3.5" fill="currentColor" text-anchor="start">%s %s, %s %s</text>\n' % (
                    lat_s.strip(),ordinates[0 if almanac_obj.lat>=0 else 8],
                    lon_s,ordinates[4 if almanac_obj.lon>=0 else 12]
                ))
            else:
                s.append('<text x="-97" y="87" font-size="5" fill="currentColor" text-anchor="start">%s %s</text>\n' % (
                    lat_s.replace(' ','&numsp;'),
                    ordinates[0 if almanac_obj.lat>=0 else 8]))
                s.append('<text x="-97" y="93" font-size="5" fill="currentColor" text-anchor="start">%s %s</text>\n' % (
                    lon_s,ordinates[4 if almanac_obj.lon>=0 else 12]))
        #s.append(moonphasetest())
        datasource = ['IERS']
        if self.bodies: datasource.append('JPL')
        if self.show_stars: datasource.append('ESA') # Hipparcos
        if self.earthsatellites: datasource.append('CelesTrak')
        s.append('<text x="-97" y="97" font-size="3" fill="#808080" text-anchor="start">%s: %s</text>\n' % (self.get_text('Data source'),', '.join(datasource)))
        s.append('<text x="97" y="97" font-size="3" fill="#808080" text-anchor="end">%s</text>\n' % self.credits)
        s.append(SkymapAlmanacType.SVG_END)
        time6_ts = time.thread_time_ns()*0.000001
        log_end_ts = time.time()
        logdbg("skymap elapsed CPU time %.0fms %.0fms %.0fms %.0fms %.0fms %.0fms" % (time1_ts-time0_ts,time2_ts-time1_ts,time3_ts-time2_ts,time4_ts-time3_ts,time5_ts-time4_ts,time6_ts-time5_ts))
        logdbg("skymap elapsed time %.2f seconds" % (log_end_ts-log_start_ts))
        return ''.join(s)


class MoonSymbolBinder:
    """ SVG image of the moon showing her phase """

    def __init__(self, almanac_obj, labels, colors):
        self.almanac_obj = almanac_obj
        self.labels = labels
        self.colors = colors
        self.width = 50
    
    def __call__(self, width=None):
        if width:
            self.width = weeutil.weeutil.to_int(width)
        return self
    
    def __str__(self):
        return self.moon_symbol()
    
    def moon_symbol(self):
        """ create an SVG image of the moon showing her phases """
        time_ti = user.skyfieldalmanac.timestamp_to_skyfield_time(self.almanac_obj.time_ts)
        phase = skyfield.almanac.moon_phase(user.skyfieldalmanac.sun_and_planets,time_ti)
        moon_index = int((phase.degrees/360.0 * 8) + 0.5) & 7
        ptext = self.almanac_obj.moon_phases[moon_index]
        txt = self.labels.get('moon','moon').capitalize()
        txt += '\n%s: %.0f&deg; %s' % (self.labels.get('Phase','Phase').capitalize(),phase.degrees,ptext)
        return '%s%s%s' % (
            SkymapAlmanacType.SVG_START % (self.width,self.width),
            moon('moon', txt, 0, 0, 100, None, self.colors, None, phase,'moon',None),
            SkymapAlmanacType.SVG_END
        )
        return s


class AnalemmaBinder:
    """ SVG image of analemma """
    
    SVG_START = '''<svg
  width="%s" height="%s" 
  viewBox="%s %s %s %s"
  xmlns="http://www.w3.org/2000/svg">
'''
    SVG_END = '</svg>\n'
    
    def __init__(self, config_dict, station_location, almanac_obj, labels):
        self.credits = '&copy; ' + station_location
        self.location = station_location
        self.almanac_obj = almanac_obj
        self.labels = labels
        self.colors = config_dict.get('analemma_colors',['currentColor','#808080','#7cb5ec','#f7a35c'])
        self.width = 280
        self.height = 300
        self.tz = "civil"
        self.show_timestamp = weeutil.weeutil.to_bool(config_dict.get('show_timestamp',True))
        self.show_location = weeutil.weeutil.to_bool(config_dict.get('show_location',True))

    def __call__(self, **kwargs):
        for key in kwargs:
            if key in {'width','height'}:
                self.width = weeutil.weeutil.to_int(kwargs[key])
            elif key in {'show_timestamp','show_location'}:
                setattr(self,key,weeutil.weeutil.to_bool(kwargs[key]))
            else:
                setattr(self,key,kwargs[key])
        return self

    def __str__(self):
        try:
            return self.analemma()
        except Exception as e:
            logerr("analemma %s %s" % (e.__class__.__name__,e))
            return ""
    
    def analemma(self):
        """ create an SVG image of an analemma """
        # diagram area
        fontsize = self.height/25
        x0 = int(fontsize*3)
        y0 = int(self.height-fontsize*2.7)
        width = int(self.width-x0-fontsize)
        height = int(self.height-fontsize*(2.7+2.2+(1.1 if self.show_timestamp or self.show_location else 0.0)))
        # midnight at the beginning of the year
        year = weeutil.weeutil.archiveYearSpan(self.almanac_obj.time_ts)
        # time of day
        hms = (self.almanac_obj.time_ts-year[0])%86400
        # convert to Skyfield time
        time_ti = user.skyfieldalmanac.timestamp_to_skyfield_time(year[0]+hms)
        t0 = user.skyfieldalmanac.timestamp_to_skyfield_time(year[0])
        t1 = user.skyfieldalmanac.timestamp_to_skyfield_time(year[1])
        logdbg("analemma year=(%s,%s) ti=%s" % (t0,t1,time_ti))
        # list of the days of a year
        days = user.skyfieldalmanac.ts.ut1_jd([time_ti.ut1+i for i in range(365)])
        # location
        observer, horizon, body = user.skyfieldalmanac._get_observer(self.almanac_obj,user.skyfieldalmanac.SUN,False)
        # Sun's positions
        alts, azs, _ = observer.at(days).observe(body).apparent().altaz()
        # Min and max
        min_alt = numpy.floor(numpy.min(alts.degrees)-3)
        max_alt = numpy.ceil(numpy.max(alts.degrees)+3)
        min_az = numpy.floor(numpy.min(azs.degrees)-1.5)
        max_az = numpy.ceil(numpy.max(azs.degrees)+1.5)
        # Scale
        if abs(max_alt-min_alt)>=40:
            yscale = 10
        else:
            yscale = 5
        min_alt = numpy.floor(min_alt/yscale)*yscale
        max_alt = numpy.ceil(max_alt/yscale)*yscale
        xscale = abs(max_az-min_az)/width*fontsize*4
        if xscale<1.5:
            xscale = 1
        elif xscale<2.5:
            xscale = 2
        elif xscale<6:
            xscale = 5
        elif xscale<12:
            xscale = 10
        min_az = numpy.floor(min_az/xscale)*xscale
        max_az = numpy.ceil(max_az/xscale)*xscale
        logdbg("analemma min_alt=%s max_alt=%s min_az=%s max_az=%s" % (min_alt,max_alt,min_az,max_az))
        # Seasons
        t_season, k_season = skyfield.almanac.find_discrete(t0,t1,skyfield.almanac.seasons(user.skyfieldalmanac.sun_and_planets))
        t = user.skyfieldalmanac.ts.ut1_jd(numpy.round(t_season.ut1-time_ti.ut1,0)+time_ti.ut1)
        alt_season, az_season, _ = observer.at(t).observe(body).apparent().altaz()
        logdbg("analemma seasons %s" % t_season)
        logdbg("analemma seasons alt %s" % alt_season)
        logdbg("analemma seasons az %s" % az_season)
        # convert positions to SVG coordinates
        x_factor = width/(max_az-min_az)
        y_factor = height/(min_alt-max_alt)
        ys = (alts.degrees-min_alt)*y_factor+y0
        xs = (azs.degrees-min_az)*x_factor+x0
        y_season = (alt_season.degrees-min_alt)*y_factor+y0
        x_season = (az_season.degrees-min_az)*x_factor+x0
        s = []
        # SVG header
        s.append(AnalemmaBinder.SVG_START % (self.width,self.height,0,0,self.width,self.height))
        # SVG description (always in English, not presented to the user)
        s.append('<desc>Analemma for %.4f&deg; %s, %08.4f&deg; %s for the year %s at %s</desc>\n' % (
            abs(self.almanac_obj.lat),
            'N' if self.almanac_obj.lat>=0 else 'S',
            abs(self.almanac_obj.lon),
            'E' if self.almanac_obj.lon>=0 else 'W',
            time.strftime("%Y",time.localtime(self.almanac_obj.time_ts)),
            time.strftime("%H:%M:%S %Z",time.localtime(self.almanac_obj.time_ts))
        ))
        s.append('<rect x="%s" y="%s" width="%s" height="%s" stroke="%s" stroke-width="1" fill="none" />\n' % (
            x0,y0-height,width,height,self.colors[0]))
        # y scale
        for i in range(int(min_alt),int(max_alt)+yscale,yscale):
            y = (i-min_alt)*y_factor+y0
            if int(min_alt)<i<int(max_alt):
                s.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" />\n' % (x0,y,x0+width,y,self.colors[1]))
            s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="end" dominant-baseline="middle">%s&deg;</text>\n' % (x0-3,y,self.colors[0],fontsize,i))
        s.append('<text x="%.2f" y="%.2f" fill="currentColor" font-size="%s" text-anchor="middle" dominant-baseline="middle" transform="rotate(270,%.2f,%.2f)">%s</text>\n' % (
            x0-2.3*fontsize,y0-0.5*height,fontsize,x0-2.3*fontsize,y0-0.5*height,self.labels.get('Altitude','Altitude')))
        # x scale
        for i in range(int(min_az),int(max_az)+xscale,xscale):
            x = (i-min_az)*x_factor+x0
            s.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" />\n' % (x,y0,x,y0-height,self.colors[1]))
            s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="middle" dominant-baseline="middle">%s&deg;</text>\n' % (
                x,y0+fontsize*1.1,self.colors[0],fontsize,i%360))
        s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="middle" dominant-baseline="middle">%s</text>\n' % (
            x0+0.5*width,y0+fontsize*2.2,self.colors[0],fontsize,self.labels.get('Azimuth','Azimuth')))
        # analemma
        s.append('<path stroke="%s" stroke-width="2" fill="none" d="M%s,%s' % (self.colors[2],xs[0],ys[1]))
        for x,y in zip(xs,ys):
            s.append('L%.2f,%.2f' % (x,y))
        s.append('z" />\n')
        # seasons
        r = fontsize/3
        for x,y,t,w in zip(x_season,y_season,user.skyfieldalmanac.skyfield_time_to_djd(t_season),k_season):
            time_vt = ValueHelper(ValueTuple(t,'dublin_jd','group_time'),'ephem_year',formatter=self.almanac_obj.formatter,converter=self.almanac_obj.converter)
            time_s = str(time_vt).split(' ')[0]
            s.append('<circle cx="%.2f" cy="%.2f" r="%s" fill="%s" stroke="none" />\n' % (x,y,r,self.colors[3]))
            if w==0:
                anchor = "end"
                xoffset = -2*r
                yoffset = 0
            elif w==2:
                anchor = "start"
                xoffset = 2*r
                yoffset = 0
            else:
                c = (x-x0)/width
                if c<0.33333333:
                    anchor = "start"
                    xoffset = -r
                elif c<0.66666666:
                    anchor = "middle"
                    xoffset = 0
                else:
                    anchor = "end"
                    xoffset = r
                if w==1:
                    yoffset = -0.8*fontsize
                else:
                    yoffset = fontsize
            s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="%s" dominant-baseline="middle">%s</text>\n' % (
                x+xoffset,y+yoffset,self.colors[3],fontsize*1.1,anchor,time_s))
        # caption
        s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="middle">%s</text>\n' % (
            0.5*self.width,fontsize*1.5,self.colors[0],fontsize*1.5,self.labels.get("Analemma","Analemma")))
        formatter = self.almanac_obj.formatter
        txt = ""
        if self.show_timestamp:
            # timestamp
            if self.tz.upper() in {'LMT','UTC'}:
                # Local Mean Time or UTC
                format = self.almanac_obj.formatter.time_format_dict.get('ephem_day','%H:%M:%S').replace('%a','').strip()
                if self.tz.upper()=='LMT':
                    localtime = self.almanac_obj.time_ts+self.almanac_obj.lon*240
                    tz = self.labels.get("local mean time","mittlere Ortszeit")
                else:
                    localtime = self.almanac_obj.time_ts
                    tz = "UTC"
                txt = "%s %s" % (
                    time.strftime(format,time.gmtime(localtime)),
                    tz
                )
            else:
                # Civil time according to the actual time zone
                time_vt = ValueHelper(ValueTuple(self.almanac_obj.time_ts,'unix_epoch','group_time'),'ephem_day',formatter=formatter,converter=self.almanac_obj.converter)
                txt = str(time_vt)
        if self.show_location:
            # location
            if self.location:
                # location described by a name
                txt = "%s, %s" % (txt,self.location)
            else:
                # location described by geographic coordinates
        # location
                lat_vt = ValueHelper(ValueTuple(abs(self.almanac_obj.lat),'degree_compass','group_direction'),'current',formatter=formatter,converter=self.almanac_obj.converter)
                lon_vt = ValueHelper(ValueTuple(abs(self.almanac_obj.lon),'degree_compass','group_direction'),'current',formatter=formatter,converter=self.almanac_obj.converter)
                lat_s = lat_vt.format("%.4f").replace(' ','&numsp;')
                lon_s = lon_vt.format("%08.4f")
                txt = "%s, %s&thinsp;%s, %s&thinsp;%s" % (
                    txt,
                    lat_s,
                    formatter.ordinate_names[0 if self.almanac_obj.lat>=0 else 8],
                    lon_s,
                    formatter.ordinate_names[4 if self.almanac_obj.lon>=0 else 12]
                )
        s.append('<text x="%.2f" y="%.2f" fill="%s" font-size="%s" text-anchor="middle">%s</text>\n' % (
            0.5*self.width,fontsize*2.7,self.colors[0],fontsize*1.1,txt))
        s.append(AnalemmaBinder.SVG_END)
        return "".join(s)


def moon(id, txt, x, y, r, distance, col, radius, phase, short_label, shape):
    """ create SVG image of the moon showing her phase """
    phase = round(phase.degrees,1)%360
    full_moon = phase==180.0
    new_moon = phase==0.0
    s = []
    s.append('<g><title>%s</title>\n' % txt)
    s.append('<circle cx="%.4f" cy="%.4f" r="%s" fill="%s" stroke="none" />\n' % (x,y,r,col[1] if full_moon else col[0]))
    if not full_moon and not new_moon:
        desc = 0 if phase>180.0 else 1
        phase180 = phase%180
        quarter = 0 if phase180<90 else 1
        fullness = (phase180-90.0 if phase180>90.0 else 90.0-phase180)/90.0
        s.append('<path fill="%s" stroke="none" d="M%.4f,%.4fa%.4f,%.4f 0 0 %s %.4f,%.4f' % (col[1],x,y-r,r,r,desc,0,2*r))
        if phase!=90.0 and phase!=270.0:
            s.append('a%.4f,%.4f 0 0 %s %.4f %.4f' % (fullness*r,r,quarter,0,-2*r))
        s.append('z" />\n')
    s.append('</g>\n')
    return ''.join(s)
    
def moonphasetest():
    """ test moon phases in the moon symbol """
    s = ""
    s+=moon('30',-50,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=30),'',None)
    s+=moon('60',-30,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=60),'',None)
    s+=moon('90',-10,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=90),'',None)
    s+=moon('120',10,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=120),'',None)
    s+=moon('150',30,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=150),'',None)
    s+=moon('180',50,90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=180),'',None)
    s+=moon('210',-50,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=210),'',None)
    s+=moon('240',-30,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=240),'',None)
    s+=moon('270',-10,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=270),'',None)
    s+=moon('300',10,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=300),'',None)
    s+=moon('330',30,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=330),'',None)
    s+=moon('360',50,-90,10,None,['rgba(255,243,228,0.3)','#ffecd5'],0,skyfield.units.Angle(degrees=360),'',None)
    return s


class SkymapService(StdService):
    """ Service to initialize the Skymap almanac extension """

    def __init__(self, engine, config_dict):
        """ init this extension """
        super(SkymapService,self).__init__(engine, config_dict)
        # directory to save ephemeris and IERS files
        sqlite_root = config_dict.get('DatabaseTypes',configobj.ConfigObj()).get('SQLite',configobj.ConfigObj()).get('SQLITE_ROOT','.')
        self.path = os.path.join(sqlite_root,'skyfield')
        # configuration
        alm_conf_dict = _get_config(config_dict)
        if alm_conf_dict['enable']:
            alm_conf_dict['Texts'] = self.process_language(config_dict)
            # instantiate the Skymap almanac
            self.skymap_almanac = SkymapAlmanacType(alm_conf_dict, self.path, engine.stn_info.location)
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

    def process_language(self, config_dict):
        """ get language dependend words
        
            Unfortunately `$alamanac` does only provide language dependend 
            words for the moon phases and the compass directions. The skin's
            language configuration data is not available. This is the
            workaround.
            
            This method searches the WeeWX configuration (which is derived 
            from `weewx.conf`) for all language codes used. Then it loads
            the respective language files for the Seasons skin and extracts
            words used in astronomy or almanac.
            
            List of the planets' names in different languages:
            https://en.wiktionary.org/wiki/Appendix:Planets
        """
        languages = []
        lang_dict = dict()
        # Report configuration section
        rpt_conf_dict = config_dict.get('StdReport',configobj.ConfigObj())
        # Skins directory
        skin_root = rpt_conf_dict.get('SKIN_ROOT')
        skin_root = os.path.join(config_dict.get('WEEWX_ROOT','.'),skin_root)
        # Search configuration for language codes
        for rpt in rpt_conf_dict.sections:
            if 'lang' in rpt_conf_dict[rpt]:
                languages.append(rpt_conf_dict[rpt]['lang'])
        languages = set(languages)
        logdbg('languages used in this WeeWX instance: %s' % languages)
        for lang in languages:
            conf = dict()
            if lang=='en' or lang.startswith('en_'):
                conf.update({
                    'Solar time':'Solar time',
                    'Sidereal time':'Sidereal time',
                    'Distance':'Distance',
                    'Data source':'Data source',
                    'Magnitude':'Magnitude',
                    'First point of Aries':'First point of Aries',
                    'Apparent size':'Apparent size'
                })
            if lang=='de' or lang.startswith('de_'):
                conf.update({
                    'Solar time':'Sonnenzeit',
                    'Sidereal time':'Sternzeit',
                    'Distance':'Entfernung',
                    'Data source':'Datenquelle',
                    'Magnitude':'Magnitude',
                    'First point of Aries':'Frühlingspunkt',
                    'Apparent size':'Scheinbare Größe',
                    # planet names that are different from English
                    'mercury':'Merkur',
                    'mercury_barycenter':'Merkur',
                    'neptune':'Neptun',
                    'neptune_barycenter':'Neptun',
                })
            if lang in {'cz','cs'} or lang.startswith('cz_') or lang.startswith('cs_'):
                conf.update({
                    'Solar time':'Sluneční čas',
                    'Sidereal time':'Hvězdný čas',
                    'Distance':'Vzdálenost',
                    'Magnitude':'Hvězdná velikost',
                    'First point of Aries':'Jarní bod',
                    # planet names that are different from English
                    'mercury':'Merkur',
                    'venus':'Venuše',
                    'earth':'Země',
                    'uranus':'Uran',
                    'uranus_barycenter':'Uran',
                    'neptune':'Neptun',
                    'neptune_barycenter':'Neptun'
                })
            if lang=='nl' or lang.startswith('nl_'):
                conf.update({
                    'Solar time':'Zonnetijd',
                    'Sidereal time':'Sterrentijd',
                    # planet names that are different from English
                    'mercury':'Mercurius',
                    'earth':'de Aarde',
                    'saturn':'Saturnus',
                    'saturn_barycenter':'Saturnus',
                    'neptune':'Neptunus',
                    'neptune_barycenter':'Neptunus'
                })
            skin = os.path.join(skin_root,'Seasons','lang')
            try:
                data = configobj.ConfigObj(os.path.join(skin,'%s.conf' % lang))
                if data:
                    # used for determining skin language
                    conf['hour'] = data.get('Units',dict()).get('Labels',dict()).get('hour')
                    conf['moon_phase_new_moon'] = data.get('Almanac',dict()).get('moon_phases',[])[0]
                    # get language dependend texts used in astronomy
                    x = data.get('Texts',dict())
                    for key in {'Azimuth','Day','Declination','Equinox','Latitude','Moon Phase','Phase','Right ascension','Sunrise','Sunset','Transit','Year','Solar time','Sidereal time'}:
                        if key in x:
                            conf[key] = x[key]
                    for key in {'Sun','Moon'}:
                        if key in x:
                            conf[key.lower()] = x[key]
                    # The language files of the Seasons skin contain an "Astronomical" section
                    astro = x.get('Astronomical',dict())
                    # Astronomical altitude and magnitude
                    for key in {'Altitude','Magnitude','Solar time','Sidereal time','First point of Aries','Apparent size'}:
                        if astro.get(key):
                            conf[key] = astro.get(key)
                    # Names of the planets
                    # Note: We need the planets' names in lowercase.
                    for key in list(user.skyfieldalmanac.PLANETS)+['ceres']:
                        if key.capitalize() in astro:
                            conf[key] = astro[key.capitalize()]
                            conf[key+'_barycenter'] = astro[key.capitalize()]
            except (OSError,ValueError) as e:
                logerr("languge '%s'; %s - %s" % (lang,e.__class__.__name__,e))
            logdbg('%s: %s' % (lang,conf))
            lang_dict[lang] = conf
        return lang_dict
