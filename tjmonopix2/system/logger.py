import logging

import coloredlogs

FORMAT = '%(asctime)s [%(name)-17s] - %(levelname)-7s %(message)s'


def setup_main_logger(name='TJ-Monopix2', level=logging.INFO):
    _reset_all_loggers()
    _set_basil_logger_to(logging.WARNING)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    _setup_coloredlogs(logger)
    _add_success_level(logger)
    _add_notice_level(logger)

    _add_logfiles_to(logger)

    return logger


def setup_derived_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    _setup_coloredlogs(logger)
    _add_success_level(logger)
    _add_notice_level(logger)

    _add_logfiles_to(logger)

    return logger


def setup_logfile(filename, level=logging.INFO):
    fh = logging.FileHandler(filename)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(FORMAT))

    return fh


def add_logfile_to_loggers(fh):
    # Add filehandler to all active loggers
    for lg in logging.Logger.manager.loggerDict.values():
        if isinstance(lg, logging.Logger):
            lg.addHandler(fh)


def _add_logfiles_to(logger):
    fhs = []
    for lg in logging.Logger.manager.loggerDict.values():
        if isinstance(lg, logging.Logger):
            for handler in lg.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    fhs.append(handler)

    for fh in fhs:
        logger.addHandler(fh)


def close_logfile(fh):
    # Remove filehandler from all active loggers
    for lg in logging.Logger.manager.loggerDict.values():
        if isinstance(lg, logging.Logger):
            lg.removeHandler(fh)
            # fh.close()


def _setup_coloredlogs(logger):
    loglevel = logger.getEffectiveLevel()
    coloredlogs.DEFAULT_FIELD_STYLES = {'asctime': {},
                                        'hostname': {},
                                        'levelname': {'bold': True},
                                        'name': {},
                                        'programname': {}}
    coloredlogs.DEFAULT_LEVEL_STYLES = {'critical': {'color': 'red', 'bold': True},
                                        'debug': {'color': 'magenta'},
                                        'error': {'color': 'red', 'bold': True},
                                        'info': {},
                                        'success': {'color': 'green'},
                                        'notice': {'color': 'blue'},
                                        'warning': {'color': 'yellow'}}
    coloredlogs.DEFAULT_LOG_LEVEL = loglevel

    coloredlogs.install(fmt=FORMAT, milliseconds=True, loglevel=loglevel)


def _add_success_level(logger):
    logging.SUCCESS = 35
    logging.addLevelName(logging.SUCCESS, 'SUCCESS')
    logger.success = lambda msg, *args, **kwargs: logger.log(logging.SUCCESS, msg, *args, **kwargs)


def _add_notice_level(logger):
    logging.NOTICE = 25
    logging.addLevelName(logging.NOTICE, 'NOTICE')
    logger.notice = lambda msg, *args, **kwargs: logger.log(logging.NOTICE, msg, *args, **kwargs)


def _set_basil_logger_to(level=logging.INFO):
    logging.getLogger('basil.HL.RegisterHardwareLayer').setLevel(level)


def _reset_all_loggers():
    logging.root.handlers = []
