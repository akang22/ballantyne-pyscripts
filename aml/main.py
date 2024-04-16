import requests
import xmltodict
import datetime
import re

def get_corrupt_foreign_officials():
    def split_name(name):
        return re.split(" \\(", name)[0]

        if re.search("\\(born on ", name) is not None:
            arr = re.split("\\(born on ", name)
            return (arr[0], arr[1][:-1])

        if re.search("\\(born in ", name) is not None:
            arr = re.split("\\(born in ", name)
            return (arr[0], arr[1][:-1])

        return (name, None)

    link = "https://laws-lois.justice.gc.ca/eng/XML/SOR-2017-233.xml"

    try:
        response = requests.get(link).content
    except:
        print('hi')
        # TODO network failure handling, including retries

    xml = xmltodict.parse(response)

    names = [split_name(item['Text']) for item in xml['Regulation']['Schedule'][0]['List']['Item']]

    # TODO: move to dataframes/sql

    return names 


def get_corrupt_foreign_officials_tunisia():
    def split_name(line):
        return [re.split("(( \\()|(\\))|(,))", name)[0] for name in re.split(" \\(also known among other names as ", line)]

    link = "https://laws-lois.justice.gc.ca/eng/XML/SOR-2011-78.xml"

    try:
        response = requests.get(link).content
    except:
        print('hi')
        # TODO network failure handling, including retries

    xml = xmltodict.parse(response)

    names = [name for item in xml['Regulation']['Schedule'][0]['List'][0]['Item'] if 'Repealed' not in item['Text'] for name in split_name(item['Text'])]

    return names
