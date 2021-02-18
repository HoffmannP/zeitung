#!/usr/bin/env python3

import PyPDF2 as pyPdf
import PyPDF2.pdf as pdf
import PyPDF2.generic as pdfGeneric
import PyPDF2.utils as pdfUtils
import re
import sys
import os

def getPage(filename):
    # don't reformate to with as file will be closed
    source = pyPdf.PdfFileReader(open(filename, 'rb'))
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
                operands[0].startswith('Dieses Dokument ist lizenziert für ThULB Jena, ')):
                print(f'Entferne "{operands[0]}"')
            operands[0] = pdfGeneric.TextStringObject('')

    page.__setitem__(pdfGeneric.NameObject('/Contents'), content)
    return page

def extractPages(path):
    ausgabe = None
    datum = None
    max_version = [ 0, 0, 0 ]
    otz_page = re.compile(r'seite_OTZ_(?P<ausgabe>[A-Z]*)_(?P<datum>\d{8})_V(?P<v1>\d{2})_(?P<seite>\d{3})_V(?P<v2>\d)\.pdf')
    pages = {}
    for entry in os.scandir(path):
        match = otz_page.fullmatch(entry.name)
        if not match:
            continue

        if datum is None:
            datum = match.group('datum')
        else:
            if datum != match.group('datum'):
                continue
        max_version[1] = max(max_version[1], int(match.group('v1')))
        max_version[2] = max(max_version[2], int(match.group('v2')))
        if ausgabe is None:
            ausgabe = match.group('ausgabe')

        pages[int(match.group('seite'))] = getPage(entry.path)
    return {
        'ausgabe': ausgabe,
        'datum': datum,
        'v1': max_version[1],
        'v2': max_version[2],
        'pages': pages}

def bindPages(path, collection):
    output = pyPdf.PdfFileWriter()
    print('Hinzufügen der Seiten ', end='')
    for page_nr in sorted(iter(collection['pages'].keys())):
        print(f'{page_nr} ', end='')
        output.addPage(collection['pages'][page_nr])
    print('(fertig)')
    output_name = f'{path}/OTZ_{collection["ausgabe"]}_{collection["datum"]}_V{collection["v1"]:02}_V{collection["v2"]}.pdf'
    with open(output_name, 'wb') as f:
        output.write(f)


if __name__ == '__main__':
    path = sys.argv[1]
    collection = extractPages(path)
    bindPages(path, collection)