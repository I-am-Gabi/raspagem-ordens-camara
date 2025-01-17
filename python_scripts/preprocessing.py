# -*- coding: utf-8 -*-
import json
import itertools
import PyPDF2
import re
import os
import sys

import nltk
from nltk import word_tokenize
from nltk.tokenize import SpaceTokenizer

import pandas as pd

from db import collection
collection.remove()


partidos = ['PRTB', 'PCB', 'PSTU', 'PP', 'PTdoB', 'PR', 'PSOL', 'PRB', 'PSL', 'PTN', 'PCO', 'PSDC', 'PHS', 'PV',
            'PPS', 'PRP', 'PMN', 'PSC', 'PSDB', 'PSB', 'PCdoB', 'DEM', 'PTC', 'PT', 'PTB', 'PMDB', 'PDT',
            'PATRIOTA', 'AVANTE', 'PMB', 'PSD', 'PROS', 'SD', 'MDB']
punctuations = ['(', ')', ';', ':', '[', ']', '-']
scape = ['\n', '\\', '-', 'Œ']


def replace_all(symbol_scape, content):
    """
    Replace all 'symbol_scape' from given string

    Args: 
    symbol_scape : document words 
    content: string to remove symbols

    Returns:
        string without symbols 
    """
    new_str = content
    for symbol in symbol_scape:
        new_str = new_str.replace(symbol, '')
    return new_str


def find_orator(keywords):
    """
    Return orators

    Args: 
    keywords : document words 

    Returns:
        a list of orators name 
    """
    found_orators = False
    orators = []
    for keyword in keywords:
        # found somethig like 14h/14h15
        if found_orators and re.search(r'\d\dh', keyword):
            found_orators = False
        # append orator name if not
        if found_orators and keyword != '.':
            orators.append(keyword)
        # found a new orator
        if keyword == "ORADOR":
            found_orators = True
    orators = [s.split('.') for s in orators if s not in partidos]
    orators = list(itertools.chain.from_iterable(orators))
    final_orators = []

    count = -1

    # append string to find orators names
    for s in orators:
        if re.search(r'VER[.ª]*[ª.]*', s):
            count += 1
            final_orators.append('')
        elif s not in ['a', 'ª']:
            final_orators[count] += s + ' '

    return [s.rstrip() for s in final_orators]


def find_topics(keywords):
    flag_title = False
    flag_responsible = False
    flag_subject = False
    flag_forwarding = False

    flag_start_content = False
    topic = {'tipo': '', 'n': '', 'responsavel': '',
             'movimento': '', 'assunto': ''}

    list_topics = []
    for keyword in keywords:
        if keyword == 'PAUTA':
            flag_start_content = True

        # estamos lendo o cabeçalho do arquivo
        if not flag_start_content:
            continue

        if keyword == 'ASSUNTO' and flag_title and not flag_forwarding:
            topic['tipo'] = topic['tipo'].rstrip().replace(' .', '')
            responsavel = re.sub(
                r'VER[.a]*[.ª]*[ .]* ', '',
                topic['responsavel'].rstrip()).replace(' .', '')
            # as vezes teremos mais de um partido envolvido
            # topic['partido'] = responsavel.rsplit(' ', 1)[1]
            topic['responsavel'] = responsavel  # .rsplit(' ', 1)[0]

            flag_title = False
            flag_subject = True
            continue

        if keyword == 'MOVIMENTO' and flag_subject and not flag_title:
            flag_subject = False
            flag_forwarding = True
            continue

        if keyword in ['PROJETO', 'REQUERIMENTO', 'MOÇÃO', 'EMENDA'] and not flag_subject:
            if flag_forwarding or flag_start_content:
                if flag_forwarding:
                    topic['assunto'] = topic['assunto'].replace(
                        ' . ', '')
                    topic['movimento'] = re.sub(
                        r'ESTADO DO RIO GRANDE DO NORTE CÂMARA MUNICIPAL DO NATAL PALÁCIO PADRE MIGUELINHO', '',
                        topic['movimento'].rstrip()).replace('.', '').rstrip()
                    list_topics.append(topic)

                    topic = {'tipo': '', 'n': '', 'responsavel': '',
                             'movimento': '', 'assunto': ''}

                flag_title = True
                flag_subject = flag_forwarding = flag_responsible = False
            else:
                # quuando a string 'projeto' se repete em motivmento e titulo
                continue

        if (flag_subject and not flag_title):
            topic['assunto'] += keyword + ' '

        if (flag_forwarding and not flag_subject):
            topic['movimento'] += keyword + ' '

        if flag_title and re.search(r'\d/20\d\d', keyword):
            topic['n'] = keyword
            flag_responsible = True
        elif flag_title and flag_responsible:
            topic['responsavel'] += keyword + ' '
        elif flag_title and not re.search(r'^N[.]*[\u00ba]+', keyword):
            topic['tipo'] += keyword + ' '

    # save the last topic
    topic['assunto'] = topic['assunto'].replace(' . ', '')
    topic['movimento'] = re.sub(
        r'ESTADO DO RIO GRANDE DO NORTE CÂMARA MUNICIPAL DO NATAL PALÁCIO PADRE MIGUELINHO', '',
        topic['movimento'].rstrip()).replace('.', '').rstrip()
    list_topics.append(topic)

    return list_topics


def read_content(file_path):
    pdfFileObj = open(file_path, 'rb')
    pdfReader = PyPDF2.PdfFileReader(pdfFileObj, strict=False)

    pdf_text = ''
    for page in range(pdfReader.numPages):
        page_text = pdfReader.getPage(page).extractText()
        page_text = replace_all(scape, page_text)
        pdf_text += page_text

    tokens = word_tokenize(pdf_text)
    keywords = [
        word for word in tokens if not word in punctuations]

    document = {}
    document['oradores'] = find_orator(keywords[0:150])
    document['pautas'] = find_topics(keywords)

    # TODO
    if not document['oradores']:
        return {}

    return document


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("give us the way to save the output (csv|mongo)")
    else:
        arg = sys.argv[1]
        if arg == 'csv':
            pass
        elif arg == 'mongo':
            path = "../documents"
            files = []

            for dir_path, _, filenames in os.walk(path):
                for filename in [f for f in filenames if f.endswith(".pdf")]:
                    file_path = os.path.join(dir_path, filename)
                    document = read_content(file_path)
                    collection.insert_one(document)
        else:
            print('invalid option')
