#from weewx.units import ValueTuple, ValueHelper
<script type="text/javascript">
function highlightplanet(planet)
  {
    let gr = document.getElementById(planet);
    if (gr)
      {
        //gr.parentElement.parentElement.scrollIntoView();
        let els = gr.tagName=='circle'?[gr]:gr.getElementsByTagName('circle');
        setTimeout(() => {
            for (const el of els)
              {
                let r = el.getAttribute("r");
                el.setAttribute("r","3");
                el.setAttribute("stroke","#e5554e");
                setTimeout(() => { 
                    el.setAttribute("r",r);
                    el.setAttribute("stroke","none"); 
                }, 1000);
              }
        }, 500);
      }
  }
</script>
    <p>$gettext("Values calculated for") $current.dateTime $gettext("o'clock").</p>
    <table>
    <tr>
    <th>$pgettext('Astronomical','Body')</th>
    <th style="text-align:right">$pgettext('Astronomical','Altitude')</th>
    <th style="text-align:center">$gettext('Azimuth')</th>
    <th style="text-align:right">$gettext('Right ascension')</th>
    <th style="text-align:right">$gettext('Declination')</th>
    <th style="text-align:right">$pgettext('Astronomical','Distance')</th>
    <th style="text-align:right">$pgettext('Astronomical','Magnitude')</th>
    <th>$gettext('Sunrise')</th>
    <th>$gettext('Sunset')</th>
    <th colspan="2">$pgettext('Astronomical','Distance from Sun')</th>
    </tr>
    #for $body in ['sun','moon'] + $almanac.planets + ['HIP32349','HIP30438','HIP71683','HIP69673','HIP91262','HIP24608','HIP24436']
    #set $binder = $getattr($almanac,$body)
    <tr>
    <td>$binder.name</td>
    <td style="text-align:right">$binder.altitude</td>
    <td style="text-align:right">
      $binder.azimuth
      <div style="width:2.2em;display:inline-block;text-align:left">$binder.azimuth.ordinal_compass</div>
    </td>
    #set $ra_vh = $ValueHelper(ValueTuple($binder.topo_ra.raw/15.0 if $binder.topo_ra.raw is not None else None,None,None),'day',formatter=$station.formatter)
    <td style="text-align:right">$ra_vh.format("%.1f") h</td>
    <td style="text-align:right">$binder.topo_dec</td>
    <td style="text-align:right">#slurp
    #if $body=='moon'
    $binder.topo_dist.format("%.0f")#slurp
    #else if $body.startswith('HIP')
    $binder.topo_dist.light_year.format("%.0f")#slurp
    #else
    $binder.topo_dist.gigameter#slurp
    #end if
    </td>
    #if $body in {'sun','moon'}
    <td>&nbsp;</td>
    #else
    #set $mag_vh = $ValueHelper(ValueTuple($binder.mag,None,None),'day',formatter=$station.formatter)
    <td style="text-align:right">$mag_vh.format("%.1f")</td>
    #end if
    <td>$binder.rise</td>
    <td>$binder.set</td>
    #if $body=='sun'
    <td>&mdash;</td>
    #else if $body=='moon' or $body.startswith('HIP')
    <td>&nbsp;</td>
    #else
    #set sund_vh = $ValueHelper(ValueTuple($binder.sun_distance,None,None),'day',formatter=$station.formatter)
    <td>$sund_vh.format("%.2f") AU</td>
    #end if
    <td>
    #if $binder.alt>=0
    <button type="button" class="btn btn-default btn-xs" onclick="highlightplanet('$body')">$gettext("Show")</button>
    #end if
    </td>
    </tr>
    #end for
    </table>
