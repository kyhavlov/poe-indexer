import os
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNClassifier
import util
tf.logging.set_verbosity(tf.logging.INFO)

def train_model(item_type):
    model_dir = "models/" + item_type.lower().replace(" ", "_")
    if os.path.exists(model_dir):
        return
    print("==> Training model for '%s'" % item_type)
    csv_filename = filename = "data/" + item_type.lower().replace(" ", "_") + ".csv"
    df_all = pd.read_csv(csv_filename, skipinitialspace=True, encoding='utf-8')
    df_all.fillna(0.0, inplace=True)

    # Convert the price to a bucket representing a range
    df_all['price_chaos'] = (df_all['price_chaos'].apply(util.price_bucket)).astype(int)

    # Hash the item type to a number
    df_all['itemType'] = (df_all['itemType'].apply(lambda x: util.type_hash[x])).astype(float)

    LABEL_COLUMN = util.LABEL_COLUMN

    # Split the data 80/20 training/test
    percent_test = 20
    n = (len(df_all) * percent_test)/100
    df_train = df_all.head(len(df_all) - n)
    df_test = df_all.tail(n)

    train_x = df_train.ix[:, df_train.columns != LABEL_COLUMN].as_matrix().astype(float)
    train_y = df_train.as_matrix([LABEL_COLUMN])
    test_x = df_test.ix[:, df_test.columns != LABEL_COLUMN].as_matrix().astype(float)
    test_y = df_test.as_matrix([LABEL_COLUMN])

    deep_columns = tf.contrib.learn.infer_real_valued_columns_from_input(train_x)
    hidden_units = util.get_hidden_units(len(df_train.columns)-1)
    model = DNNClassifier(model_dir=model_dir, feature_columns=deep_columns, hidden_units=hidden_units,
                          n_classes=len(util.bins), enable_centered_bias=True)

    steps = len(df_train)/75
    sessions = (steps/500)+2
    for i in range(sessions):
        model.fit(train_x, train_y, steps=500, batch_size=5000)
        results = model.evaluate(test_x, test_y, steps=1, batch_size=df_test.size)

    # Print some predictions from the test data
    predictions = df_test.sample(10)
    v = model.predict_proba(predictions.ix[:, df_test.columns != LABEL_COLUMN].as_matrix().astype(float), batch_size=10)

    price_map = []

    for i in v:
        # take the top 5 most likely price ranges
        top_largest = i.argsort()[-5:][::-1]
        prices = {}
        for p in top_largest:
            prices[util.get_bin_label(p)] = float(round(100*i[p], 1))
        price_map.append(prices)

    for r in price_map:
        print r

for item_type in util.all_bases:
    train_model(item_type)
