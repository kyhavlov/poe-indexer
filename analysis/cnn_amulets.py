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

    entries = []
    for item in items:
        item_entry = [item['ilvl'], 1 if item['corrupted'] else 0]
        mods = get_mods(item)

        for mod_type in mod_lists:
            mod_category = mod_type + 'Mods'
            if mod_category not in item or len(item[mod_category]) == 0:
                item_entry.extend([0] * (max_mods[mod_type]*2))
            else:
                for i in range(int(len(mods[mod_type])/2)):
                    item_entry.append(mod_lists[mod_type][mods[mod_type][i*2]])
                    item_entry.append(mods[mod_type][i*2+1])
                if mod_type == 'explicit' and len(item[mod_category]) < 12:
                    item_entry.extend([0] * (12 - len(item[mod_category])))

        entries.append(item_entry)

    print(items[123])
    print(entries[123])


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
