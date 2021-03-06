# -*- encoding: utf-8 -*-
# Copyright © 2015 the Snipe contributors
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided
# with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.

'''
Unit tests for stuff in windows.py
'''

import itertools
import sys
import time
import unittest

sys.path.append('..')
sys.path.append('../lib')

import snipe.filters
import snipe.messages


class TestStartup(unittest.TestCase):
    def testStartup(self):
        context = MockContext()
        startup = snipe.messages.StartupBackend(context)
        self.assertEquals(len(list(startup.walk(None))), 1)
        self.assertEquals(len(list(startup.walk(None, False))), 1)


class TestBackend(unittest.TestCase):
    def testBackend(self):
        context = MockContext()
        synth = SyntheticBackend(context)
        self.assertEquals(len(list(synth.walk(None))), 1)
        self.assertEquals(len(list(synth.walk(None, False))), 1)


class TestAggregator(unittest.TestCase):
    def testAggregator(self):
        context = MockContext()
        startup = snipe.messages.StartupBackend(context)
        synth = SyntheticBackend(context)
        sink = snipe.messages.SinkBackend(context)
        a = snipe.messages.AggregatorBackend(context, [startup, synth, sink])
        self.assertEquals(startup.count(), 1)
        self.assertEquals(synth.count(), 1)
        self.assertEquals(a.count(), 3)
        self.assertEquals(len(list(a.walk(None, False))), 3)
        list(a.send('sink', 'a message'))
        self.assertEquals(a.count(), 4)
        self.assertEquals(len(list(a.walk(None, False))), 4)
        self.assertEquals(len(list(a.walk(None))), 4)
        self.assertEquals(len(list(a.walk(None, search=True))), 3)
        self.assertEquals(
            len(list(a.walk(None, filter=snipe.filters.makefilter('yes')))),
            4)
        self.assertEquals(
            len(list(a.walk(
                None,
                filter=snipe.filters.makefilter('backend == "sink"'),
                search=True))),
            1)
        self.assertEquals(len(list(a.walk(
            float('Inf'),
            forward=False,
            backfill_to=0.0,
            ))), 4)
        self.assertEquals(len(list(a.walk(float('-Inf')))), 4)

        for i in range(2): # because caching?
            forward = list(a.walk(None, True))
            for (x, y) in list(zip([None] + forward, forward + [None]))[1:-1]:
                self.assertLess(x, y)

            backward = list(a.walk(None, False))
            for (x, y) in list(zip([None] + backward, backward + [None]))[1:-1]:
                self.assertGreater(x, y)
        a.shutdown()


class MockContext:
    def __init__(self):
        self.context = self


class SyntheticBackend(snipe.messages.SnipeBackend):
    name = 'synthetic'

    def __init__(self, context, name=None, conf={}):
        super().__init__(context, name, conf)
        count = conf.get('count', 1)
        string = conf.get('string', '0123456789')
        width = conf.get('width', 72)
        self.name = '%s-%d-%s-%d' % (
            self.name, count, string, width)
        now = int(time.time())
        self.messages = [
            snipe.messages.SnipeMessage(
                self,
                ''.join(itertools.islice(
                    itertools.cycle(string),
                    i,
                    i + width)),
                now - count + i)
            for i in range(count)]
