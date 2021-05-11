#!/usr/bin/python3
# Author: Juan Pablo Herrera, Julio Bianco
from lxml import html
import argparse
import csv
import datetime
import json
import requests
import os
import sys
import unicodedata
import webbrowser

estate_status = {'n': 'new', 'a': 'available', 'd': 'discarded', 't': 'tainted', 'r': 'removed'}


def format_name(name):
    if name:
        nfkd_form = unicodedata.normalize('NFKD', name.replace(' ', '-').lower())
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])


def format_status(category):
    if category == 'todas':
        category = [estate_status['n'], estate_status['a'], estate_status['r']]
    elif category == 'nuevas':
        category = [estate_status['n']]
    elif category == 'disponibles':
        category = [estate_status['n'], estate_status['a']]
    elif category == 'removidas':
        category = [estate_status['r'], estate_status['d']]
    elif category == 'descartadas':
        category = [estate_status['d']]
    return category


def init(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--propiedades', default='avisos.json', help='Precio mínimo de la propiedad')
    parser.add_argument('-o', '--operacion', default='alquileres', choices=['alquileres', 'ventas'],
                        help='Especifica el tipo de operación')
    parser.add_argument('-d', '--precio_desde', type=int, default=35000, help='Precio mínimo de la propiedad')
    parser.add_argument('-u', '--precio_hasta', type=int, default=70000, help='Precio máximo de la propiedad')
    parser.add_argument('-m', '--moneda', default='pesos', choices=['pesos', 'dolares'],
                        help='Moneda en que se ofrece la propiedad')
    parser.add_argument('-cd', '--canditad_de_dormitorios', type=int, default=3,
                        help='Cantidad de dormitorios de la propiedad')
    parser.add_argument('-p', '--provincia', default='cordoba', type=format_name,
                        help='Provincia en la que se encuentra la propiedad')
    parser.add_argument('-B', '--barrio', default=None, type=format_name,
                        help='Barrio en la que se encuentra la propiedad')
    parser.add_argument('-c', '--ciudad', default=None, type=format_name,
                        help='Ciudad en la que se encuentra la propiedad')
    parser.add_argument('-b', '--tipo_de_barrio', default=None,
                        choices=['abierto', 'country', 'cerrado', 'con-seguridad'],
                        help='Tipo de barrio')
    parser.add_argument('-t', '--tipo_de_unidad', default=None,
                        choices=['casa', 'duplex', 'triplex', 'chalet', 'casa-quinta', 'Cabana', 'prefabricada'],
                        help='Tipo de unidad')
    parser.add_argument('-w', '--browser', action='store_true', help='Abrir las propiedades en un browser')
    parser.add_argument('--initial_link', default=None, help=argparse.SUPPRESS)
    parser.add_argument('--search', default=None, help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(help='Acciones', dest='command')
    show_parser = subparsers.add_parser("listar")
    show_parser.add_argument('categoria', choices=['todas', 'nuevas', 'disponibles', 'removidas', 'descartadas'],
                             default='nuevas', help='Busca y lista propiedades basandose en la caracteristica')
    remove_parser = subparsers.add_parser("quitar")
    remove_parser.add_argument('id', type=int,
                               help='Busca el identificador y marca la propiedad como borrada')

    args = parser.parse_args(arguments)

    if args.command is None:
        args.categoria = format_status('disponibles')
        args.command = 'listar'
    elif args.command == 'listar':
        if args.categoria is not None:
            args.categoria = format_status(args.categoria)

    initial_link = f'https://clasificados.lavoz.com.ar/inmuebles/casas/alquileres?list=true' \
                   f'&provincia={args.provincia}&precio-desde={args.precio_desde}&precio-hasta={args.precio_hasta}' \
                   f'&moneda={args.moneda}&operacion={args.operacion}' \
                   f'&cantidad-de-dormitorios%5B1%5D={args.canditad_de_dormitorios}-dormitorios'
    search = f'{args.provincia}_{args.precio_desde}_{args.precio_hasta}_{args.moneda}_{args.operacion}_' \
             f'{args.canditad_de_dormitorios}'

    if args.ciudad:
        initial_link += f'&ciudad={args.ciudad}'
        search += f'_{args.ciudad}'
    if args.tipo_de_barrio:
        initial_link += f'&tipo-de-barrio={args.tipo_de_barrio}'
        search += f'_{args.tipo_de_barrio}'
    if args.barrio:
        initial_link += f'&barrio[1]={args.barrio}'
        search += f'_{args.barrio}'
    if args.tipo_de_unidad:
        initial_link += f'&tipo-de-unidad={args.tipo_de_unidad}'
        search += f'_{args.tipo_de_unidad}'
    args.search = search
    args.initial_link = initial_link
    return args


def get_announcement(announcement):
    estate = {}
    link = announcement.xpath('div[2]/div/a/@href')
    key = None
    if link:
        link = link[0].strip()
        key = link.split('/')[5]
    if key:
        description = announcement.xpath('div[2]/div/a/div/text()')
        description = description[0].strip() if description else "***falta la descripcion***"
        nbhd = announcement.xpath('div[2]/div/div[3]/span[2]/text()')
        nbhd = nbhd[0].strip() if nbhd else "no especificado"
        price = announcement.xpath('div[2]/div/div[1]/div[1]/p/text()')
        price = price[0].strip() if price else "consultar"
        detail = announcement.xpath('div[2]/div/div[4]/text()')
        detail = detail[0].strip() if detail else "Sin informacion adicional"
        estate = {'id': key,
                  'description': description,
                  'nbhd': nbhd,
                  'price': price,
                  'link': link,
                  'detail': detail}
    return estate


def load_history(database):
    if os.path.exists(database):
        with open(database, 'r', encoding='utf8') as json_file:
            data = json.load(json_file)
    else:
        data = {}
    return data


def save_data(history, data, store, search):
    history[search] = data
    with open(store, 'w', encoding='utf8') as json_file:
        json.dump(history, json_file, ensure_ascii=False)
    with open(f'{search}.csv', 'w', encoding='utf8') as data_file:
        csv_writer = csv.writer(data_file)
        csv_writer.writerow([search])
        first = True
        for estate_info in data.keys():
            if first:
                header = list(data[estate_info].keys())
                header.insert(0, 'id')
                csv_writer.writerow(header)
                first = False
            new_row = list(data[estate_info].values())
            new_row.insert(0, estate_info)
            csv_writer.writerow(new_row)


def taint_properties(properties):
    for estate in properties.keys():
        if properties[estate]['status'] != estate_status['d'] and \
                properties[estate]['status'] != estate_status['r']:
            properties[estate]['status'] = estate_status['t']
    return properties


def remove_tainted(properties):
    current_properties = properties.copy()
    for estate in properties.keys():
        if properties[estate]['status'] == estate_status['t']:
            print(f'La propiedad {estate} no se encuentra mas en la lista')
            print(properties[estate])
            current_properties[estate]['status'] = estate_status['r']
    return current_properties


def show_estate(items_shown, headline, description, url, browser):
    print(f'{items_shown}- {headline}')
    print(f'\t{description}')
    if browser:
        if items_shown == 1:
            webbrowser.open_new(url)
        else:
            webbrowser.open_new_tab(url)
    else:
        print(f'\t{url}')


def get_page_estates(announces, properties):
    for announce in announces:
        estate = get_announcement(announce)
        if estate:
            if estate['id'] not in properties.keys():
                properties[estate['id']] = {'description': estate['description'],
                                            'detail': estate['detail'],
                                            'nbhd': estate['nbhd'],
                                            'price': estate['price'],
                                            'link': estate['link'],
                                            'status': estate_status['n'],
                                            'date': f'{datetime.date.today()}'
                                            }
            elif properties[estate['id']]['status'] == estate_status['d']:
                continue
            else:
                properties[estate['id']]['status'] = estate_status['a']
    return properties


def display_estates(properties, shown, estate_type, operation, browser):
    items_shown = 1

    for estate in properties.keys():
        if properties[estate]['status'] in shown:
            estate_type = estate_type if estate_type else 'propiedad'
            headline = f'Aviso {estate} de {estate_type} en {operation} en barrio ' \
                       f'{properties[estate]["nbhd"]} a {properties[estate]["price"]}'
            show_estate(items_shown, headline, properties[estate]["description"], properties[estate]["link"], browser)
            items_shown += 1
    return items_shown


def get_content(base_link, page_number):
    page_link = base_link + ("&page=" + str(page_number) if page_number > 1 else "")
    page = requests.get(page_link)
    content = html.fromstring(page.content)
    return content


def find_last_page_number(content):
    last_page = 1
    pagination_links = content.xpath('/html/body/div[3]/div/div[2]/div/div[2]/div[2]/div[4]/nav/div/ul/*/a/@href')
    if pagination_links:
        last_page = int(pagination_links[-1].split("=")[-1])
    return last_page


def find_properties(params, properties):
    properties = taint_properties(properties)
    last_page = 1
    page_number = 1
    while page_number <= last_page:
        content = get_content(params.initial_link, page_number)
        announces_location = '/html/body/div[3]/div/div[2]/div/div[2]/div/div[2]/*'
        if page_number == 1:
            last_page = find_last_page_number(content)
            if last_page > 1:
                announces_location = '/html/body/div[3]/div/div[2]/div/div[2]/div[2]/div[2]/*'
        announces = content.xpath(announces_location)
        get_page_estates(announces, properties)
        page_number += 1
    return properties


def main(arguments):
    params = init(arguments)
    history = load_history(params.propiedades)
    properties = {}
    if params.search in history.keys():
        properties = history[params.search]
    if params.command == 'listar':
        if estate_status['n'] in params.categoria:
            properties = find_properties(params, properties)
        display_estates(properties, params.categoria, params.tipo_de_unidad, params.operacion, params.browser)
    elif params.command == 'remover':
        if properties[str(params.id)]:
            properties[str(params.id)]['status'] = estate_status['d']
    save_data(history, remove_tainted(properties), params.propiedades, params.search)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
