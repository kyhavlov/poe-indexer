import csv
import numpy as np
import tensorflow as tf
import json
import util

tf.logging.set_verbosity(tf.logging.INFO)


# Our application logic will be added here
def main(unused_argv):
    json_data = open('amulets.json').read()
    items = json.loads(json_data)

    print(get_mods(items[0]))

    mod_lists = {
        'implicit': dict(),
        'crafted': dict(),
        'explicit': dict(),
    }

    max_mods = {'implicit': 1, 'crafted': 1, 'explicit': 6}

    for item in items:
        mods = get_mods(item)
        for mod_type in mod_lists:
            for mod in mods[mod_type][::2]:
                mod_lists[mod_type][mod] = 0

    for mod_type in mod_lists:
        temp_list = sorted(list(mod_lists[mod_type]))
        mod_ids = {}
        for i in range(len(temp_list)):
            mod_ids[temp_list[i]] = i+1
        mod_lists[mod_type] = mod_ids

    print(mod_lists['explicit'])

    entries = np.zeros([len(items), 18], dtype=float)
    classes = np.zeros([len(items), 1])
    for i in range(len(items)):
        item = items[i]
        item_entry = [item['ilvl'], 1 if item['corrupted'] else 0]
        mods = get_mods(item)

        if 'implicitMods' in item:
            mod_type = 'implicit'
            item_entry.append(mod_lists[mod_type][mods[mod_type][0]])
            item_entry.append(mods[mod_type][1])
        else:
            item_entry.extend([0] * 2)

        if 'craftedMods' in item:
            mod_type = 'crafted'
            item_entry.append(mod_lists[mod_type][mods[mod_type][0]])
            item_entry.append(mods[mod_type][1])
        else:
            item_entry.extend([0] * 2)

        if 'explicitMods' in item:
            mod_type = 'explicit'
            for j in range(int(len(mods[mod_type]) / 2)):
                item_entry.append(mod_lists[mod_type][mods[mod_type][j * 2]])
                item_entry.append(mods[mod_type][j * 2 + 1])
            if len(mods[mod_type]) < 12:
                item_entry.extend([0] * (12 - len(mods[mod_type])))
        else:
            item_entry.extend([0] * 12)

        entries[i] = np.array(item_entry)
        classes[i] = util.price_bucket(item['price_chaos'])

    np.savetxt('amulets.csv', entries, fmt='%.2f')
    np.savetxt('amulet_classes.csv', classes, fmt='%.2f')

    print(items[123])
    print(entries[123])
    print(classes[123])


def get_mods(item):
    mods = {
        'implicit': [],
        'explicit': [],
        'crafted': [],
    }

    for mod_type in mods:
        category = mod_type + 'Mods'
        if category in item and len(item[category]) > 0:
            for mod in item[category]:
                name, value = util.format_mod(mod)
                mods[mod_type].extend([name, value])

    return mods

if __name__ == "__main__":
    tf.app.run(main)
