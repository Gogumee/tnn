import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data
from tnn import main
from tnn.convrnn import tnn_ConvBasicCell
import numpy as np

'''This is an example of passing a custom cell to your model,
in this case a vanilla convRNN implemented from scratch,
which can serve as a template for more complex custom cells'''

batch_size = 256 # batch size for training
NUM_NEURONS = 200 # number of neurons we are predicting
NUM_TIMESTEPS = 4 # number of timesteps we are predicting on
NETWORK_DEPTH = 3 # number of total layers in our network

# we always unroll num_timesteps after the first output of the model
TOTAL_TIMESTEPS = NETWORK_DEPTH + NUM_TIMESTEPS 

# we unroll at least NETWORK_DEPTH times (3 in this case) so that the input can reach the output of the network
# note tau is the value of the memory decay (by default 0) at the readout layer and trainable_flag is whether the memory decay is trainable, which by default is False

def model_func(input_images, ntimes=TOTAL_TIMESTEPS, 
    batch_size=batch_size, edges_arr=[], 
    base_name='json/VanillaRNN', 
    tau=0.0, trainable_flag=False):

    with tf.variable_scope("my_model"):
        # reshape the 784 dimension MNIST digits to be 28x28 images
        input_images = tf.reshape(input_images, [-1, 28, 28, 1])
        base_name += '.json'
        print('Using base: ', base_name)
        # creates the feedforward network graph from json
        G = main.graph_from_json(base_name)

        for node, attr in G.nodes(data=True):
            memory_func, memory_param = attr['kwargs']['memory']
            if 'filter_size' in memory_param:
                attr['cell'] = tnn_ConvBasicCell
            else:
                # default to not having a memory cell
                # tau = 0.0, trainable = False
                attr['kwargs']['memory'][1]['memory_decay'] = tau
                attr['kwargs']['memory'][1]['trainable'] = trainable_flag

        # add any non feedforward connections here: e.g. [('L2', 'L1')]
        G.add_edges_from(edges_arr)

        # initialize network to infer the shapes of all the parameters
        main.init_nodes(G, input_nodes=['L1'], batch_size=batch_size)
        # unroll the network through time
        main.unroll(G, input_seq={'L1': input_images}, ntimes=ntimes)

        outputs = {}
        # start from the final output of the model and 4 timesteps beyond that
        for t in range(ntimes-NUM_TIMESTEPS, ntimes):
            idx = t - (ntimes - NUM_TIMESTEPS) # keys start at timepoint 0
            outputs[idx] = G.node['readout']['outputs'][t]

        return outputs

# get MNIST images
mnist = input_data.read_data_sets('/mnt/fs0/datasets/', one_hot=True)

# create the model
x = tf.placeholder(tf.float32, [batch_size, 784])

y_ = tf.placeholder(tf.float32, [batch_size, NUM_NEURONS, NUM_TIMESTEPS]) # predicting 168 neurons at 4 timepoints

outputs = model_func(x, ntimes=TOTAL_TIMESTEPS, 
    batch_size=batch_size, edges_arr=[], 
    base_name='json/VanillaRNN', tau=0.0, trainable_flag=False)

# setup the loss (average across time, the l2 loss at each timepoint 
# between model predictions and neuron responses)
with tf.name_scope('cumulative_loss'):
    print(outputs)
    labels_arr = [tf.squeeze(tf.slice(y_, [0, 0, i], [-1, -1, 1])) \
                 for i in range(len(outputs))]
    outputs_arr = [tf.squeeze(outputs[i]) for i in range(len(outputs))]
    cumm_loss = tf.add_n([tf.nn.l2_loss(outputs_arr[i] - labels_arr[i]) \
        for i in range(len(outputs))]) / len(outputs)

# setup the optimizer
with tf.name_scope('adam_optimizer'):
    train_step = tf.train.AdamOptimizer(1e-4).minimize(cumm_loss)

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    for i in range(20000):
        batch = mnist.train.next_batch(batch_size)
        labels_batch = np.random.randn(batch_size, NUM_NEURONS, NUM_TIMESTEPS) # random noise
        if i % 100 == 0:
            train_loss = cumm_loss.eval(feed_dict={x: batch[0], y_: labels_batch})
            print('step %d, training loss %g' % (i, train_loss))
        train_step.run(feed_dict={x: batch[0], y_: labels_batch})

