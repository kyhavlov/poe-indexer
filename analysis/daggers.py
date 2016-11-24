from elasticsearch import Elasticsearch
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNLinearCombinedRegressor
import tempfile
import util
tf.logging.set_verbosity(tf.logging.INFO)

es = Elasticsearch(hosts=["192.168.1.4:9200"])

# Query elasticsearch for the items to use for the data set
results = es.search(index="items", body={
    "size": 2500,
    "query": {
        "bool": {
            "must": [{
                "match_phrase": {"properties.name": "Dagger"}
            }, {
                "script": {
                    "script": "doc['removed'].value >  doc['last_updated'].value"
                }
            }]
        }
    }
})

# Initialize the columns to use
# Continuous means the variable is a number instead of something discrete, like a mod name
CONTINUOUS_COLUMNS = [
    'ilvl',
    'corrupted',
    'frameType',
    'Quality',
    'Physical Damage',
    'Critical Strike Chance',
    'Attacks per Second',
    'Level',
    'Str',
    'Dex',
    'Int',
]

# Categorical columns are for things like typeLine, which will have category values
# such as 'Skean' or 'Platinum Kris'
CATEGORICAL_COLUMNS = [
    'typeLine'
]

# price is our column to predict
LABEL_COLUMN = 'price_chaos'

COLUMNS = []
COLUMNS.extend(CONTINUOUS_COLUMNS)
COLUMNS.extend(CATEGORICAL_COLUMNS)
COLUMNS.append(LABEL_COLUMN)
data = []
mod_names = {}

# Fill out the columns
for item in results['hits']['hits']:
    # Do basic formatting of the item
    i = util.format_item(item['_source'])
    if i is None:
        continue

    if i['price_chaos'] >= 100 or i['price_chaos'] < 1:
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
percent_test = 10
n = (len(data) * percent_test)/100
df_train = pd.DataFrame(data[:-n])
df_test = pd.DataFrame(data[-n:])

# Add mod names to continuous columns
for mod in mod_names:
    CONTINUOUS_COLUMNS.append(mod)

# Replace spaces in column names because wtf tensorflow
for i in range(len(CONTINUOUS_COLUMNS)):
    orig = CONTINUOUS_COLUMNS[i]
    col = orig.replace(" ", "_").replace("%", "").replace("+", "").replace("'", "").replace(",", "")
    CONTINUOUS_COLUMNS[i] = col
    df_train.rename(columns={orig: col}, inplace=True)
    df_test.rename(columns={orig: col}, inplace=True)
    if col not in df_train:
        df_train[col] = np.nan
    if col not in df_test:
        df_test[col] = np.nan

print("Got %d Hits:" % len(data))
print(len(CONTINUOUS_COLUMNS))
print(len(df_train.columns))
print(len(df_test.columns))

#print("Training data:")
#print(df_train)
#print("Test data:")
#print(df_test)

#df_train.to_csv('daggers.csv')

# input_fn takes a pandas dataframe and returns some input columns and an output column
def input_fn(df):
    # Creates a dictionary mapping from each continuous feature column name (k) to
    # the values of that column stored in a constant Tensor.
    continuous_cols = {k: tf.constant(df[k].values)
                       for k in CONTINUOUS_COLUMNS}
    # Creates a dictionary mapping from each categorical feature column name (k)
    # to the values of that column stored in a tf.SparseTensor.
    categorical_cols = {k: tf.SparseTensor(
        indices=[[i, 0] for i in range(df[k].size)],
        values=df[k].values,
        shape=[df[k].size, 1])
                        for k in CATEGORICAL_COLUMNS}
    # Merges the two dictionaries into one.
    feature_cols = dict(continuous_cols.items() + categorical_cols.items())
    # Converts the label column into a constant Tensor.
    label = tf.constant(df[LABEL_COLUMN].values)
    # Returns the feature columns and the label.
    return feature_cols, label

def train_input_fn():
    return input_fn(df_train)

def eval_input_fn():
    return input_fn(df_test)

# set up tensorflow column names
deep_columns = []
for col in CONTINUOUS_COLUMNS:
    deep_columns.append(tf.contrib.layers.real_valued_column(col))
wide_columns = []
for col in CATEGORICAL_COLUMNS:
    wide_col = tf.contrib.layers.sparse_column_with_hash_bucket(col, hash_bucket_size=1000)
    wide_columns.append(wide_col)
    deep_columns.append(tf.contrib.layers.embedding_column(wide_col, dimension=8))

print('deep column count: %d' % len(deep_columns))
print('wide column count: %d' % len(wide_columns))

model_dir = tempfile.mkdtemp()
model = DNNLinearCombinedRegressor(model_dir=model_dir, linear_feature_columns=wide_columns,
                                   dnn_feature_columns=deep_columns, dnn_hidden_units=[80, 60, 40, 20, 10])

model.fit(input_fn=train_input_fn, steps=2000)

results = model.evaluate(input_fn=eval_input_fn, steps=1)
for key in sorted(results):
    print "%s: %s" % (key, results[key])
