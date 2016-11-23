from elasticsearch import Elasticsearch
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNRegressor
import tempfile
import util

es = Elasticsearch(hosts=["192.168.1.4:9200"])

# Query elasticsearch for the items to use for the data set
results = es.search(index="items", body={
    "size": 10000,
    "query": {
        "bool": {
            "must": [{
                "match_phrase": {"typeLine": "Vaal Haste"}
            }, {
                "script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value"
                }
            }]
        }
    }
})

# Initialize the columns to use
level = []
quality = []
price = []

items = []
# Fill out the columns
for item in results['hits']['hits']:
    i = util.format_item(item['_source'])
    if i is not None:
        items.append(i)
    else:
        continue

    if i['price_chaos'] < 6.0 or i['price_chaos'] > 25.0:
        continue

    # set up data set
    util.prop_or_default(i, 'Level', 0)
    level.append(i['Level'])
    util.prop_or_default(i, 'Quality', 0)
    quality.append(i['Quality'])

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
model = DNNRegressor(model_dir=model_dir, feature_columns=deep_columns, hidden_units=[100, 200, 50])

model.fit(input_fn=train_input_fn, steps=200)

results = model.evaluate(input_fn=eval_input_fn, steps=1)
for key in sorted(results):
    print "%s: %s" % (key, results[key])

# predict the price of a single level 20, 0 quality vaal haste
df_pred = pd.DataFrame({'level': pd.Series([1, 1, 20, 20]),
                        'quality': pd.Series([0, 20, 0, 20]),
                        'price': pd.Series()})

def predict_fn():
    return input_fn(df_pred)

prediction = model.predict(input_fn=predict_fn)
print(prediction)
