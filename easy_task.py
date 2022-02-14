#!/usr/bin/python3
# -*- coding: utf-8 -*-

from multiprocessing import Process, Queue
from enum import Enum
import inspect
from abc import ABC, abstractmethod


class State(Enum):
    STOP = "S_STOP"
    SHUTDOWN = "S_SHUTDOWN"
    SHUTDOWN_LAST = "S_SHUTDOWN_LAST"


class ICallable(ABC):

    @classmethod
    def init(self):
        pass

    @abstractmethod
    def __call__(self, x):
        ...

    @classmethod
    def shutdown(self):
        pass


class Task(object):
    def __init__(self, id, fn, input_queue, output_queue, multiplicity):
        self.id = id
        self.fn = fn
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.multiplicity = multiplicity

    def start(self):
        self.process = Process(target=self.main_loop, args=(self.input_queue, self.output_queue))
        self.process.start()

    def main_loop(self, input_queue, output_queue):
        self.input_queue = input_queue
        self.output_queue = output_queue

        try:
            if hasattr(self.fn, "init"):
                self.fn.init()

            while True:
                x = self.input_queue.get()
                if x == State.SHUTDOWN:
                    break
                if x == State.SHUTDOWN_LAST:
                    self.output_queue.put(State.STOP)
                    break
                if x == State.STOP:
                    for i in range(self.multiplicity-1):
                        self.input_queue.put(State.SHUTDOWN)
                    self.input_queue.put(State.SHUTDOWN_LAST)
                    continue

                result = self.fn(x)
                if inspect.isgenerator(result):
                    for x in result:
                        if x == State.STOP:
                            self.input_queue.put(State.STOP)
                            break
                        self.output_queue.put(x)
                else:
                    if result == State.STOP:
                        self.input_queue.put(State.STOP)
                    else:
                        self.output_queue.put(result)

            if hasattr(self.fn, "shutdown"):
                self.fn.shutdown()

        except KeyboardInterrupt:
            pass
        except Exception:
            print("For {}".format(self.fn))
            raise


class TaskPipeline(object):
    def __init__(self):
        self.tasks = []
        self.input_queue = Queue(1)
        self.output_queue = Queue(1)
        self.nextId = 1

    def run(self, arg=None):
        for task in self.tasks:
            task.start()
        self.input_queue.put(arg)
        while True:
            x = self.output_queue.get()
            if x == State.STOP:
                break

    def add(self, func, fan_out=1):
        input_queue = self.input_queue
        output_queue = self.output_queue
        if len(self.tasks):
            input_queue = Queue(1)
            self.tasks[-1].output_queue = input_queue

        for i in range(fan_out):
            task = Task(self.nextId, func, input_queue, output_queue, fan_out)
            self.nextId += 1
            self.tasks.append(task)

# def input_func(x):
#     for i in range(x):
#         yield i
#     yield State.STOP
#
# def output_func(x):
#     yield x * 2
#
# class ResultTest(ICallable):
#     def __init__(self, arg):
#         self.arg = arg
#
#     def __call__(self, x):
#         print('result', x)
#
# pipe = TaskPipeline()
# pipe.add(input_func)
# pipe.add(output_func)
# pipe.add(ResultTest('test'))
# pipe.run(5)
