#!/usr/bin/python3
# -*- coding: utf-8 -*-

# @file easy_message.py
# @brief
# @author QRS
# @version 1.0
# @date 2022-02-17 21:34


import abc, sys
import threading

from multiprocessing import Queue
from queue import Empty
from enum import IntEnum, unique


class SingletonType(type):
    _instance_lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            with SingletonType._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super(SingletonType,cls).__call__(*args, **kwargs)
        return cls._instance


@unique
class MessageType(IntEnum):
    NOP = -1
    LOG = 1
    STATE = 2
    QUIT = 99


class Message(object):
    def __init__(self, what, arg1, arg2, obj):
        self.what = what
        self.arg1 = arg1
        self.arg2 = arg2
        self.obj = obj

    def __str__(self):
        obj = self.obj[:32] if isinstance(self.obj, str) else self.obj.__class__.__name__
        return f'Message({self.what}, {self.arg1}, {self.arg2}, {obj})'

    @staticmethod
    def obtain(what, arg1, arg2, obj):
        return Message(what, arg1, arg2, obj)


class MessageHandler(metaclass=abc.ABCMeta):
    def __init__(self, keys=[]):
        self.keys = keys
        self.mq = None

    @abc.abstractmethod
    def handle_message(self, what, arg1, arg2, obj):
        pass

    def send_message(self, what, arg1=-1, arg2=-1, obj=None):
        if self.mq:
            msg = Message.obtain(what, arg1, arg2, obj)
            self.mq.put(msg)
        return True

    def dispatch_message(self, msg):
        try:
            return self.handle_message(msg.what, msg.arg1, msg.arg2, msg.obj)
        except Exception as err:
            sys.stderr.write(f'{err}\n')


class DefaultHandler(MessageHandler):
    def __init__(self, mq):
        super(DefaultHandler, self).__init__(keys=[])
        self.mq = mq

    def handle_message(self, what, arg1, arg2, obj):
        return False


class MainLooper(threading.Thread, metaclass=SingletonType):

    def __init__(self):
        super(MainLooper, self).__init__(name='MainLooper')
        self.mq = Queue()
        self.handlers = {}
        self.H = DefaultHandler(self.mq)

    @property
    def default_handler(self):
        return self.H

    def add_handler(self, handler):
        handler.mq = self.mq
        for ty in handler.keys:
            if ty not in self.handlers:
                self.handlers[ty] = []
            self.handlers[ty].append(handler)

    def run(self):
        while True:
            try:
                msg = self.mq.get(timeout=3)
                if msg.what == MessageType.QUIT:
                    break
                if msg.what not in self.handlers:
                    continue
                for handler in self.handlers[msg.what]:
                    if handler.dispatch_message(msg):
                        break
            except Empty:
                pass

# MessageHandler.logger = nbeasy_get_logger('nbeasy')
# @unique
# class ServiceType(IntEnum):
#     NOP = -1
#     APP = 1
#     SRS = 2
#
#
# @unique
# class StateType(IntEnum):
#     NOP = -1
#     RUNNING = 1
#     STARTING = 2
#     STARTED = 3
#     STOPPING = 4
#     STOPPED = 5
#     STOPPTIMEOUT = 6
#     CRASHED = 99
#
#
# class ServiceStateMessageHandler(MessageHandler):
#     keys = [MessageType.STATE]
#
#     def __init__(self):
#         super().__init__(keys=self.keys)
#
#     def on_app(self, arg2, obj):
#         if StateType.RUNNING == arg2:
#             self.logger.info('app running')
#         return True
#
#     def on_srs(self, arg2, obj):
#         if StateType.RUNNING == arg2:
#             self.logger.info('srs running')
#         return True
#
#     def handle_message(self, what, arg1, arg2, obj):
#         self.logger.info(f'({what}, {arg1}, {arg2}, {obj})')
#         if what not in self.keys:
#             return False
#
#         if ServiceType.APP == arg1:
#             return self.on_app(arg2, obj)
#         elif ServiceType.SRS == arg1:
#             return self.on_srs(arg2, obj)
#
#         return False
#
# main_loop = MainLooper()
# main_loop.add_handler(ServiceStateMessageHandler())
# main_loop.start()
# main_loop.default_handler.send_message(MessageType.STATE, ServiceType.APP, StateType.RUNNING, 'test')
# main_loop.join()
