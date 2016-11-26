import json
import time
import BaseHTTPServer
import pandas as pd
import tensorflow as tf
import numpy as np
from tensorflow.contrib.learn import DNNClassifier
import util
tf.logging.set_verbosity(tf.logging.INFO)

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
            row = util.item_to_row(util.format_item(item))
            for col in row:
                val = row.pop(col)
                row[util.format_column_name(col)] = val
            if util.LABEL_COLUMN in row:
                row.pop(util.LABEL_COLUMN)
            row['itemType'] = util.type_hash[row['itemType']]
            df = df.append(row, ignore_index=True)

        df.fillna(0.0, inplace=True)
        inputs = df.as_matrix().astype(float)
        predictions = model.predict(inputs, batch_size=len(df))
        p = []
        for pred in predictions:
            p.append(util.get_bin_label(pred))

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(p))

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
