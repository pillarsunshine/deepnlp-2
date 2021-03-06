import argparse
import tensorflow as tf
from tensorflow.python import debug as tf_debug

import data_loader
from model import Model
from utils import Config


def run(mode, run_config, params):
    model = Model()
    estimator = tf.estimator.Estimator(
        model_fn=model.model_fn,
        model_dir=Config.train.model_dir,
        params=params,
        config=run_config)

    if Config.train.debug:
        debug_hooks = tf_debug.LocalCLIDebugHook()
        hooks = [debug_hooks]
    else:
        hooks = []

    loss_hooks = tf.train.LoggingTensorHook({'total_loss': 'loss/total_loss',
                                             'step': 'global_step'},
                                            every_n_iter=Config.train.check_hook_n_iter)

    if mode == 'train':
        train_data = data_loader.get_tfrecord('train')
        train_input_fn, train_input_hook = data_loader.get_dataset_batch(train_data, buffer_size=10000,
                                                                         batch_size=Config.train.batch_size,
                                                                         scope="train")
        hooks.extend([train_input_hook, loss_hooks])
        estimator.train(input_fn=train_input_fn, hooks=hooks)

    elif mode == 'train_and_val':
        train_data, val_data = data_loader.get_tfrecord('train'), data_loader.get_tfrecord('val')
        train_input_fn, train_input_hook = data_loader.get_dataset_batch(train_data, buffer_size=10000,
                                                                         batch_size=Config.train.batch_size,
                                                                         scope="val")
        val_input_fn, val_input_hook = data_loader.get_dataset_batch(val_data, batch_size=Config.train.batch_size,
                                                                     scope="val")
        hooks.extend([train_input_hook, loss_hooks])
        for n in range(Config.train.epoch):
            estimator.train(input_fn=train_input_fn, hooks=hooks)
            estimator.evaluate(input_fn=val_input_fn, hooks=[val_input_hook])

    elif mode == 'eval':
        test_data = data_loader.get_tfrecord('val')
        test_input_fn, test_input_hook = data_loader.get_dataset_batch(test_data, batch_size=Config.train.batch_size,
                                                                       scope="eval")
        hooks.extend([test_input_hook])
        estimator.evaluate(input_fn=test_input_fn, hooks=hooks)


def main(mode):
    params = tf.contrib.training.HParams(**Config.train.to_dict())

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    run_config = tf.estimator.RunConfig(
        model_dir=Config.train.model_dir,
        session_config=config,
        save_checkpoints_steps=Config.train.save_checkpoints_steps,
        log_step_count_steps=None)

    run(mode, run_config, params)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mode', type=str, default='train', choices=['train', 'train_and_val', 'eval'],
                        help='Mode (train)')
    parser.add_argument('--config', type=str, default='config/mlp-parser.yml', help='config file name')

    args = parser.parse_args()

    tf.logging.set_verbosity(tf.logging.INFO)

    Config(args.config)
    print(Config)
    if Config.get("description", None):
        print("Config Description")
        for key, value in Config.description.items():
            print(f" - {key}: {value}")

    main(args.mode)
