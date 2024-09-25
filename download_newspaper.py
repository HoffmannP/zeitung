#!/usr/bin/env python3
"""
Lädt eine Ausgabe einer Zeitung (default vom aktuellen Datum) herunter und wandelt die
verschiedenen PDF-Seiten in ein ganzes PDF um
"""

import datetime
import sys
import tempfile
import subprocess

import bs4
import requests


BACKURI = 'www.wiso-net.de'
ZEITUNG = 'OTZ'
REGIONAL_EDITION = 'Jena'
DEFAULT_EDITION = 'Schleiz und Bad Lobenstein'
GENERIC_RESORT = [
    'Thüringen',
    'Politik',
    'Wirtschaft',
    'Region',
    'Kultur',
    'Sport',
    'Freizeit',
    'Verbraucher',
    'Kinder',
    'Jugend',
    'Panorama']
REGIONAL_RESORT = [
    'Titel',
    'Vermischtes',
    'Lokalnachrichten',
    'Lokalsport']
ARTICLE_NUMBER_FRONTIER = 15
MAXTOC = 500
PDFTK = '/usr/bin/pdftk'
DIRECTORY = '/home/ber/Unicloud/Zeitung'

publish_date = None  # pylint: disable=C0103
downloads = 0  # pylint: disable=C0103


class NetworkError(Exception):
    """Fehler beim Download von Genios."""


def load_toc(session_object):
    """Lädt Inhaltsverzeichnis der Zeitung"""
    # date = f'{PUBLISH_DATE.strftime("%Y")}/DT%3D{PUBLISH_DATE.strftime("%Y%m%d")}'
    year = publish_date.strftime("%Y")
    sdate = publish_date.strftime("%Y-%m-%d")
    date = f'{year}/{ZEITUNG}__%3A{year}%3A{sdate}%3A{sdate}'
    # heft = f'Heft%2B{PUBLISH_DATE.strftime("%d.%m.%Y")}'
    heft = publish_date.strftime("%d.%m.%Y")
    dom = read_dom(
        session_object,
        f'https://{BACKURI}/toc_list/{ZEITUNG}/{date}/{heft}/{ZEITUNG}?max={MAXTOC}',
        reason='loading TOC')
    return dom.select(f'tr[class^="item_{ZEITUNG}__"]')


def read_dom(session_object, url, reason='website'):
    """Lädt DOM einer HTML-Seite"""
    global downloads  # pylint: disable=W0603

    retry = 0
    while retry < 3:
        try:
            html = session_object.get(url).text
            downloads += 1
            return bs4.BeautifulSoup(html, features='lxml')
        except requests.exceptions.ConnectionError:
            retry += 1
            continue
    print(f'3x NETWORK ERROR while {reason} ({url})')
    raise NetworkError


def parse_toc_entry(entry):
    """Parses toc entries in dom"""
    box = entry.select('td.boxDocument')[0]
    descs = box.select('span.boxDescription')
    absts = box.select('span.boxAbstract')
    return {
        'id': entry.select('td.boxFirst > input')[0]['value'],
        'group': entry.select('td.boxSave > a')[0]['id'],
        'title': box.select('a')[0].text.strip(),
        'resort': box.select('span.boxSubHeader')[1].text.strip('/ '),
        'desc': descs[0].contents if len(descs) > 0 else None,
        'abst': absts[0].contents if len(absts) > 0 else None,
        'page': int(entry.select('td.boxPage')[0].text[3:])}


def parse_toc(toc):
    """Parse toc for each entry"""
    return [parse_toc_entry(entry) for entry in toc]


def group_by_page(toclist):
    """Group toc entries by page number"""
    pages = {}
    for entry in toclist:
        page = entry['page']
        if page not in pages:
            pages[page] = [entry]
        else:
            pages[page].append(entry)
    return pages


def best_fit(session_object, articles):
    """Selects best edition"""
    num_articles = len(articles)
    article = articles[0]
    resort = article['resort']

    if resort in GENERIC_RESORT:
        regional_page = False
        if num_articles > ARTICLE_NUMBER_FRONTIER:
            print(f'Article number {num_articles} > {ARTICLE_NUMBER_FRONTIER} ' +
                  f'even though GENERIC_RESORT {resort}')
    elif resort in REGIONAL_RESORT:
        regional_page = True
        if num_articles <= ARTICLE_NUMBER_FRONTIER:
            print(f'Article number {num_articles} <= {ARTICLE_NUMBER_FRONTIER} ' +
                  f'even though REGIONAL_RESORT {resort}')
    else:
        if len(articles) > ARTICLE_NUMBER_FRONTIER:
            regional_page = True
        else:
            regional_page = False
        suggested_resort = 'REGIONAL_RESORT' if regional_page else 'GENERIC_RESORT'
        print(f'Resort «{resort}» could be «{suggested_resort}»')

    target_edition = REGIONAL_EDITION if regional_page else DEFAULT_EDITION
    editions = []
    for article in articles:
        dom = read_dom(
            session_object,
            f'https://{BACKURI}/document/{article["id"]}')
        edition_tag = dom.select('.moduleDocumentTable tr:nth-child(3) td:nth-child(2)')[0]
        editions = [edition.strip() for edition in edition_tag.text.split(';')]
        if target_edition in editions:
            return {**article, 'edition': target_edition}
        editions.append({**article, 'edition': '; '.join(editions)})

    print(editions)
    print(f'Did not find target edition {target_edition} ' +
          f'even though it as {"REGIONAL_RESORT" if regional_page else "GENERIC_RESORT"} {resort}')


def pdf_page(session_object, page_id):
    """Gibt PDF-Seitenobjekt einer Seite zurück"""
    link = f'https://{BACKURI}/document/{page_id}'
    url1 = f'https://{BACKURI}/stream/downloadConsole'
    url2 = f'https://{BACKURI}' + next(filter(
        lambda t: len(t) > 100,
        session_object.post(url1, params={
            'srcId': link,
            'id': page_id,
            'type': -7,
            'sourceId': link}).text.split('"')))
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(session_object.get(url2, stream=True).content)
        return f.name


def main():
    """Get newspaper for one specific date"""
    session = requests.Session()

    pages = group_by_page(parse_toc(load_toc(session)))
    pdf_pages = {}
    for page, articles in pages.items():
        page_edition = best_fit(session, articles)
        pdf_pages[page] = pdf_page(session, page_edition['id'])
        print(f'{page:2d}', page_edition['edition'])
    output = f'{DIRECTORY}/{ZEITUNG}_{publish_date.strftime("%Y-%m-%d")}.pdf'
    command = [PDFTK] + list(pdf_pages.values()) + ['cat', 'output', output]
    subprocess.call(command)
    print(f'Insgesamt {downloads} Downloads für {output}')
    subprocess.call(['rm'] + list(pdf_pages.values()))


if __name__ == '__main__':
    publish_date = datetime.datetime.now() if len(sys.argv) <= 1 else \
        datetime.datetime.strptime(sys.argv[1], '%d.%m.%Y')
    main()
