import numpy as np
import pandas as pd
import util

# Query elasticsearch for the items to use for the data set
'''query_results = util.es_bulk_query({
    "query": {
        "bool": {
            "should": [
                {"match": {"properties.name": "Armour Energy Evasion"}},
                {"match": {"typeLine": "Ring Amulet Talisman Quiver Belt Sash"}}
            ],
            "minimum_should_match": 1,
            # Don't include magic items, they mess with the typeLine
            "must_not": [
                {"match": {"frameType": 1}},
                # skip uniques for now too
                {"match": {"frameType": 3}}
            ],
            "must": [{
                "script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value"
                }
            }]
        }
    }
})'''
query_results = util.es_bulk_query({
    "query": {
        "bool": {
            # Don't include magic items, they mess with the typeLine
            "must_not": [
                {"match": {"frameType": 1}},
                # skip uniques for now too
                #{"match": {"frameType": 3}}
            ],
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

data = []

count = 0
# Fill out the columns
for item in query_results:
    # Ignore this item if it only moved tabs and wasn't sold, or if the buyout's too low
    if item['_source']['removed'] - item['_source']['last_updated'] <= 10:
        continue

    # Do basic formatting of the item
    i = util.format_item(item['_source'])
    if i['price_chaos'] > 195.0 or i['price_chaos'] < 0.0:
        continue

    data.append(util.item_to_row(i))

    count += 1
    if count % 1000 == 0:
        print('processed %d results' % count)

# Format the results into a pandas dataframe
percent_test = 20
n = (len(data) * percent_test)/100
df = pd.DataFrame(data)

# Replace illegal chars in column names and add missing columns where necessary
for i in range(len(df.columns)):
    orig = df.columns[i]
    col = util.format_column_name(orig)
    df.rename(columns={orig: col}, inplace=True)

print("Got %d Hits:" % len(data))
print('column count: ', len(df.columns))

print('exporting to csv...')
# Shuffle the data to avoid organization during the ES query
df = df.iloc[np.random.permutation(len(df))]
df.to_csv(util.TRAIN_FILE, index=False, encoding='utf-8')
