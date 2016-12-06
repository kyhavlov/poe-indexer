import json
import time
import BaseHTTPServer
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNClassifier
import util
tf.logging.set_verbosity(tf.logging.ERROR)

column_set = {}
model = {}

df_weapons = pd.read_csv("weapons.csv", skipinitialspace=True, nrows=0, encoding='utf-8')
df_weapons = df_weapons.ix[:, df_weapons.columns != util.LABEL_COLUMN]
df_weapons['itemType'] = (df_weapons['itemType'].apply(lambda x: util.type_hash[x])).astype(float)
column_set['weapons'] = set(df_weapons.columns)
weapons_x = df_weapons.as_matrix().astype(float)
deep_columns_weapons = tf.contrib.learn.infer_real_valued_columns_from_input(weapons_x)

model['weapons'] = DNNClassifier(model_dir='model_weapons', feature_columns=deep_columns_weapons, hidden_units=util.HIDDEN_UNITS,
                      n_classes=len(util.bins), enable_centered_bias=True)

df_armor = pd.read_csv("armor.csv", skipinitialspace=True, nrows=0, encoding='utf-8')
df_armor = df_armor.ix[:, df_armor.columns != util.LABEL_COLUMN]
df_armor['itemType'] = (df_armor['itemType'].apply(lambda x: util.type_hash[x])).astype(float)
column_set['armor'] = set(df_armor.columns)
armor_x = df_armor.as_matrix().astype(float)
deep_columns_armor = tf.contrib.learn.infer_real_valued_columns_from_input(armor_x)

model['armor'] = DNNClassifier(model_dir='model_armor', feature_columns=deep_columns_armor, hidden_units=util.HIDDEN_UNITS,
                      n_classes=len(util.bins), enable_centered_bias=True)

HOST_NAME = '0.0.0.0'
PORT_NUMBER = 8080

class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    def do_POST(self):
        if self.path != '/price':
            self.send_response(401)
            return

        raw_json = self.rfile.read(int(self.headers.getheader('content-length')))
        parsed_json = json.loads(raw_json)
        df = {}
        df["weapons"] = df_weapons.copy()
        df["armor"] = df_armor.copy()

        for item in parsed_json:
            util.format_item(item)
            row = util.item_to_row(item)

            if row['itemType'] in util.weapons:
                item_class = "weapons"
            else:
                item_class = "armor"

            print(item_class)
            print(row)

            if util.LABEL_COLUMN in row:
                row.pop(util.LABEL_COLUMN)
            row['itemType'] = util.type_hash[row['itemType']]

            ignored = []
            for col in row:
                if col not in column_set[item_class]:
                    ignored.append(col)
            for col in ignored:
                row.pop(col)
            print('Ignored mods: ', ignored)

            df[item_class] = df[item_class].append(row, ignore_index=True)

        print(len(df["weapons"]))
        print(len(df["armor"]))

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        for frame in df:
            if len(df[frame]) == 0:
                continue
            df[frame].fillna(0.0, inplace=True)

            inputs = df[frame].as_matrix().astype(float)
            predictions = model[frame].predict_proba(inputs, batch_size=len(df))
            price_map = []
            for i in predictions:
                # take the top 5 most likely price ranges
                top_largest = i.argsort()[-5:][::-1]
                prices = {'estimate': util.get_price_estimate(i)}
                for p in top_largest:
                    prices[util.get_bin_label(p)] = float(round(100*i[p], 2))
                price_map.append(prices)
            self.wfile.write(json.dumps(price_map))

if __name__ == '__main__':
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), Handler)
    print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER)
