import os.path
import numpy as np
import pandas as pd
import util

# Query elasticsearch for the items to use for the data set
def download_data(query_body, filename):
    query_results = util.es_bulk_query(query_body)

    data = []
    columns = set()

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

        row = util.item_to_row(i)
        for col in row:
            columns.add(col)

        data.append(row)

        count += 1
        if count % 10000 == 0:
            print('processed %d results' % count)

    print('column count: ', len(columns))

    # Format the results into a pandas dataframe
    percent_test = 20
    n = (len(data) * percent_test)/100
    df = pd.DataFrame(data, columns=sorted(columns))

    print("Got %d Hits:" % len(data))

    print('exporting to csv...')
    # Shuffle the data to avoid organization during the ES query
    df = df.iloc[np.random.permutation(len(df))]
    df.to_csv(filename, index=False, encoding='utf-8')

base_query = {
    "query": {
        "bool": {
            "should": [
                #{"match_phrase": {"typeLine": "Assassin Bow"}},
            ],
            "minimum_should_match": 1,
            # Don't include magic items, they mess with the typeLine
            "must_not": [
                {"match": {"frameType": 1}}
            ],
            "must": [
                {"script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value && doc['removed'].value > 1480915463"
                }
            }]
        }
    }
}

for item_type in util.all_bases:
    matches = []
    for subtype in util.all_bases[item_type]:
        matches.append({"match_phrase": {"typeLine": subtype}})
    base_query["query"]["bool"]["should"] = matches
    filename = "data/" + item_type.lower().replace(" ", "_") + ".csv"
    if not os.path.isfile(filename):
        print("==> Fetching data for '%s'" % item_type)
        download_data(base_query, filename)
