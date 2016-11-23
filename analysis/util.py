import re


def clean_properties(item, name):
    properties = {}
    if name in item:
        for prop in item[name]:
            # flatten values array
            properties[prop['name']] = [value for sublist in prop['values'] for value in sublist]
            values = properties[prop['name']]

            if len(values) == 1:
                v = values[0]
                v = v.rstrip('%')
                v = v.lstrip('+')
                v = v.rstrip(' sec')
                v = v.rstrip(' (Max)')

                if '-' in v:
                    halves = v.split("-")
                    v = (float(halves[0]) + float(halves[1]))/2
                elif '/' in v:
                    halves = v.split("/")
                    v = float(halves[0])
                else:
                    if '.' in v:
                        v = float(v)
                    else:
                        v = int(v)

                properties[prop['name']] = v
    return properties


def prop_or_default(item, name, default):
    if name in item['properties']:
        item[name] = item['properties'][name]
    else:
        item[name] = default


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
    "vaal": 1.4,
    "regret": 1.9,
    "exa": 65.0,
    "chance": 1.0/4.8,
    "divine": 15.4,
    "alt": 1.0/15.0,
    "alch": 1.0/3.6,
    "chisel": 1.0/2.6,
    "fuse": 1.0/2.2,
}

