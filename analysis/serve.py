import json
import time
import BaseHTTPServer
import pandas as pd
import tensorflow as tf
from tensorflow.contrib.learn import DNNClassifier
import util
tf.logging.set_verbosity(tf.logging.ERROR)

df_all = pd.read_csv(util.TRAIN_FILE, skipinitialspace=True, nrows=0, encoding='utf-8')
df_all = df_all.ix[:, df_all.columns != util.LABEL_COLUMN]
df_all['itemType'] = (df_all['itemType'].apply(lambda x: util.type_hash[x])).astype(float)

HOST_NAME = '127.0.0.1'
PORT_NUMBER = 8080

train_x = df_all.as_matrix().astype(float)
deep_columns = tf.contrib.learn.infer_real_valued_columns_from_input(train_x)

model_dir = 'model'
model = DNNClassifier(model_dir=model_dir, feature_columns=deep_columns, hidden_units=util.HIDDEN_UNITS,
                      n_classes=len(util.bins), enable_centered_bias=True)


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

        df = df_all.copy()

        for item in parsed_json:
            print(item)
            util.format_item(item)
            print(item)
            row = util.item_to_row(item)
            for col in row:
                val = row.pop(col)
                row[util.format_column_name(col)] = val
            if util.LABEL_COLUMN in row:
                row.pop(util.LABEL_COLUMN)
            row['itemType'] = util.type_hash[row['itemType']]
            print(row)
            df = df.append(row, ignore_index=True)

        df.fillna(0.0, inplace=True)
        inputs = df.as_matrix().astype(float)
        predictions = model.predict_proba(inputs, batch_size=len(df))
        price_map = []
        for i in predictions:
            # take the top 5 most likely price ranges
            top_largest = i.argsort()[-5:][::-1]
            prices = {'estimate': util.get_price_estimate(i)}
            for p in top_largest:
                prices[util.get_bin_label(p)] = float(round(100*i[p], 2))
            price_map.append(prices)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
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
