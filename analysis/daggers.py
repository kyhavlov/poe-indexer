from elasticsearch import Elasticsearch
import pandas as pd
import tensorflow as tf
import tensorflow.contrib.layers.python.ops.sparse_feature_cross_op
from tensorflow.contrib.learn import DNNLinearCombinedRegressor
import tempfile
import util

es = Elasticsearch(hosts=["192.168.1.4:9200"])

# Query elasticsearch for the items to use for the data set
results = es.search(index="items", body={
    "size": 10000,
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

IMPLICIT_COUNT = 1
EXPLICIT_COUNT = 8
for i in range(IMPLICIT_COUNT):
    CATEGORICAL_COLUMNS.append('implicit_mod%s' % i)
    CONTINUOUS_COLUMNS.append('implicit_mod%s_value' % i)
for i in range(EXPLICIT_COUNT):
    CATEGORICAL_COLUMNS.append('explicit_mod%s' % i)
    CONTINUOUS_COLUMNS.append('explicit_mod%s_value' % i)

# price is our column to predict
LABEL_COLUMN = 'price_chaos'

COLUMNS = []
COLUMNS.extend(CONTINUOUS_COLUMNS)
COLUMNS.extend(CATEGORICAL_COLUMNS)
COLUMNS.append(LABEL_COLUMN)
data = {}
for c in COLUMNS:
    data[c] = []

items = []
# Fill out the columns
for item in results['hits']['hits']:
    # Do basic formatting of the item
    i = util.format_item(item['_source'])
    if i is not None:
        items.append(i)
    else:
        continue

    util.prop_or_default(i, 'Quality', 0)
    util.prop_or_default(i, 'Physical Damage', 0.0)
    util.prop_or_default(i, 'Critical Strike Chance', 0.0)
    util.prop_or_default(i, 'Attacks per Second', 0.0)

    util.req_or_default(i, 'Level', 0)
    util.req_or_default(i, 'Str', 0)
    util.req_or_default(i, 'Dex', 0)
    util.req_or_default(i, 'Int', 0)

    for x in range(IMPLICIT_COUNT):
        if 'implicitMods' in i and len(i['implicitMods']) > x:
            mod, value = util.format_mod(i['implicitMods'][x])
            data['implicit_mod%s' % x].append(mod)
            data['implicit_mod%s_value' % x].append(value)
        else:
            data['implicit_mod%s' % x].append("")
            data['implicit_mod%s_value' % x].append(0.0)

    for x in range(EXPLICIT_COUNT):
        if 'explicitMods' in i and len(i['explicitMods']) > x:
            mod, value = util.format_mod(i['explicitMods'][x])
            data['explicit_mod%s' % x].append(mod)
            data['explicit_mod%s_value' % x].append(value)
        else:
            data['explicit_mod%s' % x].append("")
            data['explicit_mod%s_value' % x].append(0.0)

    # add each column for this item
    for c in COLUMNS:
        if c in i:
            data[c].append(i[c])

# Replace spaces because wtf tensorflow
for i in range(len(CONTINUOUS_COLUMNS)):
    orig = CONTINUOUS_COLUMNS[i]
    col = orig.replace(" ", "_")
    CONTINUOUS_COLUMNS[i] = col
    array = data.pop(orig)
    data[col] = array

# Format the results into pandas dataframes
percent_test = 10
n = (len(items) * percent_test)/100
df_train = pd.DataFrame({k: pd.Series(data[k][:-n]) for k in data})
df_test = pd.DataFrame({k: pd.Series(data[k][-n:]) for k in data})

print("Got %d Hits:" % len(items))
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

#print(deep_columns)
#print(wide_columns)

model_dir = tempfile.mkdtemp()
model = DNNLinearCombinedRegressor(model_dir=model_dir, linear_feature_columns=wide_columns,
                                   dnn_feature_columns=deep_columns, dnn_hidden_units=[100, 50])

model.fit(input_fn=train_input_fn, steps=500)

results = model.evaluate(input_fn=eval_input_fn, steps=1)
for key in sorted(results):
    print "%s: %s" % (key, results[key])

# predict the price of a single level 20, 0 quality vaal haste
'''df_pred = pd.DataFrame({'level': pd.Series([1, 16, 20, 20]),
                        'quality': pd.Series([0, 15, 0, 20]),
                        'price': pd.Series()})

def predict_fn():
    return input_fn(df_pred)

prediction = model.predict(input_fn=predict_fn)
print(prediction)
'''