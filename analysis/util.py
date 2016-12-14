from elasticsearch import Elasticsearch
import operator
import re
import time

ES_ADDRESS = "127.0.0.1:9200"

# Initialize the columns to use
# Continuous means the variable is a number instead of something discrete, like a mod name
CONTINUOUS_COLUMNS = [
    'ilvl',
    'corrupted',
    'frameType',
    'itemType',
    'itemSubType',
    'day'
]

# The label column is what the model is being trained to predict
LABEL_COLUMN = 'price_chaos'

ALL_COLUMNS = []
ALL_COLUMNS.extend(CONTINUOUS_COLUMNS)
ALL_COLUMNS.append(LABEL_COLUMN)

TRAIN_FILE = 'train.csv'

#HIDDEN_UNITS = [800, 600, 500, 400, 300, 200, 150]
#HIDDEN_UNITS = [400, 300, 200, 100, 50]
HIDDEN_UNITS = [150, 150, 150, 150, 150]

# buckets for prices to be separated into
VALUE_EXALTED = 70.0
bins = [0, 2.5, 5, 10, 15, 20, 25, 30, 40, 55,
    1.0 * VALUE_EXALTED,
    1.5 * VALUE_EXALTED,
    2.0 * VALUE_EXALTED,
    2.5 * VALUE_EXALTED,
    3.0 * VALUE_EXALTED
]

start_time = 1480915460

def get_day(seconds):
    return (seconds-start_time)/86400

def get_hidden_units(n):
    hidden_units = []
    for i in range(5):
        hidden_units.append((n*3)/4)
    return hidden_units

def price_bucket(x):
    for i in range(len(bins)):
        if i == len(bins)-1 or x < bins[i+1]:
            return i

def price_to_onehot(x):
    arr = [0] * len(bins)
    arr[price_bucket(x)] = 1.0
    return arr

def get_price_estimate(price_weights):
    price = 0.0
    for i in range(len(price_weights)):
        avg = bins[i]
        if i < len(bins)-1:
            avg += bins[i+1]
            avg = avg/2.0
        if price_weights[i] >= 0.05:
            price += avg * price_weights[i]
    return round(price, 1)

def get_bin_label(x):
    price = bins[x]
    price_denom = 1.0
    currency = 'chaos'
    if price >= currency_values['exa']:
        price_denom = currency_values['exa']
        currency = 'exa'
    if x == len(bins)-1:
        return '>= %d %s' % (price/price_denom, currency)
    return '%0.1f-%0.1f %s' % (price/price_denom, bins[x+1]/price_denom, currency)


def es_bulk_query(body):
    return es_bulk_query_func(body, None)

def es_bulk_query_func(body, func):
    es = Elasticsearch(hosts=[ES_ADDRESS])

    response = es.search(index='items', doc_type='item', scroll='10m', size=10000, body=body)
    sid = response['_scroll_id']
    scroll_size = response['hits']['total']

    items = []

    while scroll_size > 0:
        scroll_size = len(response['hits']['hits'])
        items.extend(response['hits']['hits'])
        if func is not None:
            func(response['hits']['hits'])
        print('scroll size: ' + str(scroll_size))
        response = es.scroll(scroll_id=sid, scroll='2m')
        sid = response['_scroll_id']

    return items

def es_query(body, size=10):
    es = Elasticsearch(hosts=[ES_ADDRESS])

    response = es.search(index='items', doc_type='item', size=size, body=body)

    return response['hits']['hits']


# Convert the properties from an array of objects to a map of name -> value
def clean_properties(item, name):
    properties = {}
    if name in item:
        for prop in item[name]:
            # flatten values array
            values = []
            for sublist in prop['values']:
                if len(sublist) > 0:
                    values.append(sublist[0])

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
                            try:
                                val += int(v)
                            except ValueError:
                                continue

                properties[prop['name']] = val

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


def format_column_name(col):
    return col.replace(" ", "_").replace("%", "").replace("+", "").replace("'", "").replace(",", "").replace("\n", "_")


# Formats items to make them easier to process
def format_item(item):
    if 'corrupted' not in item:
        item['corrupted'] = False

    item['properties'] = clean_properties(item, 'properties')
    item['additionalProperties'] = clean_properties(item, 'additionalProperties')
    item['requirements'] = clean_properties(item, 'requirements')

    if item['typeLine'].startswith('Superior '):
        item['typeLine'] = item['typeLine'][9:]
    item['itemType'] = item_types[item['typeLine']]
    item['itemSubType'] = get_item_subtype(item['typeLine'])

    if 'price' in item and 'price_chaos' not in item:
        item['price_chaos'] = format_price(item['price'])

    if 'removed' in item:
        item['day'] = get_day(item['removed'])
    else:
        item['day'] = get_day(int(time.time()))

    return item


def format_price(price):
    m = re.search('\S+ (\d+\.?\d*) (\w+)', price)
    if m is None:
        return -1.0
    elif m.group(2).lower() not in currency_values:
        print('currency "%s" not found' % m.group(2))
        return -1.0
    else:
        return float(m.group(1)) * currency_values[m.group(2).lower()]

# Returns a table row containing the item's relevant attributes
def item_to_row(i):
    row = {}

    def add_mod(m, v):
        row[m] = v

    for p in i['properties']:
        add_mod('prop_'+p, i['properties'][p])

    for p in i['requirements']:
        # Only take the first 3 chars of req names, because 'Str' and 'Strength' both appear for some reason
        add_mod('req_'+p[:3], i['requirements'][p])

    for p in i['additionalProperties']:
        add_mod('add_prop_'+p, i['additionalProperties'][p])

    if 'sockets' in i:
        row['socket_count'] = len(i['sockets'])
        link_counts = {}
        for socket in i['sockets']:
            if socket['group'] not in link_counts:
                link_counts[socket['group']] = 1
            else:
                link_counts[socket['group']] += 1

            if 'sockets_'+socket['attr'] not in row:
                row['sockets_'+socket['attr']] = 1
            else:
                row['sockets_'+socket['attr']] += 1
        if len(link_counts) == 0:
            row['socket_links'] = 0
        else:
            row['socket_links'] = max(link_counts.iteritems(), key=operator.itemgetter(1))[1]

    if 'implicitMods' in i and len(i['implicitMods']) > 0:
        for mod in i['implicitMods']:
            name, value = format_mod(mod)
            add_mod('implicit_' + name, value)

    if 'explicitMods' in i and len(i['explicitMods']) > 0:
        for mod in i['explicitMods']:
            name, value = format_mod(mod)
            add_mod('explicit_'+name, value)

    if 'craftedMods' in i and len(i['craftedMods']) > 0:
        for mod in i['craftedMods']:
            name, value = format_mod(mod)
            add_mod('crafted_'+name, value)

    # add each column for this item
    for c in ALL_COLUMNS:
        if c in i:
            row[c] = i[c]

    return row

