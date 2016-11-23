import pandas as pd
import re
import tensorflow as tf
from tensorflow.contrib.learn import DNNRegressor
import tempfile
from elasticsearch import Elasticsearch

es = Elasticsearch(hosts=["192.168.1.4:9200"])

# Query elasticsearch for the items to use for the data set
results = es.search(index="items", body={
    "size": 200,
    "query": {
        "bool": {
            "must": [{
                "match_phrase": {"typeLine": "Vaal Haste"}
            }, {
                "exists": {"field": "removed"}
            }]
        }
    }
})

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

# initialize the columns to use
level = []
quality = []
price = []

items = []
# format item documents to be easier to use
for item in results['hits']['hits']:
    def cleanProperties(item, name):
        properties = {}
        if name in item:
            for prop in item[name]:
                # flatten value array
                properties[prop['name']] = [value for sublist in prop['values'] for value in sublist]
        return properties

    i = item['_source']
    i['properties'] = cleanProperties(i, 'properties')
    i['additionalProperties'] = cleanProperties(i, 'additionalProperties')
    i['requirements'] = cleanProperties(i, 'requirements')

    m = re.search('\S+ (\d+\.?\d*) (\w+)', i['price'])
    if m is None:
        continue
    i['price_chaos'] = float(m.group(1)) * currency_values[m.group(2)]
    items.append(i)

    # Ignore this item if it moved tabs instead of being sold, or if the buyout's too low
    if i['removed'] - i['last_updated'] <= 10:
        continue

    if i['price_chaos'] < 6.0 or i['price_chaos'] > 25.0:
        continue

    # set up data set
    level.append(int(i['properties']['Level'][0].replace(' (Max)', '')))
    if 'Quality' in i['properties']:
        quality.append(int(i['properties']['Quality'][0][1:-1]))
    else:
        quality.append(0)

    price.append(i['price_chaos'])


# Format the results into pandas dataframes
n = len(price)/6
df_train = pd.DataFrame({'level': pd.Series(level[n:]),
                         'quality': pd.Series(quality[n:]),
                         'price': pd.Series(price[n:])})
df_test = pd.DataFrame({'level': pd.Series(level[:n]),
                         'quality': pd.Series(quality[:n]),
                         'price': pd.Series(price[:n])})

print("Got %d Hits:" % results['hits']['total'])
print("Training data:")
print(df_train)
print("Test data:")
print(df_test)

# Continuous means the variable is a number instead of something discrete, like a mod name
CONTINUOUS_COLUMNS = [
    'level',
    'quality',
]

# price is our column to predict
LABEL_COLUMN = 'price'

# input_fn takes a pandas dataframe and returns some input columns and an output column
def input_fn(df):
    # Creates a dictionary mapping from each continuous feature column name (k) to
    # the values of that column stored in a constant Tensor.
    continuous_cols = {k: tf.constant(df[k].values)
                       for k in CONTINUOUS_COLUMNS}

    # Converts the label column into a constant Tensor.
    label = tf.constant(df[LABEL_COLUMN].values)
    # Returns the feature columns and the label.
    return continuous_cols, label

def train_input_fn():
    return input_fn(df_train)

def eval_input_fn():
    return input_fn(df_test)

# set up some tensorflow column names
level = tf.contrib.layers.real_valued_column('level')
quality = tf.contrib.layers.real_valued_column('quality')

deep_columns = [level, quality]

model_dir = tempfile.mkdtemp()
model = DNNRegressor(model_dir=model_dir, feature_columns=deep_columns, hidden_units=[100, 50])

model.fit(input_fn=train_input_fn, steps=100)

results = model.evaluate(input_fn=eval_input_fn, steps=1)
for key in sorted(results):
    print "%s: %s" % (key, results[key])

# predict the price of a single level 20, 0 quality vaal haste
df_pred = pd.DataFrame({'level': pd.Series([20]),
                        'quality': pd.Series([0]),
                        'price': pd.Series()})

def predict_fn():
    return input_fn(df_pred)

prediction = model.predict(input_fn=predict_fn)
print(prediction)
