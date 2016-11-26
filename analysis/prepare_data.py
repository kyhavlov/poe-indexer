import operator
import pandas as pd
import util

# Query elasticsearch for the items to use for the data set
query_results = util.es_bulk_query({
    "query": {
        "bool": {
            "should": [
                {"match": {"properties.name": "Armour Energy Evasion"}},
                {"match": {"typeLine": "Ring Amulet Talisman Quiver Belt Sash"}}
            ],
            "minimum_should_match": 1,
            # Don't include magic items, they mess with the typeLine
            "must_not": {
                "match": {"frameType": 1}
            },
            "must": [{
                "script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value"
                }
            }]
        }
    }
})

# price is our column to predict
COLUMNS = []
COLUMNS.extend(util.CONTINUOUS_COLUMNS)
COLUMNS.extend(util.CATEGORICAL_COLUMNS)
COLUMNS.append(util.LABEL_COLUMN)
data = []
mod_names = {}

types = {}

count = 0
# Fill out the columns
for item in query_results:
    # Do basic formatting of the item
    i = util.format_item(item['_source'])
    if i is None:
        continue

    if i['price_chaos'] > 65.0:
        continue

    row = {}

    types[i['itemType']] = True

    def add_mod(m, v):
        row[m] = v
        mod_names[m] = True

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
            name, value = util.format_mod(mod)
            add_mod('implicit_' + name, value)

    if 'explicitMods' in i and len(i['explicitMods']) > 0:
        for mod in i['explicitMods']:
            name, value = util.format_mod(mod)
            add_mod('explicit_'+name, value)

    # add each column for this item
    for c in COLUMNS:
        if c in i:
            row[c] = i[c]
    data.append(row)

    count += 1
    if count % 1000 == 0:
        print('processed %d results' % count)

print(types)

# Format the results into a pandas dataframe
percent_test = 20
n = (len(data) * percent_test)/100
df = pd.DataFrame(data)

# Replace illegal chars in column names and add missing columns where necessary
for i in range(len(df.columns)):
    orig = df.columns[i]
    col = orig.replace(" ", "_").replace("%", "").replace("+", "").replace("'", "").replace(",", "").replace("\n", "_")
    df.rename(columns={orig: col}, inplace=True)

print("Got %d Hits:" % len(data))
print('column count: ', len(df.columns))

print('exporting to csv...')
df.to_csv(util.TRAIN_FILE, index=False, encoding='utf-8')
