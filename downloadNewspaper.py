#!/usr/bin/env python3

import bs4
import datetime
import io
import PyPDF2 as pyPdf
import PyPDF2.pdf as pdf
import PyPDF2.generic as pdfGeneric
import PyPDF2.utils as pdfUtils
import requests
import sys

def prelogin():
    session = requests.Session()
    dom = readDom(session, 'https://bib-jena.genios.de/')
    script = selectOne(dom, 'div#outer div#layer_overlay + script + script')
    return (session, next(filter(lambda t: len(t) == 720, script.split('"'))))

def login (username, password):
    session, state = prelogin()
    url = 'https://bib-jena.genios.de/formEngine/doAction'
    session.post(url, params={
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
    return session

def loadTOC(session):
    dom = readDom(session, f'https://bib-jena.genios.de/toc_list/OTZ?target=OTZ&issueName=Heft%2B{TODAY.strftime("%d.%m.%Y")}&max=500')
    return dom.select('tr[class^="item_OTZ__"]')

def readDom(s, u):
    return bs4.BeautifulSoup(s.get(u).text, features='lxml')

def parseInt(inp):
    try:
        return int(inp)
    except ValueError:
        return -1

def getPageIdNr(articleRow):
    page_id = articleRow['class'][0][5:]
    page_number = int(articleRow.contents[6].text[3:])
    return page_id, page_number

def selectOne(d, selector, text=True, lenient=False):
    result = d.select(selector)
    if len(result) == 0:
        if not lenient:
            raise LookupError(selector)
        return ''
    if text:
        return result[0].text.strip()
    return result[0]

def articleMetadata(session, page_id):
    dom = readDom(session, 'https://bib-jena.genios.de/document/{}'.format(page_id))
    try:
        ausgabe = selectOne(dom, 'tr:nth-child(3) td.boxFirst + td').lower()
        link = selectOne(dom, 'span.boxItem a', text=False)['id']
    except LookupError as err:
        raise LookupError(f'Keine Ergebnisse mit dem Selektor "{err}" auf der Seite "https://bib-jena.genios.de/document/{page_id}"')
    return {
        'ausgabe': ausgabe,
        'pdf': link}

def getPdfPage(session, page_id, link):
    url1 = 'https://bib-jena.genios.de/stream/downloadConsole'
    url2 = 'https://bib-jena.genios.de' + next(filter(
        lambda t: len(t) > 100,
        session.post(url1, params={
            'srcId': link,
            'id': page_id,
            'type': -7,
            'sourceId': link}).text.split('"')))
    content = io.BytesIO(session.get(url2, stream=True).content)
    source = pyPdf.PdfFileReader(content)
    if source.getNumPages() > 1:
        raise ValueError('Mehr als eine Seite in Zeitungsseitendatei')
    return removeWatermark(source)

def removeWatermark(source):
    page = source.getPage(0)
    content_object = page['/Contents'].getObject()
    content = pdf.ContentStream(content_object, source)

    for operands, operator in content.operations:
        if operator == pdfUtils.b_('Tj'):
            if not (
                operands[0].startswith('Alle Rechte vorbehalten. © Ostthüringer Zeitung.  Download vom') or
                operands[0].startswith('Dieses Dokument ist lizenziert für ')):
                print(f'Entferne "{operands[0]}"')
            operands[0] = pdfGeneric.TextStringObject('')

    page.__setitem__(pdfGeneric.NameObject('/Contents'), content)
    return page

def getAllPages(session):
    all_pages = {}
    for page_id, number in map(getPageIdNr, loadTOC(session)):
        ausgabe_id = page_id.split('_')[3]
        if number not in all_pages:
            all_pages[number] = {}
        if ausgabe_id not in all_pages[number]:
            all_pages[number][ausgabe_id] = page_id
    return all_pages

def getFullAusgabe(session, ausgabe):
    ausgabe = ausgabe.lower()
    pdf_pages = {}
    pages = getAllPages(session)
    for number in sorted(iter(pages.keys())):
        if number < 21:
            continue
        if len(pages[number]) == 1:
            page_id = pages[number].popitem()[1]
            meta = articleMetadata(session, page_id)
            if meta['ausgabe'] == ausgabe:
                print(f'Seite {number} Ausgabe {ausgabe} gefunden')
            else:
                print(f'Seite {number} eine Ausgabe vorhanden: {meta["ausgabe"]}')
            pdf_pages[number] = getPdfPage(session, page_id, meta['pdf'])
            continue
        ausgaben = {}
        found = False
        for page_id in pages[number].values():
            meta = articleMetadata(session, page_id)
            if meta['ausgabe'] == ausgabe:
                print(f'Seite {number} Ausgabe {ausgabe} gefunden')
                pdf_pages[number] = getPdfPage(session, page_id, meta['pdf'])
                found = True
                break
            ausgaben[meta['ausgabe']] = { 'page_id': page_id, 'link': meta['pdf'] }
        if found:
            continue
        print(f'Seite {number} {len(ausgaben)} Ausgaben vorhanden {meta["ausgabe"]} gewählt', ausgaben.keys())
        ausgabe = ausgaben[DEFAULT_AUSGABE.lower()]
        print(ausgabe)
        pdf_pages[number] = getPdfPage(session, ausgabe['page_id'], ausgabe['pdf'])
    return pdf_pages

def bindPages(pages, ausgabe):
    output = pyPdf.PdfFileWriter()
    print('Hinzufügen der Seiten ', end='')
    for page_nr in pages:
        print(f'{page_nr} ', end='')
        output.addPage(pages[page_nr])
    print('(fertig)')
    output_name = f'OTZ_{TODAY.strftime("%Y-%m-%d")}_{ausgabe}.pdf'
    with open(output_name, 'wb') as f:
        output.write(f)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        TODAY = datetime.datetime.strptime(sys.argv[1], '%d.%m.%Y')
    else:
        TODAY = datetime.datetime.now()
    DEFAULT_AUSGABE = 'schleiz'
    ausgabe = 'Jena'
    session = login('L0075062', '14092010')
    pages = getFullAusgabe(session, ausgabe)
    bindPages(pages, ausgabe)