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

property_status = {'a': 'active', 'd': 'discarded', 't': 'tainted'}

def format_name(name):
    if name:
        nfkd_form = unicodedata.normalize('NFKD', name.replace(' ', '-').lower())
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])


def init(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--propiedades', default='avisos.json', help='Precio mínimo de la propiedad')
    parser.add_argument('-a', '--mostrar_todo', action='store_true', help='Mostrar todas las propiedades')
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
    parser.add_argument('-r', '--remove', default=None, type=int, help='Marcar propiedad como descartada')
    parser.add_argument('--initial_link', default=None, help=argparse.SUPPRESS)
    parser.add_argument('--search', default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
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
    property = {}
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
        property = {'id': key,
                    'description': description,
                    'nbhd': nbhd,
                    'price': price,
                    'link': link,
                    'detail': detail}
    return property


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
        for property_info in data.keys():
            if first:
                header = list(data[property_info].keys())
                header.insert(0, 'id')
                csv_writer.writerow(header)
                first = False
            new_row = list(data[property_info].values())
            new_row.insert(0, property_info)
            csv_writer.writerow(new_row)


def taint_properties(properties):
    for property in properties.keys():
        if properties[property]['status'] != property_status['d']:
            properties[property]['status'] = property_status['t']
    return properties


def remove_properties(properties):
    current_properties = properties.copy()
    for property in properties.keys():
        if properties[property]['status'] == property_status['t']:
            print(f'La propiedad {property} no se encuentra mas en la lista')
            print(properties[property])
            # current_properties.pop(property)
    return current_properties


def show_property(properties_displayed, headline, description, url, params):
    print(f'{properties_displayed}- {headline}')
    print(f'\t{description}')
    if params.browser:
        if properties_displayed == 1:
            webbrowser.open_new(url)
        else:
            webbrowser.open_new_tab(url)
    else:
        print(f'\t{url}')


def get_page_properties(announces, properties, params, properties_displayed):
    force_print = params.mostrar_todo
    property_type = params.tipo_de_unidad if params.tipo_de_unidad else 'propiedad'
    operation = params.operacion
    for announce in announces:
        property = get_announcement(announce)
        must_show = force_print
        if property:
            if properties[property['id']]['status'] == property_status['d']:
                continue
            if property['id'] not in properties.keys():
                properties[property['id']] = {'description': property['description'],
                                              'detail': property['detail'],
                                              'nbhd': property['nbhd'],
                                              'price': property['price'],
                                              'link': property['link'],
                                              'status': 'new',
                                              'date': f'{datetime.date.today()}'
                                              }
                must_show = True
            else:
                if properties[property['id']]['status'] != property_status['d']:
                    properties[property['id']]['status'] = property_status['a']
            if must_show:
                headline = f'Aviso {property["id"]} de {property_type} en {operation} en barrio '\
                    f'{property["nbhd"]} a {property["price"]}'
                show_property(properties_displayed, headline, property["description"], property["link"], params)
                properties_displayed += 1
    return properties_displayed


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


def find_properties(params, properties, history):
    properties = taint_properties(properties)

    last_page = 1
    page_number = 1
    properties_displayed = 1
    while page_number <= last_page:
        content = get_content(params.initial_link, page_number)
        announces_location = '/html/body/div[3]/div/div[2]/div/div[2]/div/div[2]/*'
        if page_number == 1:
            last_page = find_last_page_number(content)
            if last_page > 1:
                announces_location = '/html/body/div[3]/div/div[2]/div/div[2]/div[2]/div[2]/*'
        announces = content.xpath(announces_location)
        properties_displayed = get_page_properties(announces, properties, params, properties_displayed)
        page_number += 1
    return remove_properties(properties)




def main(arguments):
    params = init(arguments)
    history = load_history(params.propiedades)
    properties = {}
    if params.search in history.keys():
        properties = history[params.search]
    if params.remove:
        if properties[str(params.remove)]:
            properties[str(params.remove)]['status'] = property_status['d']
    else:
        properties = find_properties(params, properties, history)
    save_data(history, properties, params.propiedades, params.search)
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
