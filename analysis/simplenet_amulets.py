import numpy as np
import tensorflow as tf
import util

# from tensorflow.examples.tutorials.mnist import input_data
# mnist = input_data.read_data_sets('MNIST_data', one_hot=True)

items = np.genfromtxt('amulets.csv')
labels = np.genfromtxt('amulet_classes.csv', dtype=int)
one_hot = np.eye(len(util.PRICE_BUCKETS))[labels]
tsplit = 0.6
amulets = util.DataSet(items, one_hot, train_split=tsplit)

num_vars = items.shape[1]
num_price_buckets = len(one_hot[1])

sess = tf.InteractiveSession()

x = tf.placeholder(tf.float32, shape=[None, num_vars])
y_ = tf.placeholder(tf.float32, shape=[None, num_price_buckets])

W = tf.Variable(tf.zeros([num_vars, num_price_buckets]))
b = tf.Variable(tf.zeros([num_price_buckets]))

sess.run(tf.global_variables_initializer())

y = tf.matmul(x, W) + b

cross_entropy = tf.reduce_mean(
    tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y))

train_step = tf.train.GradientDescentOptimizer(0.5).minimize(cross_entropy)

for _ in range(1000):
    batch = amulets.next_batch(100)
    train_step.run(feed_dict={x: batch[0], y_: batch[1]})

correct_prediction = tf.equal(tf.argmax(y, 1), tf.argmax(y_, 1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

print(accuracy.eval(feed_dict={x: amulets.valid_data, y_: amulets.valid_labels}))
