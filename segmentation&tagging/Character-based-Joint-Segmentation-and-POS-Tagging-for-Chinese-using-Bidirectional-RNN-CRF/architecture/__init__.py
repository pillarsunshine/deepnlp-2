from utils import Config
import tensorflow as tf
from tensorflow.contrib import slim

from data_loader import read_pretrained_wordvec

class Graph:
    def __init__(self, mode):
        self.mode = mode
        if mode == tf.estimator.ModeKeys.TRAIN:
            self.is_training = True
        else:
            self.is_training = False

    def build(self, inputs):
        id = inputs['id']
        length = inputs['length']
        embeddings = self.embedding(id)
        logits = self.build_gru(embeddings,length)
        return logits

    def embedding(self,inputs):
        _, wordvec = read_pretrained_wordvec(Config.data.wordvec_fname)
        embedding = tf.get_variable('embedding', [wordvec.shape[0], wordvec.shape[1]],
                                    initializer=tf.constant_initializer(wordvec, tf.float32), trainable=False)
        output = tf.nn.embedding_lookup(embedding, inputs)
        return output

    def build_gru(self, inputs,length):

        with tf.variable_scope('bilstm'):
            gru_cell_fw = tf.nn.rnn_cell.GRUCell(Config.model.gru_unit,kernel_initializer=tf.orthogonal_initializer)
            gru_cell_bw = tf.nn.rnn_cell.GRUCell(Config.model.gru_unit,kernel_initializer=tf.orthogonal_initializer)
            gru_outputs, output_states = tf.nn.bidirectional_dynamic_rnn(gru_cell_fw, gru_cell_bw, inputs,length,
                                                                          dtype=tf.float32)
            gru_outputs = tf.concat(gru_outputs, axis=-1)
            gru_outputs = slim.dropout(gru_outputs, Config.model.dropout_keep_prob, is_training=self.is_training)
            outputs = slim.fully_connected(gru_outputs,Config.model.fc_unit,activation_fn=None)
            return outputs
