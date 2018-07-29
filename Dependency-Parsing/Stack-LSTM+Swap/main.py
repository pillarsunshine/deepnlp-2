import argparse
import tensorflow as tf
import os

import data_loader
from model import Model
from utils import Config


def run(mode):
    model = Model(model_dir=Config.train.model_dir,
                  log_step_count_steps=100,
                  save_checkpoints_steps=Config.train.save_checkpoints_steps)

    if mode == 'train':

        train_data = data_loader.get_tfrecord('train')
        val_data = data_loader.get_tfrecord('test')
        train_input_fn = data_loader.get_train_batch(train_data, buffer_size=5000,
                                                     batch_size=Config.train.batch_size)
        val_input_fn = data_loader.get_eval_batch(val_data, batch_size=32)

        while True:
            print('*' * 40)
            print("epoch", Config.train.epoch + 1, 'start')
            print('*' * 40)

            model.train(train_input_fn)
            model.evaluate(val_input_fn)

            Config.train.epoch += 1
            if Config.train.epoch == Config.train.max_epoch:
                break

    elif mode == 'eval':
        val_data = data_loader.get_tfrecord('test')
        val_input_fn = data_loader.get_eval_batch(val_data, batch_size=32)
        model.evaluate(val_input_fn)


def main(mode):
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    tf.enable_eager_execution(config)
    run(mode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mode', type=str, default='train', choices=['train', 'eval'],
                        help='Mode (train)')
    parser.add_argument('--config', type=str, default='config/stack-lstm+swap.yml', help='config file name')

    args = parser.parse_args()

    tf.logging.set_verbosity(tf.logging.INFO)

    Config(args.config)
    Config.train.model_dir = os.path.expanduser(Config.train.model_dir)
    Config.data.processed_path = os.path.expanduser(Config.data.processed_path)

    print(Config)
    if Config.get("description", None):
        print("Config Description")
        for key, value in Config.description.items():
            print(f" - {key}: {value}")

    main(args.mode)
