# -*- encoding: utf-8 -*-
# Copyright © 2014 the Snipe contributors
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
Unit tests for the Editor object
'''


import array
import itertools
import random
import sys
import unittest

sys.path.append('..')
sys.path.append('../lib')

import snipe.editor


class TestEditor(unittest.TestCase):
    def testEditorSimple(self):
        e = snipe.editor.Editor(None)
        e.insert('flam')
        self.assertEqual(e.cursor.point, 4)
        e.cursor.point = 0
        e.insert('flim')
        self.assertEqual(str(e.buf), 'flimflam')
        e.cursor.point += 4
        e.insert('blam')
        self.assertEqual(str(e.buf), 'flimflamblam')

    def testEditorExpansion(self):
        e = snipe.editor.Editor(None, chunksize=1)
        e.insert('flam')
        self.assertEqual(e.cursor.point, 4)
        e.cursor.point = 0
        e.insert('flim')
        self.assertEqual(str(e.buf), 'flimflam')
        e.cursor.point += 4
        e.insert('blam')
        self.assertEqual(str(e.buf), 'flimflamblam')

    def test_mark(self):
        e = snipe.editor.Editor(None)
        e.insert('ac')
        m = e.buf.mark(1)
        m2 = e.buf.mark(1, right=True)
        n = e.buf.mark(2)
        e.cursor.point = 1
        e.insert('b')
        self.assertEqual(m.point, 1)
        self.assertEqual(m2.point, 2)
        self.assertEqual(str(e.buf), 'abc')

    def testEditorMore(self):
        e = snipe.editor.Editor(None)
        e.insert('bar')
        self.assertEqual(str(e.buf), 'bar')
        self.assertEqual(len(e.buf), 3)
        m = e.buf.mark(1)
        self.assertEqual(m.point, 1)
        e.cursor.point = 0
        e.insert('foo')
        self.assertEqual(str(e.buf), 'foobar')
        self.assertEqual(m.point, 4)
        e.cursor.point=6
        e.insert('baz')
        self.assertEqual(str(e.buf), 'foobarbaz')
        self.assertEqual(m.point, 4)
        e.cursor.point=6
        e.insert('quux')
        self.assertEqual(str(e.buf), 'foobarquuxbaz')
        self.assertEqual(m.point, 4)
        e.cursor.point=3
        e.insert('Q'*8192)
        self.assertEqual(str(e.buf), 'foo' + 'Q'*8192 + 'barquuxbaz')
        self.assertEqual(m.point, 8196)
        e.cursor.point=3
        e.delete(8192)
        self.assertEqual(e.cursor.point, 3)
        self.assertEqual(str(e.buf), 'foobarquuxbaz')
        self.assertEqual(len(e.buf), 13)
        self.assertEqual(m.point, 4)
        e.cursor.point=3
        e.insert('honk')
        e.delete(3)
        self.assertEqual(str(e.buf), 'foohonkquuxbaz')
        self.assertEqual(m.point, 7)
        e.cursor.point=4
        e.insert('u')
        e.delete(1)
        self.assertEqual(str(e.buf)[4], 'u')
        e.cursor.point=4
        e.delete(1)
        self.assertEqual(str(e.buf), 'foohnkquuxbaz')
        e.cursor.point=3
        e.delete(3)
        self.assertEqual(str(e.buf), 'fooquuxbaz')

    def testFindchar(self):
        e = snipe.editor.Editor(None)
        e.insert('abcdefghji')
        e.cursor.point = 0
        self.assertEqual(e.find_character('c'), 'c')
        self.assertEqual(e.cursor.point, 2)
        self.assertEqual(e.find_character('a', 1), '')
        self.assertEqual(e.cursor.point, 10)
        self.assertEqual(e.find_character('a', -1), 'a')
        self.assertEqual(e.cursor.point, 0)
        self.assertEqual(e.find_character('z', -1), '')
        self.assertEqual(e.cursor.point, 0)
        self.assertEqual(e.find_character('c'), 'c')
        self.assertEqual(e.cursor.point, 2)

    def testIsPred(self):
        e = snipe.editor.Editor(None)
        e.insert('abcdefghji')
        e.cursor.point = 0
        self.assertTrue(e.ispred(lambda c: c == 'a'))
        self.assertFalse(e.ispred(lambda c: c == 'b'))
        self.assertFalse(e.ispred(lambda c: c == 'a', 1))
        self.assertTrue(e.ispred(lambda c: c == 'b', 1))

    def testview(self):
        e = snipe.editor.Editor(None)
        lines = [
            ''.join(itertools.islice(
                itertools.cycle(
                    [chr(x) for x in range(ord('A'), ord('Z') + 1)] +
                    [chr(x) for x in range(ord('0'), ord('9') + 1)]),
                i,
                i + 72))+'\n'
            for i in range(256)]
        e.insert(''.join(lines))
        with self.assertRaises(ValueError):
            list(e.view(0, 'pants'))
        c = e.cursor.point
        forward = [(int(m), l) for (m, l) in e.view(0, 'forward')]
        self.assertEqual(e.cursor.point, c)
        backward = [(int(m), l) for (m, l) in e.view(len(e.buf), 'backward')]
        self.assertEqual(e.cursor.point, c)
        self.assertEqual(len(forward), 257)
        self.assertEqual(forward, list(reversed(backward)))
        self.assertEqual(
            backward[0],
            (len(e.buf), [((), ''), (('cursor', 'visible'), ''), ((), '')]))
        self.assertEqual(len(forward), 257)
        c = e.cursor.point
        it = iter(e.view(0, 'forward'))
        next(it)
        self.assertEqual(e.cursor.point, c)
        next(it)
        self.assertEqual(e.cursor.point, c)
        it = iter(e.view(len(e.buf), 'backward'))
        next(it)
        self.assertEqual(e.cursor.point, c)
        next(it)
        self.assertEqual(e.cursor.point, c)

    def testviewedge(self):
        e = snipe.editor.Editor(None)
        e.insert('abc')
        self.assertEqual(
            [(int(m), l) for (m, l) in e.view(0, 'forward')],
            [(0, [((), 'abc'), (('cursor', 'visible'), ''), ((), '')])])

    def testfuzz(
        self,
        iterations=10000,
        max_len=74,
        max_op_len=10,
        show_delay=0.01,
        ):
        """
        For many <iterations> randomly either insert or delete up to
        <max_op_len> chars or just move the gap around.

        Make sure the entire thing is never more than max_len chars long.

        Make a parallel array and confirm after each operation that
        the gap buffer's contents are the same as the array's.

        If show_delay is > 0, then the gap buffer will be shown each
        iteration.  If it's 0 then nothign will display during
        iteration, but the operations will be dumped after all
        iterations.
        """

        contents = (
            u'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        g = snipe.editor.Editor(None)
        a = array.array('u')
        for n in range(iterations):
            pos = len(g.buf) and random.randint(0, len(g.buf) - 1)
            # A 1 in 3 chance to delete, unless we're at max length,
            # then delete regardless
            if not random.randint(0, 2) or len(g.buf) >= max_len:
                howmany = min(len(g.buf) - pos, random.randint(1, max_op_len))
                g.cursor.point = pos
                g.delete(howmany)
                for d in range(howmany):
                    a.pop(pos)
            else:
                g.cursor.point = pos
                # A 1 in 2 chance to insert instead of just moving th gap
                if not random.randint(0, 1):
                    howmany = random.randint(
                        1, max(max_op_len, max_len - len(g.buf)))
                    char = random.choice(contents)
                    g.insert(char * howmany)
                    for i in range(howmany):
                        a.insert(pos, char)
            self.assertEqual(a.tounicode(), str(g.buf))
            print (str(g.buf))

    def test_character_at_point(self):
        # really testing textrange
        e = snipe.editor.Editor(None)
        e.insert('one\ntwo\nthree\nfour\n')
        e.line_previous()
        e.line_previous()
        self.assertEqual(e.character_at_point(), 't')
        e.insert('x')
        self.assertEqual(e.character_at_point(), 't')
        e.move(10)
        self.assertEqual(e.character_at_point(), '\n')

    def test_extract_current_line(self):
        e = snipe.editor.Editor(None)
        shouldchange = e.extract_current_line()
        e.insert('x')
        e.cursor.point = 0
        self.assertNotEqual(e.extract_current_line(), shouldchange)

    def test_delete_char_at_end_of_buffer(self):
        e = snipe.editor.Editor(None)
        e.insert('x')
        self.assertEqual(e.cursor.point, 1)
        e.delete_forward()
        self.assertEqual(e.cursor.point, 1)
        self.assertEqual(len(e.buf), 1)


class TestBuffer(unittest.TestCase):
    def testRegister(self):
        b = snipe.editor.Buffer(name='foo')
        self.assertEqual(b.name, 'foo')
        self.assertIs(snipe.editor.Buffer.registry['foo'], b)

        b = snipe.editor.Buffer(name='foo')
        self.assertEqual(b.name, 'foo[1]')
        self.assertIs(snipe.editor.Buffer.registry['foo[1]'], b)

        b = snipe.editor.Buffer(name='foo')
        self.assertEqual(b.name, 'foo[2]')
        self.assertIs(snipe.editor.Buffer.registry['foo[2]'], b)

        del b
        del snipe.editor.Buffer.registry['foo[2]']

        b = snipe.editor.Buffer(name='foo')
        self.assertEqual(b.name, 'foo[2]')
        self.assertIs(snipe.editor.Buffer.registry['foo[2]'], b)

        del snipe.editor.Buffer.registry['foo[1]']

        b = snipe.editor.Buffer(name='foo')
        self.assertEqual(b.name, 'foo[3]')
        self.assertIs(snipe.editor.Buffer.registry['foo[3]'], b)


if __name__ == '__main__':
    unittest.main()
