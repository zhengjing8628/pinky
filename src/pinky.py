import logging
import os
import sys

from pyrocko import guts
from .model import Model

logger = logging.getLogger('pinky')


def main():
    import argparse

    parser = argparse.ArgumentParser(
                description='')
    parser.add_argument('--config')
    parser.add_argument('--configs',
            help='load a comma separated list of configs and process them')
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--evaluate', action='store_true',
            help='Predict from input of `evaluation_data_generator` in config.')
    parser.add_argument('--predict', action='store_true',
            help='Predict from input of `predict_data_generator` in config.')
    parser.add_argument('--optimize', metavar='FILENAME',
            help='use optimizer defined in FILENAME')
    parser.add_argument('--write-tfrecord', metavar='FILENAME',
        help='write data_generator out to FILENAME')
    parser.add_argument('--from-tfrecord', metavar='FILENAME',
        help='read tfrecord')
    parser.add_argument('--new-config')
    parser.add_argument('--clear', help='delete remaints of former runs',
            action='store_true')
    parser.add_argument('--show-data', type=int, default=9, nargs='?',
        help='call with `--debug` to get plot figures with additional information.')
    parser.add_argument('--nskip', type=int,
        help='For plotting. Examples to skip.')
    parser.add_argument('--ngpu', help='number of GPUs to use')
    parser.add_argument('--gpu-no', help='GPU number to use', type=int)
    parser.add_argument('--debug', help='enable logging level DEBUG', action='store_true')
    parser.add_argument('--tfdebug', help='break into tensorflow debugger', action='store_true')
    parser.add_argument('--force', action='store_true')

    args = parser.parse_args()

    if (args.predict or args.evaluate) and args.clear:
        sys.exit('\nCannot `--clear` when running `--predict` or `--evaluate`')

    if args.debug:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logging.debug('Debug level active')
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
        logger.setLevel(logging.INFO)

    # tf_config = tf.ConfigProto()
    # tf_config.gpu_options.allow_growth = True
    # if args.gpu_no:
    #     tf_config.device_count = {'GPU': args.gpu_no}

    configs = []
    if args.config:
        configs = [args.config]

    if args.configs:
        import glob
        a = args.configs.split(',')
        for ai in a:
            configs.extend(glob.glob(ai))
        # configs.extend(args.configs.split(','))

    for iconfig, config in enumerate(configs):
        model = guts.load(filename=config)
        logger.info('Start processing model: %s (%i / %i)' % (
            model.name, iconfig+1, len(configs)))

        model.config.setup()

        if args.tfdebug:
            model.enable_debugger()

        if args.clear:
            model.clear()
        # model.set_tfconfig(tf_config)

        if args.show_data:
            from . import plot
            import matplotlib.pyplot as plt
            nskip = args.nskip or 0
            plot.show_data(model, n=args.show_data, nskip=nskip, shuffle=False)
            plt.show()

        elif args.write_tfrecord:
            if len(models) != 1:
                sys.exit('can only process one model at a time')

            model = models[0]
            model_id = args.write_tfrecord

            if os.path.isfile(args.write_tfrecord):
                if args.force:
                    delete_candidate = guts.load(filename=args.write_tfrecord)
                    for g in [delete_candidate.config.evaluation_data_generator,
                            delete_candidate.config.data_generator]:
                        g.cleanup()
                    delete_if_exists(args.write_tfrecord)
                else:
                    print('file %s exists. use --force to overwrite' % \
                            args.write_tfrecord)
                    sys.exit(0)

            fn_tfrecord = '%s_train.tfrecord' % str(model_id)
            tfrecord_data_generator = DataGeneratorBase(
                    fn_tfrecord=fn_tfrecord, config=model.config)
            model.config.data_generator.write(fn_tfrecord)
            model.config.data_generator = tfrecord_data_generator

            fn_tfrecord = '%s_eval.tfrecord' % str(model_id)
            tfrecord_data_generator = DataGeneratorBase(
                    fn_tfrecord=fn_tfrecord, config=model.config)

            model.config.evaluation_data_generator.write(fn_tfrecord)
            model.config.evaluation_data_generator = tfrecord_data_generator

            model.name += '_tf'
            model.dump(filename=args.write_tfrecord + '.config')
            logger.info('Wrote new model file: %s' % (
                args.write_tfrecord + '.config'))

        elif args.from_tfrecord:
            logger.info('Reading data from %s' % args.from_tfrecord)
            model.config.data_generator = TFRecordData(
                    fn_tfrecord=args.from_tfrecord)

        elif args.new_config:
            fn_config = args.new_config
            if os.path.exists(fn_config):
                print('file exists: %s' % fn_config)
                sys.exit()

            model = Model(
                tf_config=tf_config,
                data_generator=GFSwarmData.get_example())

            model.regularize()

        if args.train and args.optimize:
            print('Can only use either --train or --optimize')
            sys.exit()

        if args.train:
            if args.ngpu:
                logger.info('Using %s GPUs' % args.ngpu)
                model.train_multi_gpu()
            else:
                model.train_and_evaluate()
                # model.train()
        elif args.evaluate:
            model.evaluate()

        elif args.predict:
            model.predict()

        elif args.optimize:
            hyper_optimizer = guts.load(filename=args.optimize)
            if args.clear:
                hyper_optimizer.clear()
            hyper_optimizer.optimize(model)
