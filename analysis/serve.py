import json
import time
import BaseHTTPServer
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNClassifier
import util
import logging
tf.logging.set_verbosity(tf.logging.ERROR)
logging.basicConfig(filename='deals.log',level=logging.DEBUG)

column_set = {}
models = {}
dataframes = {}

for item_type in util.all_bases:
    csv_filename = filename = "data/" + item_type.lower().replace(" ", "_") + ".csv"
    model_dir = "models/" + item_type.lower().replace(" ", "_")
    df = pd.read_csv(csv_filename, skipinitialspace=True, nrows=0, encoding='utf-8')
    df = df.ix[:, df.columns != util.LABEL_COLUMN]
    df['itemType'] = (df['itemType'].apply(lambda x: util.type_hash[x])).astype(float)
    dataframes[item_type] = df
    column_set[item_type] = set(df.columns)
    columns = df.as_matrix().astype(float)
    deep_columns = tf.contrib.learn.infer_real_valued_columns_from_input(columns)
    hidden_units = util.get_hidden_units(len(df.columns))

    models[item_type] = DNNClassifier(model_dir=model_dir, feature_columns=deep_columns, hidden_units=hidden_units,
                          n_classes=len(util.bins), enable_centered_bias=True)


HOST_NAME = '127.0.0.1'
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
        deal_mode = self.headers.getheader('deal-mode')
        parsed_json = json.loads(raw_json)
        df = {}
        listed_prices = {}

        for item in parsed_json:
            item = util.format_item(item)
            if item is None:
                continue
            row = util.item_to_row(item)

            item_class = row['itemType']

            #print(item_class)
            #print(row)

            if util.LABEL_COLUMN in row:
                row.pop(util.LABEL_COLUMN)
            row['itemType'] = util.type_hash[row['itemType']]
            row['day'] = util.get_day(int(time.time()))
            #print(row['day'])

            ignored = []
            for col in row:
                if col not in column_set[item_class]:
                    ignored.append(col)
            for col in ignored:
                row.pop(col)
            #print('Ignored mods: ', ignored)
            if deal_mode is not None:
                row['index'] = item['id']
                listed_prices[item['id']] = item['price_chaos']

            if item_class not in df:
                df[item_class] = dataframes[item_class].copy()
            df[item_class] = df[item_class].append(row, ignore_index=True)

        #print(len(df['Amulet']))
        #print(len(df['Body Armour']))
        #print(listed_prices)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        price_map = []
        for frame in df:
            if len(df[frame]) == 0:
                continue
            df[frame].fillna(0.0, inplace=True)

            inputs = df[frame].ix[:, df[frame].columns != 'index'].as_matrix().astype(float)
            predictions = models[frame].predict_proba(inputs, batch_size=len(df[frame]))
            n = 0
            for i in predictions:
                # take the top 5 most likely price ranges
                top_largest = i.argsort()[-5:][::-1]
                prices = {'estimate': util.get_price_estimate(i)}
                for p in top_largest:
                    prices[util.get_bin_label(p)] = float(round(100*i[p], 2))
                if deal_mode is None:
                    price_map.append(prices)
                else:
                    item_id = df[frame]['index'][n]
                    list_price = listed_prices[item_id]
                    estimated_profit = prices['estimate'] - list_price
                    if estimated_profit >= 15.0 and estimated_profit >= list_price * 1.0:
                        logging.info({item_id: {'listed': list_price, 'estimate': prices['estimate']}})
                    n += 1
        if deal_mode is not None:
            logging.info("Scanned %d items for deals" % len(parsed_json))
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
