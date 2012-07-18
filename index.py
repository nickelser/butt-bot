#!/usr/bin/env python
import sys
import os
import re
from datetime import datetime, timedelta

from butt_bot import SavedBlipDelta

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template
import wsgiref.handlers

NUM_HOURS = 6

CHART_STR = "http://chart.apis.google.com/chart?cht=ls&chco=000000&chs=250x150&chtt=butts+per+hour&chf=bg,s,BBBBBB&chxt=x,x&chxl=0:%s1:|||hours+ago||&chd=t:%s&chds=%s"

class MainHandler(webapp.RequestHandler):
    def get(self):
        total = 0
        blips_per_hour = []
        
        for h in xrange(1, NUM_HOURS):
            start = datetime.now()-timedelta(hours=h)
            end = datetime.now()-timedelta(hours=h-1)
            blips = SavedBlipDelta.all()
            blips.filter('time_added >= ', start)
            blips.filter('time_added < ', end)
            count = blips.count()
            total += count
            blips_per_hour.append(count)
        
        blips_per_hour.reverse()
        hours_ago_str = '|%s|'%('|'.join([str(x) for x in xrange(NUM_HOURS-1, 0, -1)]))
        min_max_str = '%s,%s'%(str(min(min(blips_per_hour)-1, 0)), str(max(blips_per_hour)+1))
        data_str = ','.join([str(x) for x in blips_per_hour])
        
        template_values = {
                    'total_blips': total,
                    'chart_img': CHART_STR%(hours_ago_str, data_str, min_max_str),
                    }

        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


if __name__ == '__main__':
    application = webapp.WSGIApplication([('/', MainHandler)],
                                     debug=True)
    wsgiref.handlers.CGIHandler().run(application)