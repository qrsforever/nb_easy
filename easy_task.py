#!/usr/bin/python3
# -*- coding: utf-8 -*-

from multiprocessing import Process, Queue, Value, Array, Pipe, Lock
from enum import Enum
from abc import ABC, abstractmethod
import numpy as np
import inspect
import sys # noqa


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


class ShmNumpy(object):
    def __init__(self, dtype, shape):
        self.shm_size = int(np.prod(shape))
        self.mp_array = Array(dtype, self.shm_size, lock=Lock())
        self.np_array = np.frombuffer(self.mp_array.get_obj(), dtype=dtype)
        self.dsize, self.ddim = Value('I', self.shm_size), Value('I', 3)
        self.dshape = Array('I', shape)

    @property
    def data(self):
        return self.np_array[:self.dsize.value].reshape(self.dshape[:self.ddim.value])

    @data.setter
    def data(self, d):
        assert self.shm_size >= d.size
        self.np_array[:d.size] = d.ravel()
        self.ddim.value = len(d.shape)
        self.dshape[:len(d.shape)] = d.shape
        self.dsize.value = d.size

    @property
    def shape(self):
        return self.dshape.value

    def lock(self):
        self.mp_array.acquire()

    def unlock(self):
        self.mp_array.release()


class TaskV2(object):
    def __init__(self, id, func, input_pipe, output_pipe, inshms=[], outshms=[]):
        self.id = id
        self.fn = func
        self.input_pipe, self.output_pipe = input_pipe, output_pipe
        self.inshms, self.outshms = inshms, outshms

    def inshms(self):
        return self.inshms

    def outshms(self):
        return self.outshms

    def start(self):
        self.process = Process(target=self.main_loop, args=(self.input_pipe, self.output_pipe))
        self.process.start()

    def main_loop(self, input_pipe, output_pipe):
        try:
            if hasattr(self.fn, "init"):
                self.fn.init()

            while True:
                x = self.input_pipe.recv()
                # sys.stderr.write(f'<{x}>\n')
                if x == State.STOP:
                    self.output_pipe.send(State.STOP)
                    break

                result = self.fn(x, *self.inshms, *self.outshms)
                if inspect.isgenerator(result):
                    for x in result:
                        self.output_pipe.send(x)
                else:
                    self.output_pipe.send(result)

            if hasattr(self.fn, "shutdown"):
                self.fn.shutdown()

        except KeyboardInterrupt:
            pass
        except Exception:
            print("For {}".format(self.fn))
            raise


class TaskPipelineV2(object):
    def __init__(self):
        self.tasks = []
        self.nextId = 1
        self.input_pipe, self.output_pipe = Pipe()

    def run(self, x=None):
        for task in self.tasks:
            task.start()
        self.input_pipe.send(x)
        while True:
            x = self.output_pipe.recv()
            if x == State.STOP:
                break

    def add(self, fn, shms=[]):
        input_pipe, output_pipe = Pipe()

        inshms, outshms = [], shms
        if len(self.tasks) > 0:
            inshms = self.tasks[-1].outshms

        self.tasks.append(TaskV2(self.nextId, fn, self.output_pipe, input_pipe, inshms, outshms))
        self.nextId += 1
        self.output_pipe = output_pipe

# def input_func(x, shm_frame):
#     for i in range(x):
#         shm_frame.lock()
#         shm_frame.data = np.ones(shm_frame.shape) * i
#         y = {'a': i}
#         yield  y
#     yield State.STOP
#
# def output_func(x, shm_frame):
#     y = x['a'] * 2
#     sys.stderr.write(f'{shm_frame.data[0, 0, :]}')
#     shm_frame.unlock()
#     yield y
#
# class ResultTest(ICallable):
#     def __init__(self, arg):
#         self.arg = arg
#
#     def __call__(self, x):
#         sys.stderr.write(f'result: {x}\n')
#
# pipe = TaskPipelineV2()
# pipe.add(input_func, shms=[ShmNumpy('I', (640, 352, 3))])
# pipe.add(output_func)
# pipe.add(ResultTest('test'))
# pipe.run(10)