# A mapping of currency types to their value in chaos orbs
# source: http://poe.ninja/esc/currency
# These are only used for old items that don't have a price
VALUE_CHAOS = 1.0
VALUE_VAAL = 1.1
VALUE_REGRET = 1.0
VALUE_CHANCE = 1.0/8.0
VALUE_DIVINE = 9.0
VALUE_ALTERATION = 1.0/21.0
VALUE_ALCHEMY = 1.0/4.6
VALUE_CHISEL = 1.0/6.0
VALUE_FUSING = 1.0/2.9
VALUE_JEWELLER = 1.0/12.0
currency_values = {
    "chaos": VALUE_CHAOS,
    "chaoss": VALUE_CHAOS,
    "chaosgg": VALUE_CHAOS,
    "choas": VALUE_CHAOS,
    "chaos3": VALUE_CHAOS,
    "chas": VALUE_CHAOS,
    "chaos_crab3": VALUE_CHAOS, # yes this is a real one
    "chaos1": VALUE_CHAOS,
    "chaos2": VALUE_CHAOS,
    "c": VALUE_CHAOS,
    "vaal": VALUE_VAAL,
    "regret": VALUE_REGRET,
    "exa": VALUE_EXALTED,
    "exalted": VALUE_EXALTED,
    "ex": VALUE_EXALTED,
    "exalt": VALUE_EXALTED,
    "chance": VALUE_CHANCE,
    "divine": VALUE_DIVINE,
    "alt": VALUE_ALTERATION,
    "alts": VALUE_ALTERATION,
    "altQ": VALUE_ALTERATION,
    "alteration": VALUE_ALTERATION,
    "alch": VALUE_ALCHEMY,
    "alch2": VALUE_ALCHEMY,
    "alch3": VALUE_ALCHEMY,
    "alchemy": VALUE_ALCHEMY,
    "alc": VALUE_ALCHEMY,
    "chisel": VALUE_CHISEL,
    "fuse": VALUE_FUSING,
    "fusing": VALUE_FUSING,
    "fus": VALUE_FUSING,
    "jew": VALUE_JEWELLER,
    "jewellers": VALUE_JEWELLER,
    "scour": 1.0/1.6,
    "regal": 1.5,
    "chrom": 1.0/12.0,
    "gcp": 1.5,
    "pris": 1.0,
    "blessed": 1.0/1.5,
    "bless": 1.0/1.5,

    "5": 0.0,
    "mirror": 80*VALUE_EXALTED,
}

# item base types, source: poe.trade
weapons = set(["One Hand Axe", "One Hand Sword", "Claw", "One Hand Mace", "Two Hand Mace", "Sceptre", "Two Hand Axe",
    "Two Hand Sword", "Bow", "Dagger", "Wand", "Staff"])
