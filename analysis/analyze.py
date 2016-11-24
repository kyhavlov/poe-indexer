import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNLinearCombinedRegressor
import tempfile
import util
tf.logging.set_verbosity(tf.logging.INFO)

df_train = pd.read_csv(util.TRAIN_FILE, skipinitialspace=True, encoding='utf-8')
df_test = pd.read_csv(util.TEST_FILE, skipinitialspace=True, encoding='utf-8')

all_columns = set(df_train.columns).union(set(df_test.columns))
CONTINUOUS_COLUMNS = all_columns.copy()
CONTINUOUS_COLUMNS.remove(util.LABEL_COLUMN)
for col in util.CATEGORICAL_COLUMNS:
    CONTINUOUS_COLUMNS.remove(col)
CATEGORICAL_COLUMNS = util.CATEGORICAL_COLUMNS
LABEL_COLUMN = util.LABEL_COLUMN


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
    deep_columns.append(tf.contrib.layers.embedding_column(wide_col, dimension=10))

print('deep column count: %d' % len(deep_columns))
print('wide column count: %d' % len(wide_columns))

model_dir = tempfile.mkdtemp()
model = DNNLinearCombinedRegressor(model_dir=model_dir, linear_feature_columns=wide_columns,
                                   dnn_feature_columns=deep_columns, dnn_hidden_units=[200, 100, 50])

model.fit(input_fn=train_input_fn, steps=2000)

results = model.evaluate(input_fn=eval_input_fn, steps=1)
for key in sorted(results):
    print "%s: %s" % (key, results[key])