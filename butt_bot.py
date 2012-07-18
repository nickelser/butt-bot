import random
import re
import logging

from waveapi import events
from waveapi import model
from waveapi import robot
from waveapi import document
from waveapi import simplejson
from google.appengine.ext import db

from buttify import buttify_blip

BUTT_FREQ = 1./6 # how often should we rudely intrude
BUTT_KEYWORD = '<butt>'
RESTORE_KEYWORD = '<unbutt>'
ME = 'butt-bot@appspot.com'
    
# Blip storage stolen shamelessly from readonliebot
class SavedBlip(db.Model):
    blip_id = db.StringProperty(multiline=False)
    text = db.TextProperty()
    annotations = db.TextProperty()
    elements = db.TextProperty()
    time_added = db.DateTimeProperty(auto_now_add=True)

# Stores blip info for later retrieving
def save_blip_info_full(blip_id, content, annotations='', elements=''):
    saved = SavedBlip()
    saved.blip_id = blip_id
    saved.text = db.Text(content)
    saved.annotations = db.Text(simplejson.dumps(annotations))
    saved.elements = db.Text(simplejson.dumps(elements))
    saved.put()
  
#  recursevely sets annotations (formatting)
def set_annotations_full(doc, annotations):
    if not annotations: return    
    
    for annotation in annotations:
        r = document.Range(annotation['range']['start'],
                            annotation['range']['end'])
                            
        doc.SetAnnotation(r, annotation['name'], annotation['value'])

def set_elements_full(doc, elements):
    if not elements: return
    
    for pos, element in elements.iteritems():
        e = document.ElementFromJson(element)
        doc.InsertElement(pos, e)

# Gets blip info from datastore
def get_saved_blip_full(blip_id):
    r = SavedBlip.all().filter("blip_id =", blip_id).fetch(1)
    
    if len(r) == 1:
        return r[0]
    else:
        return None
    
# Deletes blip info from datastore
def del_saved_blip_full(blip_id):
  r = SavedBlip.all().filter("blip_id =", blip_id).fetch(100)
    
  for entry in r:
      db.delete(entry)
    
# uses info object to set blip's properties
def set_blip_info_full(blip, info):
    doc = blip.GetDocument()
    doc.SetText(info.text+'') # concat with empy string to make it a string
    if info.annotations:
        set_annotations(doc, simplejson.loads(info.annotations))
    if info.elements:
        set_elements(doc, simplejson.loads(info.elements))

def save_blip_full(blip):
    annotations = blip.raw_data.get("annotations")
    elements = blip.raw_data.get("elements")
    txt = blip.GetDocument().GetText()
    del_saved_blip(blip.blipId)
    save_blip_info(blip.blipId, txt, annotations, elements)

def unbuttify_blip_full(blip):
    saved = get_saved_blip(blip.blipId)
    
    if saved is not None:
        logging.info('replacement found, dropping it in...')
        set_blip_info(blip, saved)
    else:
        logging.info('oops, no original blip found for blipid: '+blip.blipId)

# DELTA SPIRIT
# new blip delta storage
class SavedBlipDelta(db.Model):
    blip_id = db.StringProperty(multiline=False)
    time_added = db.DateTimeProperty(auto_now_add=True)
    delta = db.TextProperty()
    
def get_saved_blip(blip_id):
    r = SavedBlipDelta.all().filter("blip_id =", blip_id).fetch(1)

    if len(r) == 1:
        return r[0]
    else:
        return None

# Deletes blip info from datastore
def del_saved_blip(blip_id):
  r = SavedBlipDelta.all().filter("blip_id =", blip_id).fetch(100)

  for entry in r:
      db.delete(entry)

def save_blip(blip, delta):
    del_saved_blip(blip.blipId)
    saved = SavedBlipDelta()
    saved.blip_id = blip.blipId
    saved.delta = simplejson.dumps(delta)
    saved.put()

def unbuttify_blip(blip):
    saved = get_saved_blip(blip.blipId)
    
    if saved is None:
        logging.warning('user requested unbuttification of non-butted blip')
        return
        
    delta = simplejson.loads(saved.delta+'')
    if delta is not None:
        delta.reverse()
    doc = blip.GetDocument()
    txt = doc.GetText()
    
    for old, new in delta:
        s = re.search(re.escape(new), txt)
        
        if s is not None:
            r = document.Range(s.start(0), s.end(0))
            doc.SetTextInRange(r, old)
    
def buttify_doc(doc):
    txt = doc.GetText()
    replaced_pairs = buttify_blip(txt)
    delta = []
    
    if replaced_pairs is not None:
        # reverse the list to work from the back (to not interfere with the position accounting)
        replaced_pairs.reverse()
        for (word, start_pos, end_pos, old, new) in replaced_pairs:
            r = document.Range(start_pos, end_pos)
            doc.SetTextInRange(r, word)
            delta.append((old, new))
        
    return delta

def handle_keywords(properties, context):
    blip = context.GetBlipById(properties['blipId'])
    doc = blip.GetDocument()
    txt = doc.GetText().rstrip()
    
    s = re.search(BUTT_KEYWORD, txt)
    rs = re.search(RESTORE_KEYWORD, txt)
    
    if s is not None:
        doc.DeleteRange(document.Range(s.start(0), s.end(0)))
        delta = buttify_doc(doc)
        save_blip(blip, delta)
        return True
    elif rs is not None:
        logging.info('unbuttification requested for blip_id: '+blip.blipId)
        doc.DeleteRange(document.Range(rs.start(0), rs.end(0)))
        unbuttify_blip(blip)
        return True
    
    return False
    
def on_blip_submit(properties, event, context):
    blip = context.GetBlipById(properties['blipId'])
    doc = blip.GetDocument()
    
    # if no magic keywords, roll to see if the user gets butted so hard
    if not handle_keywords(properties, context) and random.random() <= BUTT_FREQ:
        delta = buttify_doc(doc)
        save_blip(blip, delta)

def on_version_change(properties, event, context):
    #logging.info('edited by: '+event.modifiedBy)
    if event.modifiedBy != ME:
        handle_keywords(properties, context)

def on_join(properties, event, context):
    root_wavelet = context.GetRootWavelet()
    root_wavelet.CreateBlip().GetDocument().SetText("Don't mind me if I... butt into your conversation.")

if __name__ == '__main__':
  buttbot = robot.Robot('butt-bot', 
      image_url='http://butt-bot.appspot.com/assets/butt.gif',
      version='6',
      profile_url='http://butt-bot.appspot.com/')
  buttbot.RegisterHandler(events.BLIP_SUBMITTED, on_blip_submit)
  buttbot.RegisterHandler(events.BLIP_VERSION_CHANGED, on_version_change)
  buttbot.RegisterHandler(events.WAVELET_SELF_ADDED, on_join)
  buttbot.Run()