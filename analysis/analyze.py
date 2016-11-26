import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNRegressor
import util
tf.logging.set_verbosity(tf.logging.INFO)

df_all = pd.read_csv(util.TRAIN_FILE, skipinitialspace=True, encoding='utf-8')
df_all.fillna(0.0, inplace=True)

LABEL_COLUMN = util.LABEL_COLUMN

percent_test = 20
n = (df_all.size * percent_test)/100
df_train = df_all.head(df_all.size - n)
df_test = df_all.tail(n)

itemtype_hash = {}
item_type_count = 0

def hash_type(x):
    global itemtype_hash
    global item_type_count
    if x not in itemtype_hash:
        itemtype_hash[x] = item_type_count
        item_type_count += 1
    return itemtype_hash[x]

df_train['itemType'] = (df_train['itemType'].apply(hash_type)).astype(float)
train_x = df_train.ix[:, df_train.columns != LABEL_COLUMN].as_matrix().astype(float)
train_y = df_train.as_matrix([LABEL_COLUMN])

df_test['itemType'] = (df_test['itemType'].apply(hash_type)).astype(float)
test_x = df_test.ix[:, df_test.columns != LABEL_COLUMN].as_matrix().astype(float)
test_y = df_test.as_matrix([LABEL_COLUMN])

'''for j in range(10):
    print('ITEM %d ==================' % j)
    for i in range(len(df_test.columns)):
        thing = df_test.iloc[j][i]
        if type(thing) == unicode or not np.isnan(thing):
            print(df_test.columns[i], thing)'''

deep_columns = tf.contrib.learn.infer_real_valued_columns_from_input(train_x)

model_dir = 'model'
model = DNNRegressor(model_dir=model_dir, feature_columns=deep_columns, hidden_units=[400, 300, 200, 100, 50],
                     activation_fn=tf.nn.sigmoid, enable_centered_bias=True)

for i in range(50):
    model.fit(train_x, train_y, steps=1000, batch_size=1000)
    results = model.evaluate(test_x, test_y, steps=1, batch_size=df_test.size)

'''def pred_fn():
    return input_fn(df_test[:10])

print(model.predict(input_fn=pred_fn))'''
