#!/usr/bin/env python3
"""
Lädt eine Ausgabe der OTZ (default vom aktuellen Datum) herunter und wandelt die
verschiedenen PDF-Seiten in ein ganzes PDF um
"""

import datetime
import io
import json
import os
import sys
import tempfile
import time
import bs4
import requests
import PyPDF2 as pyPdf
import PyPDF2.generic as pdfGeneric
import PyPDF2.pdf as pdf
import PyPDF2.utils as pdfUtils

class NetworkError(Exception):
    """Fehler beim Download von Genios."""


def prelogin():
    """Eröffnet eine Session vor dem Login."""
    request_session = requests.Session()
    dom = read_dom(request_session, 'https://bib-jena.genios.de/', reason='logging in')
    script = select_one(dom, 'div#outer div#layer_overlay + script + script')
    return (request_session, next(filter(lambda t: len(t) == 720, script.split('"'))))

def login(username, password):
    """Verbindet die Session mit einem Nutzer:innenkonto"""
    pre_session, state = prelogin()
    url = 'https://bib-jena.genios.de/formEngine/doAction'
    pre_session.post(url, params={
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
    return pre_session

def load_toc(session_object):
    """Lädt Inhaltsverzeichnis der Zeitung"""
    date = f'{PUBLISH_DATE.strftime("%Y")}/DT%3D{PUBLISH_DATE.strftime("%Y%m%d")}'
    heft = f'Heft%2B{PUBLISH_DATE.strftime("%d.%m.%Y")}'
    dom = read_dom(
        session_object,
        f'https://bib-jena.genios.de/toc_list/OTZ/{date}/{heft}/OTZ?max=500',
        reason='loading TOC')
    return dom.select('tr[class^="item_OTZ__"]')

def read_dom(session_object, url, reason='website'):
    """Lädt DOM einer HTML-Seite"""
    retry = 0
    while retry < 3:
        try:
            html = session_object.get(url).text
            return bs4.BeautifulSoup(html, features='lxml')
        except requests.exceptions.ConnectionError:
            retry += 1
            continue
    print(f'3x NETWORK ERROR while {reason} ({url})')
    raise NetworkError

def get_page_id_nr(article_row):
    """Gibt Seitenzahl eines Zeitungsartikels zurück"""
    page_id = article_row['class'][0][5:]
    page_number = int(article_row.contents[6].text[3:])
    return page_id, page_number

def select_one(dom, selector, text=True, lenient=False):
    """Gibt Zielwert des Selektors als Text zurück"""
    result = dom.select(selector)
    if len(result) == 0:
        if not lenient:
            raise LookupError(selector)
        return ''
    if text:
        return result[0].text.strip()
    return result[0]

def article_metadata(session_object, page_id):
    """Gibt Link zum PDF und Ausgabeort eines Zeitungsartikel zurück"""
    retry = 0
    while retry <1:
        try:
            dom = read_dom(
                session_object,
                f'https://bib-jena.genios.de/document/{page_id}',
                reason='loading Metadata')
            ausgabe_ort = select_one(dom, 'tr:nth-child(3) td.boxFirst + td').lower()
            link = select_one(dom, 'span.boxItem a', text=False)['id']
            return {
            'ausgabe': ausgabe_ort,
            'pdf': link}
        except LookupError as error:
            if str(dom).find('Ihre Kennung hat nicht die Berechtigung diese Datenbank abzurufen.') == -1:
                debug_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
                debug_file.write(str(error))
                debug_file.write(20 * '_*_ ')
                debug_file.write(str(dom))
                debug_file.close()
                print(f'Error {str(error)} in {debug_file.name} while getting "https://bib-jena.genios.de/document/{page_id}"')
                if retry == 0:
                    retry += 1
                    continue
                raise LookupError
            print('Ihre Kennung hat nicht die Berechtigung diese Datenbank abzurufen.')
            retry += 1
            print(f'Versuche "https://bib-jena.genios.de/document/{page_id}" zum {retry+1}ten Mal')
            time.sleep(retry ** 2)
    raise NetworkError

def get_pdf_page(session_object, page_id, link):
    """Gibt PDF-Seitenobjekt einer Seite zurück"""
    url1 = 'https://bib-jena.genios.de/stream/downloadConsole'
    url2 = 'https://bib-jena.genios.de' + next(filter(
        lambda t: len(t) > 100,
        session_object.post(url1, params={
            'srcId': link,
            'id': page_id,
            'type': -7,
            'sourceId': link}).text.split('"')))
    content = io.BytesIO(session_object.get(url2, stream=True).content)
    source = pyPdf.PdfFileReader(content)
    if source.getNumPages() > 1:
        raise ValueError('Mehr als eine Seite in Zeitungsseitendatei')
    return remove_watermark(source)

def remove_watermark(source):
    """Entfernt Wasserzeichen einer Zeitungsseite"""
    page = source.getPage(0)
    content_object = page['/Contents'].getObject()
    content = pdf.ContentStream(content_object, source)

    for operands, operator in content.operations:
        if operator == pdfUtils.b_('Tj'):
            if not (
                    operands[0].startswith('Alle Rechte vorbehalten. © Ostthüringer Zeitung.  Download vom') or #pylint: disable=line-too-long
                    operands[0].startswith('Dieses Dokument ist lizenziert für ')):
                print(f'Entferne "{operands[0]}"')
            operands[0] = pdfGeneric.TextStringObject('')

    page.__setitem__(pdfGeneric.NameObject('/Contents'), content)
    return page

def get_all_pages(session_object):
    """Gibt sortierte Liste an Seiten mit Zeitungsartikeln von Ausgaben zurück"""
    all_pages = {}
    for page_id, number in map(get_page_id_nr, load_toc(session_object)):
        ausgabe_id = page_id.split('_')[3]
        if number not in all_pages:
            all_pages[number] = {}
        if ausgabe_id not in all_pages[number]:
            all_pages[number][ausgabe_id] = page_id
    return all_pages

def get_full_ausgabe(session_object, selected_ausgabe):
    """Stellt eine Zeitungsausgabe eines Ausgabeortes zusammen"""
    selected_ausgabe_normalized = selected_ausgabe.lower()
    pdf_pages = {}
    all_pages = get_all_pages(session_object)
    for number, page in all_pages.items():
        selected_page, text = get_seite(session_object, page, selected_ausgabe_normalized)
        print(f'Seite {number}: {text}')
        pdf_pages[number] = selected_page
    return pdf_pages

def get_seite(session_object, ausgaben_page, ausgabe):
    """Wählt aus allen Ausgabenseiten die passende Seite aus"""
    if len(ausgaben_page) == 1:
        page_id = ausgaben_page.popitem()[1]
        meta = article_metadata(session_object, page_id)
        if meta['ausgabe'] == ausgabe:
            text = f'Ausgabe {ausgabe} vorhanden'
        else:
            text = f'nur Ausgabe {meta["ausgabe"]} vorhanden'
        return get_pdf_page(session_object, page_id, meta['pdf']), text

    ausgaben = {}
    for page_id in ausgaben_page.values():
        meta = article_metadata(session, page_id)
        ausgaben[meta['ausgabe']] = {'page_id': page_id, 'pdf': meta['pdf']}
        if meta['ausgabe'] == ausgabe:
            return get_pdf_page(session, page_id, meta['pdf']), f'Ausgabe {ausgabe} vorhanden'

    text = f'Ausgaben {DEFAULT_AUSGABE} vorhanden (aus {len(ausgaben)} gewählt)'
    selected = DEFAULT_AUSGABE.lower()
    if selected in ausgaben:
        ausgabe = ausgaben[selected]
    else:
        selected, ausgabe = ausgaben.popitem()
    return get_pdf_page(session, ausgabe['page_id'], ausgabe['pdf']), text

def bind_seiten(all_pages, ausgabe):
    """Bindet alle PDF-Seitenobjekte zu einem Gesamtdokument zusammen"""
    output = pyPdf.PdfFileWriter()
    print('Hinzufügen der Seiten ', end='')
    for page_nr in sorted(iter(all_pages.keys())):
        print(f'{page_nr} ', end='')
        output.addPage(all_pages[page_nr])
    print('(fertig)')
    output_name = f'OTZ_{PUBLISH_DATE.strftime("%Y-%m-%d_%a")}_{ausgabe}.pdf'
    with open(output_name, 'wb') as pdf_file:
        output.write(pdf_file)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        PUBLISH_DATE = datetime.datetime.strptime(sys.argv[1], '%d.%m.%Y')
    else:
        PUBLISH_DATE = datetime.datetime.now()

    DEFAULT_AUSGABE = 'Schleiz'
    AUSGABE = 'Jena'

    path = os.path.dirname(os.path.realpath(__file__))
    with open(f'{path}/login.json', 'r') as login_data:
        session = login(**json.load(login_data))

    retry = 0
    while retry < 2:
        try:
            pages = get_full_ausgabe(session, AUSGABE)
            break
        except NetworkError:
            print('nächster Versuch')
    if retry >= 2:
        print("Fehler beim Herunterladen")
    else:
        bind_seiten(pages, AUSGABE)

