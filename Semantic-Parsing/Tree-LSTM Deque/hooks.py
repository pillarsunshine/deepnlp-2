import numpy as np
import tensorflow as tf
import os

from utils import Config
from data_loader import Token, Sentence, ArcEagerParser


class EvalHook(tf.train.SessionRunHook):
    def __init__(self, model_dir=None):
        # self.total = 0
        self.head_tp = 0
        self.dep_tp = 0
        self.pred_num = 0
        self.gold_num = 0
        self.parser = ArcEagerParser()
        if model_dir:
            self.model_dir = os.path.join(Config.train.model_dir, 'eval_' + model_dir)
        else:
            self.model_dir = os.path.join(Config.train.model_dir, 'eval')

    def begin(self):
        self._summary_writer = tf.summary.FileWriter(self.model_dir)

    def before_run(self, run_context):

        return tf.train.SessionRunArgs(
            ['next_batch:0', 'next_batch:1', 'next_batch:4', 'next_batch:2', 'next_batch:3'])

    def after_run(self, run_context, run_values):
        word, pos, length, head, dep_id = run_values.results
        batch_size = word.shape[0]

        total_sen = [Sentence([Token(n + 1, word[i][n].decode(), pos[i][n].decode(), [], []) for
                               n in range(length[i])]) for i in range(batch_size)]

        while True:
            batch_tree_word_id, batch_tree_pos_id, batch_token_word_id, batch_token_pos_id, batch_history_action_id, \
            batch_buff_top_id, batch_deque_word_id, batch_deque_pos_id, batch_deque_length, batch_children_order, \
            batch_stack_order, batch_stack_length, batch_token_length, batch_history_action_length = \
                [], [], [], [], [], [], [], [], [], [], [], [], [], []

            max_children_num = []  # for padding
            for sen in total_sen:
                if not sen.terminate:
                    tree_word_id, tree_pos_id, token_word_id, token_pos_id, buff_top_id, history_action_id, \
                    deque_word_id, deque_pos_id, children_order, stack_order = self.parser.extract_from_current_state(sen)

                    batch_tree_word_id.append(tree_word_id)
                    batch_tree_pos_id.append(tree_pos_id)
                    batch_token_word_id.append(token_word_id)
                    batch_token_pos_id.append(token_pos_id)
                    batch_history_action_id.append(history_action_id)
                    batch_buff_top_id.append(buff_top_id)
                    batch_deque_word_id.append(deque_word_id)
                    batch_deque_pos_id.append(deque_pos_id)
                    batch_deque_length.append(len(deque_word_id))
                    batch_children_order.append(children_order)
                    batch_stack_order.append(stack_order)
                    batch_stack_length.append(len(stack_order))
                    batch_token_length.append(len(batch_token_word_id))
                    batch_history_action_length.append(len(history_action_id))
                    max_children_num.append(max([len(n) for n in children_order]))

            batch_tree_word_id = tf.keras.preprocessing.sequence.pad_sequences(batch_tree_word_id,
                                                                               dtype='int64', padding='post')
            batch_tree_pos_id = tf.keras.preprocessing.sequence.pad_sequences(batch_tree_pos_id,
                                                                              dtype='int64', padding='post')
            batch_token_word_id = tf.keras.preprocessing.sequence.pad_sequences(batch_token_word_id,
                                                                               dtype='int64', padding='post')
            batch_token_pos_id = tf.keras.preprocessing.sequence.pad_sequences(batch_token_pos_id,
                                                                              dtype='int64', padding='post')
            batch_history_action_id = tf.keras.preprocessing.sequence.pad_sequences(batch_history_action_id,
                                                                                    dtype='int64', padding='post')
            batch_deque_word_id = tf.keras.preprocessing.sequence.pad_sequences(batch_deque_word_id,
                                                                                  dtype='int64', padding='post')
            batch_deque_pos_id = tf.keras.preprocessing.sequence.pad_sequences(batch_deque_pos_id,
                                                                                 dtype='int64', padding='post')
            batch_stack_order = tf.keras.preprocessing.sequence.pad_sequences(batch_stack_order,
                                                                              dtype='int64', padding='post')

            # pad children order
            max_children_num = max(max_children_num)
            max_stack_len = batch_tree_word_id.shape[1]
            for n, c in enumerate(batch_children_order):
                [i.extend([0] * (max_children_num - len(i))) for i in c]
                batch_children_order[n] = batch_children_order[n] + [[0] * max_children_num] * (max_stack_len - len(c))

            feed_dict = {'tree_word_id:0': batch_tree_word_id, 'tree_pos_id:0': batch_tree_pos_id,
                         'token_word_id:0': batch_token_word_id, 'token_pos_id:0': batch_token_pos_id,
                         'history_action_id:0': batch_history_action_id, 'deque_word_id:0': batch_deque_word_id,
                         'deque_pos_id:0': batch_deque_pos_id, 'buff_top_id:0': batch_buff_top_id,
                         'deque_length:0': batch_deque_length, 'children_order:0':batch_children_order,
                         'stack_order:0': batch_stack_order,'stack_length:0': batch_stack_length,
                         'token_length:0': batch_token_length,'history_action_length:0': batch_history_action_length}

            prob = run_context.session.run("Softmax:0", feed_dict)

            idx = 0
            for sen in total_sen:
                if not sen.terminate:
                    legal_transitions = self.parser.get_legal_transitions(sen)
                    transition = np.argmax(np.array(legal_transitions) * prob[idx])
                    if transition not in [0, 1, 2, 3]:
                        self.parser.update_tree(sen, transition)  # update composition
                    self.parser.update_state_by_transition(sen, transition)  # update stack and buff
                    idx += 1
                    if self.parser.terminal(sen):
                        sen.terminate = True
            if [sen.terminate for sen in total_sen] == [True] * batch_size:
                exit()
                for i, sen in enumerate(total_sen):
                    for gold_head,gold_dep,pred in zip(head[i,:length[i]],dep_id[i,:length[i]],sen.tokens):
                        for j,head in enumerate(gold_head):
                            if head == -1:
                                continue
                            else:
                                if head in pred.pred_head_id:
                                    self.head_tp += 1
                                    if gold_dep[j] == pred.pred_dep_id[pred.pred_head_id.index(head)]:
                                        self.dep_tp += 1
                                    pred.pred_head_id.pop(pred.pred_head_id.index(head))
                                    self.pred_num += 1
                                self.gold_num += 1
                        self.pred_num += len(pred.pred_head_id)

                break

    def end(self, session):

        global_step = session.run(tf.train.get_global_step())
        summary_op = tf.get_default_graph().get_collection('f_score')

        up = self.head_tp / self.pred_num
        ur = self.head_tp/ self.gold_num
        uf = 2 * up * ur / (up + ur)

        lf = self.dep_tp /self.pred_num
        lr = self.dep_tp / self.gold_num
        lf = 2 * lf * lr / (lf + lr)

        summary = session.run(summary_op, {'uf_ph:0': uf,
                                           'lf_ph:0': lf})
        for s in summary:
            self._summary_writer.add_summary(s, global_step)

        self._summary_writer.flush()

        print('*' * 40)
        print("epoch", Config.train.epoch + 1, 'finished')
        print('UF:', uf, '    LF:', lf)
        print('*' * 40)
