#!/usr/bin/env python3

import requests
import datetime
import bs4
from cloudant.client import Cloudant
import base64

TODAY = datetime.datetime.now().strftime('%d.%m.%Y')
MAX_ERRORS = 5

def database(username, password):
    client = Cloudant(username, password, url='http://172.17.0.2:5984', connect=True)
    if 'otz' not in client:
        client.create_database('otz')
    return client['otz']

def prelogin():
    s = requests.Session()
    d = readDom(s, 'https://bib-jena.genios.de/')
    script = selectOne(d, 'div#outer div#layer_overlay + script + script')
    return (s, next(filter(lambda t: len(t) == 720, script.split('"'))))

def login (username, password):
    s, state = prelogin()
    u = 'https://bib-jena.genios.de/formEngine/doAction'
    s.post(u, params={
        'bibLoginLayer.number': username,
        'bibLoginLayer.password': password,
        'bibLoginLayer.terms_cb': 1,
        'bibLoginLayer.terms': 1,
        'bibLoginLayer.gdpr_cb': 1,
        'bibLoginLayer.gdpr': 1,
        'eventHandler': 'loginClicked',
        'EVT.srcId': 'bibLoginLayer_c0',
        'EVT.scrollTop': 0,
        'state': state})
    return s

def loadTOC(s):
    d = readDom(s, 'https://bib-jena.genios.de/toc_list/OTZ?target=OTZ&issueName=Heft%2B{}&max=400'.format(TODAY))
    return d.select('tr[class^="item_OTZ__"]')

def readDom(s, u):
    return bs4.BeautifulSoup(s.get(u).text, features="lxml")

def parseInt(inp):
    try:
        return int(inp)
    except ValueError:
        return -1

def selectOne(d, selector, text=True, lenient=False):
    result = d.select(selector)
    if len(result) == 0:
        if not lenient:
            raise LookupError(selector)
        return ""
    if text:
        return result[0].text.strip()
    return result[0]

def saveArticle(db, s, pageId):
    d = readDom(s, 'https://bib-jena.genios.de/document/{}'.format(pageId))
    try:
        title = selectOne(d, 'pre.boldLarge', lenient=True)
        images = saveImages(s, d)
        db.create_document({
            '_id': pageId,
            'titel': title,
            'date': TODAY,
            'text': selectOne(d, 'pre.text'),
            'images': images,
            'page': parseInt(selectOne(d, 'tr:nth-child(1) td.boxFirst + td').split('Seite')[1].strip()),
            'resort': selectOne(d, 'tr:nth-child(2) td.boxFirst + td'),
            'ausgabe': selectOne(d, 'tr:nth-child(3) td.boxFirst + td'),
            'pdf': savePDF(s, pageId, selectOne(d, 'span.boxItem a', text=False))})
        print("Saving '{}' with {} images [{}]".format(title, len(images), pageId))
    except LookupError as err:
        raise LookupError("Keine Ergebnisse mit dem Selektor '{}' auf der Seite 'https://bib-jena.genios.de/document/{}' gefunden".format(err, pageId))



def saveImages(s, d):
    images = d.select('div.moduleDocumentGraphic > a')
    return [saveBinary(s, i['href']) for i in images]

def savePDF(s, pageId, link):
    u = 'https://bib-jena.genios.de/stream/downloadConsole'
    return saveBinary(s, 'https://bib-jena.genios.de' + next(filter(
        lambda t: len(t) > 100,
        s.post(u, params={
            'srcId': link['id'],
            'id': pageId,
            'type': -7,
            'sourceId': link['id']}).text.split('"'))))

def saveBinary(s, u):
    return base64.b64encode(s.get(u, stream=True).content).decode()

def getPageId(articleRow):
    return articleRow['class'][0][5:]


if __name__ == '__main__':
    errors = 0
    db = database('admin', 'otz')
    s = login('L0075062', '14092010')
    for page_id in map(getPageId, loadTOC(s)):
        if page_id not in db:
            try:
                saveArticle(db, s, page_id)
            except LookupError as err:
                print(err)
                errors += 1
                if errors > MAX_ERRORS:
                    raise OverflowError("Too many errors")
                s = login('L0075062', '14092010')
                saveArticle(db, s, page_id)