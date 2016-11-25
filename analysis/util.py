from elasticsearch import Elasticsearch
import re

ES_ADDRESS = "192.168.1.5:9200"

# Initialize the columns to use
# Continuous means the variable is a number instead of something discrete, like a mod name
CONTINUOUS_COLUMNS = [
    'ilvl',
    'corrupted',
    'frameType'
]

# Categorical columns are for things like itemType, which will have category values
# such as 'Dagger' or 'One Handed Sword'
CATEGORICAL_COLUMNS = [
    'itemType'
]

# The label column is what the model is being trained to predict
LABEL_COLUMN = 'price_chaos'

TRAIN_FILE = 'train.csv'


def es_bulk_query(body):
    es = Elasticsearch(hosts=[ES_ADDRESS])

    response = es.search(index='items', doc_type='item', scroll='2m', size=10000, body=body)
    sid = response['_scroll_id']
    scroll_size = response['hits']['total']

    items = []

    while scroll_size > 0:
        scroll_size = len(response['hits']['hits'])
        items.extend(response['hits']['hits'])
        print('scroll size: ' + str(scroll_size))
        response = es.scroll(scroll_id=sid, scroll='2m')
        sid = response['_scroll_id']

    return items


def es_query(body, size=10):
    es = Elasticsearch(hosts=[ES_ADDRESS])

    response = es.search(index='items', doc_type='item', size=size, body=body)

    return response['hits']['hits']


def clean_properties(item, name):
    properties = {}
    if name in item:
        for prop in item[name]:
            # flatten values array
            values = [value for sublist in prop['values'] for value in sublist]

            if len(values) >= 1:
                val = 0.0

                # Add up all the values to get the total for things like 'Elemental Damage' that have multiple entries
                for v in values:
                    v = v.replace('%', '')
                    v = v.replace('+', '')
                    v = v.replace(' sec', '')
                    v = v.replace(' (Max)', '')

                    if '-' in v:
                        halves = v.split("-")
                        val += (float(halves[0]) + float(halves[1]))/2
                    elif '/' in v:
                        # take the first value for things like experience: 23/23923; we only care about current exp
                        halves = v.split("/")
                        val += float(halves[0])
                    else:
                        if '.' in v:
                            val += float(v)
                        else:
                            val += int(v)

                properties[prop['name']] = val
            elif len(values) == 0:
                item['itemType'] = prop['name']

    return properties


def prop_or_default(item, name, default):
    if name in item['properties']:
        item[name] = item['properties'][name]
    else:
        item[name] = default


def req_or_default(item, name, default):
    if name in item['requirements']:
        item[name] = item['requirements'][name]
    else:
        item[name] = default


def format_mod(text):
    numbers = re.findall('(\d+\.?\d*)', text)
    #if len(numbers) > 2:
    #    print("3 numbers in mod!!! " + text)
    # Give a non-zero value for mods without numbers in them to indicate that the mod is present
    if len(numbers) == 0:
        return text, 1.0
    new_text = text.replace(numbers[0], "X", 1)
    if len(numbers) == 1:
        return new_text, float(numbers[0])
    new_text = new_text.replace(numbers[1], "Y", 1)
    return new_text, (float(numbers[0]) + float(numbers[1]))/2


# Formats items to make them easier to process
def format_item(item):
    # Ignore this item if it only moved tabs and wasn't sold, or if the buyout's too low
    if item['removed'] - item['last_updated'] <= 10:
        return None

    if 'corrupted' not in item:
        item['corrupted'] = False

    item['properties'] = clean_properties(item, 'properties')
    item['additionalProperties'] = clean_properties(item, 'additionalProperties')
    item['requirements'] = clean_properties(item, 'requirements')

    m = re.search('\S+ (\d+\.?\d*) (\w+)', item['price'])
    if m is None:
        return None
    item['price_chaos'] = float(m.group(1)) * currency_values[m.group(2)]

    return item

# A mapping of currency types to their value in chaos orbs
# source: http://poe.ninja/esc/currency
# TODO: scrape and index these currency values every day for more accurate prices
currency_values = {
    "chaos": 1.0,
    "chaoss": 1.0,
    "Chaos": 1.0,
    "vaal": 1.4,
    "regret": 1.9,
    "exa": 65.0,
    "exalted": 65.0,
    "chance": 1.0/4.8,
    "divine": 15.4,
    "alt": 1.0/15.0,
    "alts": 1.0/15.0,
    "alch": 1.0/3.6,
    "chisel": 1.0/2.6,
    "fuse": 1.0/2.2,
    "fusing": 1.0/2.2,
    "fus": 1.0/2.2,
    "jew": 1.0/9.5,
    "jewellers": 1.0/9.5,
    "scour": 1.2,
    "regal": 1.1,
    "chrom": 1.0/9.2,
    "gcp": 1.3,
    "blessed": 1.0/2.6,
    "bless": 1.0/2.6,

    "5": 0.0,
    "mirror": 80*65.0,
}

