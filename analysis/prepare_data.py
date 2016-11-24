import numpy as np
import operator
import pandas as pd
import util

# Query elasticsearch for the items to use for the data set
query_results = util.es_bulk_query({
    "query": {
        "bool": {
            "must": [{
                "match_phrase": {"properties.name": "Attacks per Second"}
            }, {
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

# Fill out the columns
for item in query_results:
    # Do basic formatting of the item
    i = util.format_item(item['_source'])
    if i is None:
        continue

    if i['price_chaos'] > 50.0:
        continue

    if i['frameType'] == 3:
        continue

    row = {}

    util.prop_or_default(i, 'Quality', 0)
    util.prop_or_default(i, 'Physical Damage', 0.0)
    util.prop_or_default(i, 'Critical Strike Chance', 0.0)
    util.prop_or_default(i, 'Attacks per Second', 0.0)

    util.req_or_default(i, 'Level', 0)
    util.req_or_default(i, 'Str', 0)
    util.req_or_default(i, 'Dex', 0)
    util.req_or_default(i, 'Int', 0)

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
            row['implicit ' + name] = value
            mod_names['implicit ' + name] = True

    if 'explicitMods' in i and len(i['explicitMods']) > 0:
        for mod in i['explicitMods']:
            name, value = util.format_mod(mod)
            row[name] = value
            mod_names[name] = True

    # add each column for this item
    for c in COLUMNS:
        if c in i:
            row[c] = i[c]
    data.append(row)

# Format the results into pandas dataframes
percent_test = 30
n = (len(data) * percent_test)/100
df_train = pd.DataFrame(data[:-n])
df_test = pd.DataFrame(data[-n:])

# Add mod names to continuous columns
all_columns = util.CONTINUOUS_COLUMNS
for mod in mod_names:
    all_columns.append(mod)

# Replace illegal chars in column names and add missing columns where necessary
for i in range(len(all_columns)):
    orig = all_columns[i]
    col = orig.replace(" ", "_").replace("%", "").replace("+", "").replace("'", "").replace(",", "")
    df_train.rename(columns={orig: col}, inplace=True)
    df_test.rename(columns={orig: col}, inplace=True)
    if col not in df_train:
        df_train[col] = np.nan
    if col not in df_test:
        df_test[col] = np.nan

print("Got %d Hits:" % len(data))
print(len(df_train.columns))
print(len(df_test.columns))

print('exporting to csv...')
df_train.to_csv(util.TRAIN_FILE, index=False, encoding='utf-8')
df_test.to_csv(util.TEST_FILE, index=False, encoding='utf-8')
