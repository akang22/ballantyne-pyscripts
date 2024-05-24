import requests
import xmltodict
import datetime
import re


def arrayify(val):
    if isinstance(val, list):
        return val
    else:
        return [val]


def from_xml(link):
    def decorator(func):
        def new_func():
            try:
                response = requests.get(link).content
            except:
                print('network failed')
                # TODO network failure handling, including retries

            xml = xmltodict.parse(response)
            return func(xml)

        return new_func

    return decorator


# general TODO: clean up xml language parsing
# and stop abusing list comprehensions until then
# address
# 2 different lists for entities and people
# don't have seperate lists for different 
# leave duplicates

@from_xml("https://laws-lois.justice.gc.ca/eng/XML/SOR-2017-233.xml")
def get_corrupt_foreign_officials(xml):
    # some birth date available
    def split_name(name):
        return re.split(" \\(", name)[0]

    names = [
        split_name(item["Text"])
        for item in xml["Regulation"]["Schedule"][0]["List"]["Item"]
    ]

    return names


@from_xml("https://laws-lois.justice.gc.ca/eng/XML/SOR-2011-78.xml")
def get_tunisia_exposed(xml):
    # birth date nullable, other names,

    def split_name(line):
        return [
            re.split("(( \\()|(\\))|(,))", name)[0]
            for name in re.split(" \\(also known among other names as ", line)
        ]

    names = [
        name
        for item in xml["Regulation"]["Schedule"][0]["List"][0]["Item"]
        if "Repealed" not in item["Text"]
        for name in split_name(item["Text"])
    ]

    return names


@from_xml("https://laws-lois.justice.gc.ca/eng/XML/SOR-2014-44.xml")
def get_ukraine_exposed(xml):
    # can also add birth date and role
    def split_name(line):
        return [re.split("(( \\()|(\\))|(,))", line)[0]]

    names = [
        name
        for item in xml["Regulation"]["Schedule"][0]["Provision"]
        if "Repealed" not in item["Text"]
        for name in split_name(item["Text"])
    ]

    return names

@from_xml(
    "https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml"
)
def get_consolidated_sanctions_names(xml):
    # can have DOB, regulation, Entity
    # missing 3 values
    def split_name(line):
        return (
            (
                [f"{line['GivenName'] } {line['LastName'].upper()}"]
                if "GivenName" in line and "LastName" in line
                else []
            )
        )
    names = [name for item in xml["data-set"]["record"] for name in split_name(item)]

    return names

@from_xml(
    "https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml"
)
def get_consolidated_sanctions_entities(xml):
    # can have DOB, regulation, Entity
    # missing 3 values
    def split_name(line):
        return (
            (
                [line["Entity"]]
                if "Entity" in line
                else []
            )
        )
    names = [name for item in xml["data-set"]["record"] for name in split_name(item)]

    return names

@from_xml("https://laws-lois.justice.gc.ca/eng/XML/SOR-2001-360.xml")
def get_terrorism_groups_UN(xml):
    def split_name(line):
        # TODO: only gets one name rn from the 'other names'
        return [
            re.split(" \\(also known among other names as ", line)[0]
        ]

    names = [
        name
        for item in xml["Regulation"]["Schedule"][0]["List"]["Item"]
        for name in (
            split_name(item["Text"])
            if isinstance(item["Text"], str)
            else split_name(item["Text"]["Language"]["#text"])
        )
    ]

    return names


@from_xml("https://laws-lois.justice.gc.ca/eng/XML/SOR-2002-284.xml")
def get_list_of_entities_canada(xml):
    def split_name(line):
        # TODO: only gets one name rn, same as above
        return [
            re.split("(( \\()|(\\))|(,))", name)[0]
            for name in re.split(" \\(also known among other names as ", line)
        ]

    names = [
        name
        for item in xml["Regulation"]["Body"]["Section"][0]["List"]["Item"]
        for name in (
            split_name(item["Text"])
            if isinstance(item["Text"], str)
            else ([split_name(item["#text"])] if "#text" in item else [])
            + [
                name
                for lang in arrayify(item["Text"]["Language"])
                for name in split_name(lang["#text"])
            ]
        )
    ]

    return names
