import json
import util

# Pull all the sold rare amulets from elasticsearch
base_query = {
    "query": {
        "bool": {
            "minimum_should_match": 1,
            "must": [
                {"match": {"frameType": 2}},
                {"script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value"
                }
            }]
        }
    }
}

matches = []
for subtype in util.all_bases["Amulet"]:
    matches.append({"match_phrase": {"typeLine": subtype}})
base_query["query"]["bool"]["should"] = matches

items = util.es_bulk_query(base_query)
print(len(items))
print(items[0])

for i in range(len(items)):
    items[i] = items[i]['_source']

with open('amulets.json', 'w') as outfile:
    json.dump(items, outfile)
