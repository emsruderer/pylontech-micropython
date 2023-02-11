"""Slightly adapted code of Eric de Lange"""

import sys
import time
import os

DEFAULT= "Geen bericht, goed bericht"

CRITICAL = const(50)
ERROR = const(40)
WARNING = const(30)
INFO = const(20)
DEBUG = const(10)
NOTSET = const(0)

_level_str = {
    CRITICAL: "CRITICAL",
    ERROR: "ERROR",
    WARNING: "WARNING",
    INFO: "INFO",
    DEBUG: "DEBUG"
}

_stream = sys.stderr  # default output
_filename = None  # overrides stream
_level = INFO  # ignore messages which are less severe
_loggers = dict()


class Logger:
    MAX_FILE_SIZE = 10000
    
    def __init__(self, name, fn = None):
        self.name = name
        self.level = _level
        self.filename = fn

    def log(self, level, message = DEFAULT, **args):
        if level < self.level:
            return

        try:
            if args:
                message = message.format(**args) # message {extra_info}, {"extra_info": "this_info"}

            record = dict()
            record["levelname"] = _level_str.get(level, str(level))
            record["level"] = level
            record["message"] = message
            record["name"] = self.name
            tm = time.localtime()
            record["asctime"] = f"{tm[0]:4}-{tm[1]}-{tm[2]} {tm[3]:2}:{tm[4]:2}:{tm[5]:2}"
 
            log_str = "{name}:{asctime}  {levelname:8}--{message}\n".format(**record)

            if self.filename is None:
                _ = _stream.write(log_str)
            else:
                with open(self.filename, "a") as fp:
                    fp.write(log_str)
                self.check_logfile(self.filename)

        except Exception as e:
            print("--- Logging Error ---")
            print(repr(e))
            print("Message: '" + message + "'")
            print("Arguments:", args)
            #print("Format String: '" + _format + "'")
            raise e

    def setLevel(self, level):
        self.level = level

    def debug(self, message, **args):
        self.log(DEBUG, message, **args)

    def info(self, message, **args):
       self.log(INFO, message, **args)

    def warning(self, message, **args):
        self.log(WARNING, message, **args)

    def error(self, message, *args):
        self.log(ERROR, message, *args)

    def critical(self, message, **args):
        self.log(CRITICAL, message, **args)

    def exception(self, exception, message, **args):
        self.log(ERROR, message, **args)

        if _filename is None:
            sys.print_exception(exception, _stream)
        else:
            with open(_filename, "a") as fp:
                sys.print_exception(exception, fp)
            self.check_logfile(_filename)

    def check_logfile(self,filename, max_filesize=MAX_FILE_SIZE):
        stat = os.stat(filename)
        filesize = stat[6]
        if filesize >= max_filesize:
            backup = filename[0:-3] + 'bak'
            try:
                os.remove(backup)
            except OSError:
                pass
            os.rename(filename, backup)


def getLogger(name="pylontech",filename=None):
    if name not in _loggers:
        _loggers[name] = Logger(name,filename)
    return _loggers[name]


def basicConfig(level=INFO, filename=None, filemode='a', format=None):
    global _filename, _level, _format
    _filename = filename
    _level = level
    if format is not None:
        _format = format

    if filename is not None and filemode != "a":
        with open(filename, "w"):
            pass  # clear log file


def setLevel(level):
    getLogger().setLevel(level)


def debug(message, *args):
    getLogger().debug(message, *args)


def info(message, *args):
    getLogger().info(message, *args)


def warning(message, *args):
    getLogger().warning(message, *args)


def error(message, *args):
    getLogger().error(message, *args)


def critical(message, *args):
    getLogger().critical(message, *args)


def exception(exception, message, *args):
    getLogger().exception(exception, message, *args)


if __name__ == '__main__':
    logger= getLogger('mine')
    logger.critical("this problem is critical")
    logger.error("this is an error")
    logger.warning("a warning message")
    logger.info("message plus {extra_info}", **{"extra_info": "'this_extra_info'"})
    
    try:
        3/0
    except ZeroDivisionError as ex:
        logger.exception(ex, ex.args[0])