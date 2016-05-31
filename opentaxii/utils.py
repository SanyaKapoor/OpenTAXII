import sys
import logging
import structlog
import urlparse
import importlib
import base64

from .exceptions import InvalidAuthHeader

log = structlog.getLogger(__name__)


def get_path_and_address(domain, address):
    parsed = urlparse.urlparse(address)

    if parsed.scheme:
        return None, address
    else:
        return address, domain + address


def import_class(module_class_name):
    module_name, _, class_name = module_class_name.rpartition('.')
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def initialize_api(api_config):
    cls = import_class(api_config['class'])
    params = api_config['parameters']

    if params:
        instance = cls(**params)
    else:
        instance = cls()

    log.info("api.initialized", api=cls.__name__)

    return instance


def parse_basic_auth_token(token):
    try:
        value = base64.b64decode(token)
    except TypeError:
        raise InvalidAuthHeader("Can't decode Basic Auth header value")

    try:
        username, password = value.split(':', 1)
        return (username, password)
    except ValueError:
        raise InvalidAuthHeader("Invalid Basic Auth header value")


class PlainRenderer(object):

    def __call__(self, logger, name, event_dict):
        pairs = ', '.join(['%s=%s' % (k, v) for k, v in event_dict.items()])
        return '%(timestamp)s [%(logger)s] %(level)s: %(event)s {%(pairs)s}' \
                % dict(pairs=pairs, **event_dict)


def configure_logging(logging_levels, plain=False):

    _remove_all_existing_log_handlers()

    renderer = PlainRenderer() if plain \
            else structlog.processors.JSONRenderer()

    structlog.configure(
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer
        ],
        context_class = dict,
        logger_factory = structlog.stdlib.LoggerFactory(),
        wrapper_class = structlog.stdlib.BoundLogger,
        cache_logger_on_first_use = True,
    )

    handler = logging.StreamHandler(sys.stdout)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    for logger, level in logging_levels.items():

        if logger.lower() == 'root':
            logger = ''

        logging.getLogger(logger).setLevel(level.upper())


def _remove_all_existing_log_handlers():
    for logger in logging.Logger.manager.loggerDict.values():
        if hasattr(logger, 'handlers'):
            del logger.handlers[:]

    root_logger = logging.getLogger()
    del root_logger.handlers[:]