all_bases = {
    "Helmet": ["Aventail Helmet", "Barbute Helmet", "Battered Helm", "Bone Circlet", "Bone Helmet", "Callous Mask", "Close Helmet", "Cone Helmet", "Crusader Helmet", "Deicide Mask", "Eternal Burgonet", "Ezomyte Burgonet", "Fencer Helm", "Festival Mask", "Fluted Bascinet", "Gilded Sallet", "Gladiator Helmet", "Golden Mask", "Golden Wreath", "Great Crown", "Great Helmet", "Harlequin Mask", "Hubris Circlet", "Hunter Hood", "Iron Circlet", "Iron Hat", "Iron Mask", "Lacquered Helmet", "Leather Cap", "Leather Hood", "Lion Pelt", "Lunaris Circlet", "Magistrate Crown", "Mind Cage", "Necromancer Circlet", "Nightmare Bascinet", "Noble Tricorne", "Pig-Faced Bascinet", "Plague Mask", "Praetor Crown", "Prophet Crown", "Raven Mask", "Reaver Helmet", "Regicide Mask", "Royal Burgonet", "Rusted Coif", "Sallet", "Samite Helmet", "Scare Mask", "Secutor Helm", "Siege Helmet", "Silken Hood", "Sinner Tricorne", "Solaris Circlet", "Soldier Helmet", "Steel Circlet", "Torture Cage", "Tribal Circlet", "Tricorne", "Ursine Pelt", "Vaal Mask", "Vine Circlet", "Visored Sallet", "Wolf Pelt", "Zealot Helmet"],
    "One Hand Axe": ["Arming Axe", "Boarding Axe", "Broad Axe", "Butcher Axe", "Ceremonial Axe", "Chest Splitter", "Cleaver", "Decorative Axe", "Engraved Hatchet", "Etched Hatchet", "Infernal Axe", "Jade Hatchet", "Jasper Axe", "Karui Axe", "Reaver Axe", "Royal Axe", "Runic Hatchet", "Rusted Hatchet", "Siege Axe", "Spectral Axe", "Tomahawk", "Vaal Hatchet", "War Axe", "Wraith Axe", "Wrist Chopper"],
    #"Flask": ["Amethyst Flask", "Aquamarine Flask", "Basalt Flask", "Bismuth Flask", "Colossal Hybrid Flask", "Colossal Life Flask", "Colossal Mana Flask", "Diamond Flask", "Divine Life Flask", "Divine Mana Flask", "Eternal Life Flask", "Eternal Mana Flask", "Giant Life Flask", "Giant Mana Flask", "Grand Life Flask", "Grand Mana Flask", "Granite Flask", "Greater Life Flask", "Greater Mana Flask", "Hallowed Hybrid Flask", "Hallowed Life Flask", "Hallowed Mana Flask", "Jade Flask", "Large Hybrid Flask", "Large Life Flask", "Large Mana Flask", "Medium Hybrid Flask", "Medium Life Flask", "Medium Mana Flask", "Quartz Flask", "Quicksilver Flask", "Ruby Flask", "Sacred Hybrid Flask", "Sacred Life Flask", "Sacred Mana Flask", "Sanctified Life Flask", "Sanctified Mana Flask", "Sapphire Flask", "Silver Flask", "Small Hybrid Flask", "Small Life Flask", "Small Mana Flask", "Stibnite Flask", "Sulphur Flask", "Topaz Flask"],
    #"Fishing Rods": ["Fishing Rod"],
    "One Hand Sword": ["Ancient Sword", "Antique Rapier", "Apex Rapier", "Baselard", "Basket Rapier", "Battered Foil", "Battle Sword", "Broad Sword", "Burnished Foil", "Copper Sword", "Corsair Sword", "Courtesan Sword", "Cutlass", "Dragonbone Rapier", "Dragoon Sword", "Dusk Blade", "Elder Sword", "Elegant Foil", "Elegant Sword", "Estoc", "Eternal Sword", "Fancy Foil", "Gemstone Sword", "Gladius", "Graceful Sword", "Grappler", "Harpy Rapier", "Hook Sword", "Jagged Foil", "Jewelled Foil", "Legion Sword", "Midnight Blade", "Pecoraro", "Primeval Rapier", "Rusted Spike", "Rusted Sword", "Sabre", "Serrated Foil", "Smallsword", "Spiraled Foil", "Tempered Foil", "Thorn Rapier", "Tiger Hook", "Twilight Blade", "Vaal Blade", "Vaal Rapier", "Variscite Blade", "War Sword", "Whalebone Rapier", "Wyrmbone Rapier"],
    "Claw": ["Awl", "Blinder", "Cat's Paw", "Double Claw", "Eagle Claw", "Eye Gouger", "Fright Claw", "Gemini Claw", "Gouger", "Great White Claw", "Gut Ripper", "Hellion's Paw", "Imperial Claw", "Nailed Fist", "Noble Claw", "Prehistoric Claw", "Sharktooth Claw", "Sparkling Claw", "Terror Claw", "Thresher Claw", "Throat Stabber", "Tiger's Paw", "Timeworn Claw", "Twin Claw", "Vaal Claw"],
    "Body Armour": ["Arena Plate", "Assassin's Garb", "Astral Plate", "Battle Lamellar", "Battle Plate", "Blood Raiment", "Bone Armour", "Bronze Plate", "Buckskin Tunic", "Cabalist Regalia", "Carnal Armour", "Chain Hauberk", "Chainmail Doublet", "Chainmail Tunic", "Chainmail Vest", "Chestplate", "Colosseum Plate", "Commander's Brigandine", "Conjurer's Vestment", "Conquest Chainmail", "Copper Plate", "Coronal Leather", "Crimson Raiment", "Crusader Chainmail", "Crusader Plate", "Crypt Armour", "Cutthroat's Garb", "Desert Brigandine", "Destiny Leather", "Destroyer Regalia", "Devout Chainmail", "Dragonscale Doublet", "Eelskin Tunic", "Elegant Ringmail", "Exquisite Leather", "Field Lamellar", "Frontier Leather", "Full Chainmail", "Full Dragonscale", "Full Leather", "Full Plate", "Full Ringmail", "Full Scale Armour", "Full Wyrmscale", "General's Brigandine", "Gladiator Plate", "Glorious Leather", "Glorious Plate", "Golden Mantle", "Golden Plate", "Holy Chainmail", "Hussar Brigandine", "Infantry Brigandine", "Lacquered Garb", "Latticed Ringmail", "Light Brigandine", "Lordly Plate", "Loricated Ringmail", "Mage's Vestment", "Majestic Plate", "Necromancer Silks", "Occultist's Vestment", "Oiled Coat", "Oiled Vest", "Ornate Ringmail", "Padded Jacket", "Padded Vest", "Plate Vest", "Quilted Jacket", "Ringmail Coat", "Sacrificial Garb", "Sadist Garb", "Sage's Robe", "Saint's Hauberk", "Saintly Chainmail", "Savant's Robe", "Scale Doublet", "Scale Vest", "Scarlet Raiment", "Scholar's Robe", "Sentinel Jacket", "Shabby Jerkin", "Sharkskin Tunic", "Silk Robe", "Silken Garb", "Silken Vest", "Silken Wrap", "Simple Robe", "Sleek Coat", "Soldier's Brigandine", "Spidersilk Robe", "Strapped Leather", "Sun Leather", "Sun Plate", "Thief's Garb", "Triumphant Lamellar", "Vaal Regalia", "Varnished Coat", "War Plate", "Waxed Garb", "Widowsilk Robe", "Wild Leather", "Wyrmscale Doublet", "Zodiac Leather"],
    #"Map": ["Abyss Map", "Academy Map", "Acid Lakes Map", "Arachnid Nest Map", "Arachnid Tomb Map", "Arcade Map", "Arena Map", "Arid Lake Map", "Armory Map", "Arsenal Map", "Ashen Wood Map", "Atoll Map", "Barrows Map", "Bazaar Map", "Beach Map", "Beacon Map", "Bog Map", "Burial Chambers Map", "Canyon Map", "Castle Ruins Map", "Catacombs Map", "Cavern Map", "Cells Map", "Cemetery Map", "Channel Map", "Chateau Map", "Colonnade Map", "Colosseum Map", "Core Map", "Courtyard Map", "Coves Map", "Crematorium Map", "Crypt Map", "Crystal Ore Map", "Dark Forest Map", "Desert Map", "Dunes Map", "Dungeon Map", "Estuary Map", "Excavation Map", "Factory Map", "Forge of the Phoenix Map", "Ghetto Map", "Gorge Map", "Graveyard Map", "Grotto Map", "High Gardens Map", "Ivory Temple Map", "Jungle Valley Map", "Lair Map", "Lair of the Hydra Map", "Malformation Map", "Marshes Map", "Maze Map", "Maze of the Minotaur Map", "Mesa Map", "Mineral Pools Map", "Mud Geyser Map", "Museum Map", "Necropolis Map", "Oasis Map", "Orchard Map", "Overgrown Ruin Map", "Overgrown Shrine Map", "Palace Map", "Peninsula Map", "Phantasmagoria Map", "Pier Map", "Pit Map", "Pit of the Chimera Map", "Plateau Map", "Plaza Map", "Precinct Map", "Primordial Pool Map", "Promenade Map", "Quarry Map", "Quay Map", "Racecourse Map", "Ramparts Map", "Reef Map", "Residence Map", "Scriptorium Map", "Sewer Map", "Shaped Academy Map", "Shaped Acid Lakes Map", "Shaped Arachnid Nest Map", "Shaped Arachnid Tomb Map", "Shaped Arcade Map", "Shaped Arena Map", "Shaped Arid Lake Map", "Shaped Armory Map", "Shaped Arsenal Map", "Shaped Ashen Wood Map", "Shaped Atoll Map", "Shaped Barrows Map", "Shaped Beach Map", "Shaped Bog Map", "Shaped Burial Chambers Map", "Shaped Canyon Map", "Shaped Castle Ruins Map", "Shaped Catacombs Map", "Shaped Cavern Map", "Shaped Cells Map", "Shaped Cemetery Map", "Shaped Channel Map", "Shaped Colonnade Map", "Shaped Courtyard Map", "Shaped Coves Map", "Shaped Crypt Map", "Shaped Crystal Ore Map", "Shaped Desert Map", "Shaped Dunes Map", "Shaped Dungeon Map", "Shaped Factory Map", "Shaped Ghetto Map", "Shaped Graveyard Map", "Shaped Grotto Map", "Shaped Jungle Valley Map", "Shaped Malformation Map", "Shaped Marshes Map", "Shaped Mesa Map", "Shaped Mud Geyser Map", "Shaped Museum Map", "Shaped Oasis Map", "Shaped Orchard Map", "Shaped Overgrown Shrine Map", "Shaped Peninsula Map", "Shaped Phantasmagoria Map", "Shaped Pier Map", "Shaped Pit Map", "Shaped Primordial Pool Map", "Shaped Promenade Map", "Shaped Quarry Map", "Shaped Quay Map", "Shaped Racecourse Map", "Shaped Ramparts Map", "Shaped Reef Map", "Shaped Sewer Map", "Shaped Shore Map", "Shaped Spider Forest Map", "Shaped Spider Lair Map", "Shaped Strand Map", "Shaped Temple Map", "Shaped Terrace Map", "Shaped Thicket Map", "Shaped Tower Map", "Shaped Tropical Island Map", "Shaped Underground River Map", "Shaped Vaal City Map", "Shaped Vaal Pyramid Map", "Shaped Villa Map", "Shaped Waste Pool Map", "Shaped Wharf Map", "Shipyard Map", "Shore Map", "Shrine Map", "Spider Forest Map", "Spider Lair Map", "Springs Map", "Strand Map", "Sulphur Wastes Map", "Temple Map", "Terrace Map", "Thicket Map", "Torture Chamber Map", "Tower Map", "Tropical Island Map", "Underground River Map", "Underground Sea Map", "Vaal City Map", "Vaal Pyramid Map", "Vaal Temple Map", "Vault Map", "Villa Map", "Volcano Map", "Waste Pool Map", "Wasteland Map", "Waterways Map", "Wharf Map"],
    "One Hand Mace": ["Ancestral Club", "Auric Mace", "Barbed Club", "Battle Hammer", "Behemoth Mace", "Bladed Mace", "Ceremonial Mace", "Dragon Mace", "Dream Mace", "Driftwood Club", "Flanged Mace", "Gavel", "Legion Hammer", "Nightmare Mace", "Ornate Mace", "Pernarch", "Petrified Club", "Phantom Mace", "Rock Breaker", "Spiked Club", "Stone Hammer", "Tenderizer", "Tribal Club", "War Hammer", "Wyrm Mace"],
    "Amulet": ["Agate Amulet", "Amber Amulet", "Ashscale Talisman", "Avian Twins Talisman", "Black Maw Talisman", "Blue Pearl Amulet", "Bonespire Talisman", "Breakrib Talisman", "Chrysalis Talisman", "Citrine Amulet", "Clutching Talisman", "Coral Amulet", "Deadhand Talisman", "Deep One Talisman", "Fangjaw Talisman", "Gold Amulet", "Greatwolf Talisman", "Hexclaw Talisman", "Horned Talisman", "Jade Amulet", "Jet Amulet", "Lapis Amulet", "Lone Antler Talisman", "Longtooth Talisman", "Mandible Talisman", "Marble Amulet", "Monkey Paw Talisman", "Monkey Twins Talisman", "Onyx Amulet", "Paua Amulet", "Primal Skull Talisman", "Rot Head Talisman", "Rotfeather Talisman", "Ruby Amulet", "Spinefuse Talisman", "Splitnewt Talisman", "Three Hands Talisman", "Three Rat Talisman", "Turquoise Amulet", "Undying Flesh Talisman", "Wereclaw Talisman", "Writhing Talisman"],
    "Two Hand Mace": ["Brass Maul", "Colossus Mallet", "Coronal Maul", "Dread Maul", "Driftwood Maul", "Fright Maul", "Great Mallet", "Imperial Maul", "Jagged Maul", "Karui Maul", "Mallet", "Meatgrinder", "Morning Star", "Piledriver", "Plated Maul", "Sledgehammer", "Solar Maul", "Spiny Maul", "Steelhead", "Terror Maul", "Totemic Maul", "Tribal Maul"],
    "Sceptre": ["Abyssal Sceptre", "Blood Sceptre", "Bronze Sceptre", "Carnal Sceptre", "Crystal Sceptre", "Darkwood Sceptre", "Driftwood Sceptre", "Grinning Fetish", "Horned Sceptre", "Iron Sceptre", "Karui Sceptre", "Lead Sceptre", "Ochre Sceptre", "Opal Sceptre", "Platinum Sceptre", "Quartz Sceptre", "Ritual Sceptre", "Royal Sceptre", "Sambar Sceptre", "Sekhem", "Shadow Sceptre", "Stag Sceptre", "Tyrant's Sekhem", "Vaal Sceptre", "Void Sceptre"],
    "Two Hand Axe": ["Abyssal Axe", "Dagger Axe", "Despot Axe", "Double Axe", "Ezomyte Axe", "Fleshripper", "Gilded Axe", "Headsman Axe", "Jade Chopper", "Jasper Chopper", "Karui Chopper", "Labrys", "Noble Axe", "Poleaxe", "Shadow Axe", "Stone Axe", "Sundering Axe", "Talon Axe", "Timber Axe", "Vaal Axe", "Void Axe", "Woodsplitter"],
    #"Prophecy": ["A Call into the Void", "A Firm Foothold", "A Forest of False Idols", "A Gracious Master", "A Master Seeks Help", "A Prodigious Hand", "A Regal Death", "A Valuable Combination", "A Whispered Prayer", "Abnormal Effulgence", "Against the Tide", "An Unseen Peril", "Anarchy's End I", "Anarchy's End II", "Anarchy's End III", "Anarchy's End IV", "Ancient Doom", "Ancient Rivalries I", "Ancient Rivalries II", "Ancient Rivalries III", "Ancient Rivalries IV", "Baptism by Death", "Beyond Sight I", "Beyond Sight II", "Beyond Sight III", "Beyond Sight IV", "Beyond Sight V", "Blood in the Eyes", "Blood of the Betrayed", "Bountiful Traps", "Brothers in Arms", "Cleanser of Sins", "Crash Test", "Crushing Squall", "Custodians of Silence", "Day of Sacrifice I", "Day of Sacrifice II", "Day of Sacrifice III", "Day of Sacrifice IV", "Deadly Rivalry I", "Deadly Rivalry II", "Deadly Rivalry III", "Deadly Rivalry IV", "Deadly Rivalry V", "Deadly Twins", "Defiled in the Scepter", "Delay Test", "Delay and Crash Test", "Dying Cry", "Echoes of Lost Love", "Echoes of Mutation", "Echoes of Witchcraft", "Ending the Torment", "Enter the Maelstr\xf6m", "Erased from Memory", "Erasmus' Gift", "Fallow At Last", "Fated Connections", "Fear's Wide Reach", "Fire and Brimstone", "Fire and Ice", "Fire from the Sky", "Fire, Wood and Stone", "Flesh of the Beast", "Forceful Exorcism", "From Death Springs Life", "From The Void", "Gilded Within", "Golden Touch", "Graceful Flames", "Heart of the Fire", "Heavy Blows", "Hidden Reinforcements", "Hidden Vaal Pathways", "Holding the Bridge", "Hunter's Lesson", "Ice from Above", "In the Grasp of Corruption", "Kalandra's Craft", "Lasting Impressions", "Lightning Falls", "Living Fires", "Lost in the Pages", "Monstrous Treasure", "Mouth of Horrors", "Mysterious Invaders", "Nature's Resilience", "Nemesis of Greed", "Notched Flesh", "Overflowing Riches", "Path of Betrayal", "Plague of Frogs", "Plague of Rats", "Pleasure and Pain", "Pools of Wealth", "Possessed Foe", "Power Magnified", "Rebirth", "Reforged Bonds", "Resistant to Change", "Risen Blood", "Roth's Legacy", "SHOULD NOT APPEAR", "Sanctum of Stone", "Severed Limbs", "Smothering Tendrils", "Soil, Worms and Blood", "Storm on the Horizon", "Storm on the Shore", "Strong as a Bull", "Thaumaturgical History I", "Thaumaturgical History II", "Thaumaturgical History III", "Thaumaturgical History IV", "The Aesthete's Spirit", "The Alchemist", "The Ambitious Bandit I", "The Ambitious Bandit II", "The Ambitious Bandit III", "The Apex Predator", "The Beautiful Guide", "The Beginning and the End", "The Black Stone I", "The Black Stone II", "The Black Stone III", "The Black Stone IV", "The Blacksmith", "The Blessing", "The Bloody Flowers Redux", "The Bowstring's Music", "The Brothers of Necromancy", "The Brutal Enforcer", "The Child of Lunaris", "The Corrupt", "The Cursed Choir", "The Dream Trial", "The Dreamer's Dream", "The Eagle's Cry", "The Emperor's Trove", "The Feral Lord I", "The Feral Lord II", "The Feral Lord III", "The Feral Lord IV", "The Feral Lord V", "The Flayed Man", "The Flow of Energy", "The Forgotten Garrison", "The Forgotten Soldiers", "The Four Feral Exiles", "The God of Misfortune", "The Hardened Armour", "The Hollow Pledge", "The Hungering Swarm", "The Invader", "The Jeweller's Touch", "The Karui Rebellion", "The King and the Brambles", "The King's Path", "The Lady in Black", "The Last Watch", "The Lost Maps", "The Lost Undying", "The Misunderstood Queen", "The Mysterious Gift", "The Nest", "The Pair", "The Petrified", "The Pirate's Den", "The Plaguemaw I", "The Plaguemaw II", "The Plaguemaw III", "The Plaguemaw IV", "The Plaguemaw V", "The Prison Guard", "The Prison Key", "The Queen's Vaults", "The Scout", "The Servant's Heart", "The Sharpened Blade", "The Silverwood", "The Singular Spirit", "The Sinner's Stone", "The Snuffed Flame", "The Soulless Beast", "The Spread of Corruption", "The Stockkeeper", "The Sword King's Passion", "The Trembling Earth", "The Twins", "The Unbreathing Queen I", "The Unbreathing Queen II", "The Unbreathing Queen III", "The Unbreathing Queen IV", "The Unbreathing Queen V", "The Undead Brutes", "The Undead Storm", "The Vanguard", "The Walking Mountain", "The Ward's Ward", "The Warmongers I", "The Warmongers II", "The Warmongers III", "The Warmongers IV", "The Watcher's Watcher", "The Wealthy Exile", "Through the Mirage", "Touched by Death", "Touched by the Wind", "Trash to Treasure", "Twice Enchanted", "Unbearable Whispers I", "Unbearable Whispers II", "Unbearable Whispers III", "Unbearable Whispers IV", "Unbearable Whispers V", "Undead Uprising", "Unnatural Energy", "Vaal Invasion", "Vaal Winds", "Visions of the Drowned", "Vital Transformation", "Waiting in Ambush", "Weeping Death", "Wind and Thunder", "Winter's Mournful Melodies"],
    #"Gem": ["Abyssal Cry", "Added Chaos Damage", "Added Cold Damage", "Added Fire Damage", "Added Lightning Damage", "Additional Accuracy", "Ancestral Protector", "Ancestral Warchief", "Anger", "Animate Guardian", "Animate Weapon", "Arc", "Arctic Armour", "Arctic Breath", "Assassin's Mark", "Ball Lightning", "Barrage", "Bear Trap", "Blade Flurry", "Blade Vortex", "Bladefall", "Blasphemy", "Blast Rain", "Blight", "Blind", "Blink Arrow", "Block Chance Reduction", "Blood Magic", "Blood Rage", "Bloodlust", "Bone Offering", "Burning Arrow", "Cast On Critical Strike", "Cast on Death", "Cast on Melee Kill", "Cast when Damage Taken", "Cast when Stunned", "Caustic Arrow", "Chain", "Chance to Flee", "Chance to Ignite", "Clarity", "Cleave", "Cluster Traps", "Cold Penetration", "Cold Snap", "Cold to Fire", "Concentrated Effect", "Conductivity", "Contagion", "Controlled Destruction", "Conversion Trap", "Convocation", "Culling Strike", "Curse On Hit", "Cyclone", "Decoy Totem", "Desecrate", "Determination", "Detonate Dead", "Detonate Mines", "Devouring Totem", "Discharge", "Discipline", "Dominating Blow", "Double Strike", "Dual Strike", "Earthquake", "Elemental Focus", "Elemental Hit", "Elemental Proliferation", "Elemental Weakness", "Empower", "Endurance Charge on Melee Stun", "Enduring Cry", "Enfeeble", "Enhance", "Enlighten", "Essence Drain", "Ethereal Knives", "Explosive Arrow", "Faster Attacks", "Faster Casting", "Faster Projectiles", "Fire Nova Mine", "Fire Penetration", "Fire Trap", "Fireball", "Firestorm", "Flame Dash", "Flame Surge", "Flame Totem", "Flameblast", "Flammability", "Flesh Offering", "Flicker Strike", "Fork", "Fortify", "Freeze Mine", "Freezing Pulse", "Frenzy", "Frost Blades", "Frost Bomb", "Frost Wall", "Frostbite", "Frostbolt", "Generosity", "Glacial Cascade", "Glacial Hammer", "Grace", "Greater Multiple Projectiles", "Ground Slam", "Haste", "Hatred", "Heavy Strike", "Herald of Ash", "Herald of Ice", "Herald of Thunder", "Hypothermia", "Ice Bite", "Ice Crash", "Ice Nova", "Ice Shot", "Ice Spear", "Ice Trap", "Immortal Call", "Incinerate", "Increased Area of Effect", "Increased Burning Damage", "Increased Critical Damage", "Increased Critical Strikes", "Increased Duration", "Infernal Blow", "Innervate", "Iron Grip", "Iron Will", "Item Quantity", "Item Rarity", "Kinetic Blast", "Knockback", "Lacerate", "Leap Slam", "Less Duration", "Lesser Multiple Projectiles", "Life Gain on Hit", "Life Leech", "Lightning Arrow", "Lightning Penetration", "Lightning Strike", "Lightning Tendrils", "Lightning Trap", "Lightning Warp", "Magma Orb", "Mana Leech", "Melee Damage on Full Life", "Melee Physical Damage", "Melee Splash", "Minefield", "Minion Damage", "Minion Life", "Minion Speed", "Minion and Totem Elemental Resistance", "Mirror Arrow", "Molten Shell", "Molten Strike", "Multiple Traps", "Multistrike", "Orb of Storms", "Phase Run", "Physical Projectile Attack Damage", "Physical to Lightning", "Pierce", "Poacher's Mark", "Point Blank", "Poison", "Portal", "Power Charge On Critical", "Power Siphon", "Projectile Weakness", "Puncture", "Punishment", "Purity of Elements", "Purity of Fire", "Purity of Ice", "Purity of Lightning", "Rain of Arrows", "Raise Spectre", "Raise Zombie", "Rallying Cry", "Ranged Attack Totem", "Rapid Decay", "Reave", "Reckoning", "Reduced Mana", "Rejuvenation Totem", "Remote Mine", "Righteous Fire", "Riposte", "Scorching Ray", "Searing Bond", "Shield Charge", "Shock Nova", "Shockwave Totem", "Shrapnel Shot", "Siege Ballista", "Slower Projectiles", "Smoke Mine", "Spark", "Spectral Throw", "Spell Echo", "Spell Totem", "Spirit Offering", "Split Arrow", "Static Strike", "Storm Call", "Stun", "Summon Chaos Golem", "Summon Flame Golem", "Summon Ice Golem", "Summon Lightning Golem", "Summon Raging Spirit", "Summon Skeletons", "Summon Stone Golem", "Sunder", "Sweep", "Tempest Shield", "Temporal Chains", "Tornado Shot", "Trap", "Trap Cooldown", "Trap and Mine Damage", "Vaal Arc", "Vaal Burning Arrow", "Vaal Clarity", "Vaal Cold Snap", "Vaal Cyclone", "Vaal Detonate Dead", "Vaal Discipline", "Vaal Double Strike", "Vaal Fireball", "Vaal Flameblast", "Vaal Glacial Hammer", "Vaal Grace", "Vaal Ground Slam", "Vaal Haste", "Vaal Ice Nova", "Vaal Immortal Call", "Vaal Lightning Strike", "Vaal Lightning Trap", "Vaal Lightning Warp", "Vaal Molten Shell", "Vaal Power Siphon", "Vaal Rain of Arrows", "Vaal Reave", "Vaal Righteous Fire", "Vaal Spark", "Vaal Spectral Throw", "Vaal Storm Call", "Vaal Summon Skeletons", "Vengeance", "Vigilant Strike", "Viper Strike", "Vitality", "Void Manipulation", "Vortex", "Vulnerability", "Warlord's Mark", "Weapon Elemental Damage", "Whirling Blades", "Wild Strike", "Wither", "Wrath"],
    "Two Hand Sword": ["Bastard Sword", "Butcher Sword", "Corroded Blade", "Curved Blade", "Engraved Greatsword", "Etched Greatsword", "Exquisite Blade", "Ezomyte Blade", "Footman Sword", "Headman's Sword", "Highland Blade", "Infernal Sword", "Lion Sword", "Lithe Blade", "Longsword", "Ornate Sword", "Reaver Sword", "Spectral Sword", "Tiger Sword", "Two-Handed Sword", "Vaal Greatsword", "Wraith Sword"],
    "Jewel": ["Cobalt Jewel", "Crimson Jewel", "Prismatic Jewel", "Viridian Jewel"],
    "Bow": ["Assassin Bow", "Bone Bow", "Citadel Bow", "Composite Bow", "Compound Bow", "Crude Bow", "Death Bow", "Decimation Bow", "Decurve Bow", "Golden Flame", "Grove Bow", "Harbinger Bow", "Highborn Bow", "Imperial Bow", "Ivory Bow", "Long Bow", "Maraketh Bow", "Ranger Bow", "Recurve Bow", "Reflex Bow", "Royal Bow", "Short Bow", "Sniper Bow", "Spine Bow", "Steelwood Bow", "Thicket Bow"],
    "Gloves": ["Ambush Mitts", "Ancient Gauntlets", "Antique Gauntlets", "Arcanist Gloves", "Assassin's Mitts", "Bronze Gauntlets", "Bronzescale Gauntlets", "Carnal Mitts", "Chain Gloves", "Clasped Mitts", "Conjurer Gloves", "Crusader Gloves", "Deerskin Gloves", "Dragonscale Gauntlets", "Eelskin Gloves", "Embroidered Gloves", "Fingerless Silk Gloves", "Fishscale Gauntlets", "Goathide Gloves", "Golden Bracers", "Goliath Gauntlets", "Gripped Gloves", "Hydrascale Gauntlets", "Iron Gauntlets", "Ironscale Gauntlets", "Legion Gloves", "Mesh Gloves", "Murder Mitts", "Nubuck Gloves", "Plated Gauntlets", "Rawhide Gloves", "Ringmail Gloves", "Riveted Gloves", "Samite Gloves", "Satin Gloves", "Serpentscale Gauntlets", "Shagreen Gloves", "Sharkskin Gloves", "Silk Gloves", "Slink Gloves", "Soldier Gloves", "Sorcerer Gloves", "Spiked Gloves", "Stealth Gloves", "Steel Gauntlets", "Steelscale Gauntlets", "Strapped Mitts", "Titan Gauntlets", "Trapper Mitts", "Vaal Gauntlets", "Velvet Gloves", "Wool Gloves", "Wrapped Mitts", "Wyrmscale Gauntlets", "Zealot Gloves"],
    #"Fragments": ["Eber's Key", "Fragment of the Chimera", "Fragment of the Hydra", "Fragment of the Minotaur", "Fragment of the Phoenix", "Inya's Key", "Mortal Grief", "Mortal Hope", "Mortal Ignorance", "Mortal Rage", "Offering to the Goddess", "Sacrifice at Dawn", "Sacrifice at Dusk", "Sacrifice at Midnight", "Sacrifice at Noon", "Volkuur's Key", "Yriel's Key"],
    "Quiver": ["Blunt Arrow Quiver", "Broadhead Arrow Quiver", "Conductive Quiver", "Cured Quiver", "Fire Arrow Quiver", "Heavy Quiver", "Light Quiver", "Penetrating Arrow Quiver", "Rugged Quiver", "Serrated Arrow Quiver", "Sharktooth Arrow Quiver", "Spike-Point Arrow Quiver", "Two-Point Arrow Quiver"],
    "Dagger": ["Ambusher", "Boot Blade", "Boot Knife", "Butcher Knife", "Carving Knife", "Copper Kris", "Demon Dagger", "Ezomyte Dagger", "Fiend Dagger", "Flaying Knife", "Glass Shank", "Golden Kris", "Gutting Knife", "Imp Dagger", "Imperial Skean", "Platinum Kris", "Poignard", "Prong Dagger", "Royal Skean", "Sai", "Skean", "Skinning Knife", "Slaughter Knife", "Stiletto", "Trisula"],
    "Shield": ["Alder Spiked Shield", "Alloyed Spiked Shield", "Ancient Spirit Shield", "Angelic Kite Shield", "Archon Kite Shield", "Baroque Round Shield", "Battle Buckler", "Bone Spirit Shield", "Branded Kite Shield", "Brass Spirit Shield", "Bronze Tower Shield", "Buckskin Tower Shield", "Burnished Spiked Shield", "Cardinal Round Shield", "Cedar Tower Shield", "Ceremonial Kite Shield", "Champion Kite Shield", "Chiming Spirit Shield", "Colossal Tower Shield", "Compound Spiked Shield", "Copper Tower Shield", "Corroded Tower Shield", "Corrugated Buckler", "Crested Tower Shield", "Crimson Round Shield", "Crusader Buckler", "Driftwood Spiked Shield", "Ebony Tower Shield", "Elegant Round Shield", "Enameled Buckler", "Etched Kite Shield", "Ezomyte Spiked Shield", "Ezomyte Tower Shield", "Fir Round Shield", "Fossilised Spirit Shield", "Gilded Buckler", "Girded Tower Shield", "Goathide Buckler", "Golden Buckler", "Hammered Buckler", "Harmonic Spirit Shield", "Imperial Buckler", "Ironwood Buckler", "Ivory Spirit Shield", "Jingling Spirit Shield", "Lacewood Spirit Shield", "Lacquered Buckler", "Laminated Kite Shield", "Layered Kite Shield", "Linden Kite Shield", "Mahogany Tower Shield", "Maple Round Shield", "Mirrored Spiked Shield", "Mosaic Kite Shield", "Oak Buckler", "Ornate Spiked Shield", "Painted Buckler", "Painted Tower Shield", "Pine Buckler", "Pinnacle Tower Shield", "Plank Kite Shield", "Polished Spiked Shield", "Rawhide Tower Shield", "Redwood Spiked Shield", "Reinforced Kite Shield", "Reinforced Tower Shield", "Rotted Round Shield", "Scarlet Round Shield", "Shagreen Tower Shield", "Sovereign Spiked Shield", "Spiked Bundle", "Spiked Round Shield", "Spiny Round Shield", "Splendid Round Shield", "Splintered Tower Shield", "Steel Kite Shield", "Studded Round Shield", "Supreme Spiked Shield", "Tarnished Spirit Shield", "Teak Round Shield", "Thorium Spirit Shield", "Titanium Spirit Shield", "Twig Spirit Shield", "Vaal Buckler", "Vaal Spirit Shield", "Walnut Spirit Shield", "War Buckler", "Yew Spirit Shield"],
    "Wand": ["Carved Wand", "Crystal Wand", "Demon's Horn", "Driftwood Wand", "Engraved Wand", "Faun's Horn", "Goat's Horn", "Heathen Wand", "Imbued Wand", "Omen Wand", "Opal Wand", "Pagan Wand", "Profane Wand", "Prophecy Wand", "Quartz Wand", "Sage Wand", "Serpent Wand", "Spiraled Wand", "Tornado Wand"],
    #"Essence": ["Essence of Anger", "Essence of Anguish", "Essence of Contempt", "Essence of Delirium", "Essence of Doubt", "Essence of Dread", "Essence of Envy", "Essence of Fear", "Essence of Greed", "Essence of Hatred", "Essence of Horror", "Essence of Hysteria", "Essence of Insanity", "Essence of Loathing", "Essence of Misery", "Essence of Rage", "Essence of Scorn", "Essence of Sorrow", "Essence of Spite", "Essence of Suffering", "Essence of Torment", "Essence of Woe", "Essence of Wrath", "Essence of Zeal", "Remnant of Corruption"],
    "Boots": ["Ambush Boots", "Ancient Greaves", "Antique Greaves", "Arcanist Slippers", "Assassin's Boots", "Bronzescale Boots", "Carnal Boots", "Chain Boots", "Clasped Boots", "Conjurer Boots", "Crusader Boots", "Deerskin Boots", "Dragonscale Boots", "Eelskin Boots", "Goathide Boots", "Golden Caligae", "Goliath Greaves", "Hydrascale Boots", "Iron Greaves", "Ironscale Boots", "Leatherscale Boots", "Legion Boots", "Mesh Boots", "Murder Boots", "Nubuck Boots", "Plated Greaves", "Rawhide Boots", "Reinforced Greaves", "Ringmail Boots", "Riveted Boots", "Samite Slippers", "Satin Slippers", "Scholar Boots", "Serpentscale Boots", "Shackled Boots", "Shagreen Boots", "Sharkskin Boots", "Silk Slippers", "Slink Boots", "Soldier Boots", "Sorcerer Boots", "Stealth Boots", "Steel Greaves", "Steelscale Boots", "Strapped Boots", "Titan Greaves", "Trapper Boots", "Two-Toned Boots", "Vaal Greaves", "Velvet Slippers", "Wool Shoes", "Wrapped Boots", "Wyrmscale Boots", "Zealot Boots"],
    #"Currency": ["Albino Rhoa Feather", "Apprentice Cartographer's Seal", "Apprentice Cartographer's Sextant", "Armourer's Scrap", "Blacksmith's Whetstone", "Blessed Orb", "Cartographer's Chisel", "Chaos Orb", "Chromatic Orb", "Divine Orb", "Eternal Orb", "Exalted Orb", "Gemcutter's Prism", "Glassblower's Bauble", "Jeweller's Orb", "Journeyman Cartographer's Seal", "Journeyman Cartographer's Sextant", "Master Cartographer's Seal", "Master Cartographer's Sextant", "Mirror of Kalandra", "Orb of Alchemy", "Orb of Alteration", "Orb of Augmentation", "Orb of Chance", "Orb of Fusing", "Orb of Regret", "Orb of Scouring", "Orb of Transmutation", "Perandus Coin", "Portal Scroll", "Regal Orb", "Scroll of Wisdom", "Silver Coin", "Unshaping Orb", "Vaal Orb"],
    "Ring": ["Amethyst Ring", "Breach Ring", "Coral Ring", "Diamond Ring", "Gold Ring", "Golden Hoop", "Iron Ring", "Moonstone Ring", "Opal Ring", "Paua Ring", "Prismatic Ring", "Ruby Ring", "Sapphire Ring", "Steel Ring", "Topaz Ring", "Two-Stone Ring", "Unset Ring"],
    "Belt": ["Chain Belt", "Cloth Belt", "Crystal Belt", "Golden Obi", "Heavy Belt", "Leather Belt", "Rustic Sash", "Studded Belt", "Vanguard Belt"],
    "Staff": ["Coiled Staff", "Crescent Staff", "Eclipse Staff", "Ezomyte Staff", "Foul Staff", "Gnarled Branch", "Highborn Staff", "Imperial Staff", "Iron Staff", "Judgement Staff", "Lathi", "Long Staff", u"Maelstr\xf6m Staff", "Military Staff", "Moon Staff", "Primitive Staff", "Primordial Staff", "Quarterstaff", "Royal Staff", "Serpentine Staff", "Vile Staff", "Woodful Staff"]
}

def get_item_subtype(name):
    return all_bases[item_types[name]].index(name)

type_hash = {}
sorted_types = sorted(all_bases.keys())
for key in sorted_types:
    type_hash[key] = sorted_types.index(key)

item_types = {}
for base in all_bases:
    for t in all_bases[base]:
        item_types[t] = base
