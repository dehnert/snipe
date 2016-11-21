# -*- encoding: utf-8 -*-
# Copyright © 2016 the Snipe contributors
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
snipe.zulip
--------------
Backend for talking to `Zulip <https://zulip.org>`.
'''

_backend = 'Zulip'


import aiohttp
import asyncio
import netrc
import os
import pprint
import textwrap
import time
import urllib.parse

from . import messages
from . import util


class Zulip(messages.SnipeBackend, util.HTTP_JSONmixin):
    name = 'zulip'
    loglevel = util.Level(
        'log.zulip', 'Zulip',
        doc='loglevel for zulip backend')

    def __init__(self, context, url='https://chat.zulip.org', **kw):
        super().__init__(context, **kw)
        self.url = url.rstrip('/')
        self.messages = []
        self.tasks.append(asyncio.Task(self.connect()))

    @util.coro_cleanup
    def connect(self):
        hostname = urllib.parse.urlparse(self.url).hostname

        # TODO factor the following out of slack and irccloud
        try:
            rc = netrc.netrc(os.path.join(self.context.directory, 'netrc'))
            authdata = rc.authenticators(hostname)
        except netrc.NetrcParseError as e:
            self.log.warn(str(e))  # need better notification
            return
        except FileNotFoundError as e:
            self.log.warn(str(e))
            return

        self.user = authdata[0]
        self.token = authdata[2]

        self.params = None
        while True:
            import pprint
            if self.params is None:
                self.log.debug('registering')
                params = yield from self._post('register')

                # TODO check for an error, backoff, etc.
                self.params = params

                queue_id = params['queue_id']
                last_event_id = params['last_event_id']

            result = yield from self._get(
                'events', queue_id=queue_id, last_event_id=last_event_id)

            # TODO check for error and maybe invalidate params?

            msgs = [
                ZulipMessage(self, event)
                for event in result['events']
                if event.get('type') == 'message']
            last_event_id = max(*[last_event_id] + [
                int(event['id']) for event in result['events']])
            if msgs:
                self.messages.extend(msgs)
                # make sure that the message list remains
                # monitonically increasing by comparing the new
                # messages (and the last old message) pairwise.
                for a, b in zip(
                        self.messages[-len(msgs) - 1:][:-1],
                        self.messages[-len(msgs) - 1:][1:]):
                    if b.time <= a.time:
                        self.log.debug('before %f, %f', a.time, b.time)
                        b.time = a.time + .0001
                        self.log.debug('after %f, %f', a.time, b.time)
                self.redisplay(msgs[0], msgs[-1])

        self.log.debug('connect ends')

    @asyncio.coroutine
    def _post(self, method, **kw):
        result = yield from self.http_json(
            'POST', self.url + '/api/v1/' + method,
            auth=aiohttp.BasicAuth(self.user, self.token),
            headers={'content-type': 'application/x-www-form-urlencoded'},
            data=urllib.parse.urlencode(kw),
            )
        return result

    @asyncio.coroutine
    def _get(self, method, **kw):
        result = yield from self.http_json(
            'GET', self.url + '/api/v1/' + method,
            auth=aiohttp.BasicAuth(self.user, self.token),
            params=kw,
            )
        return result


class ZulipMessage(messages.SnipeMessage):

    def __init__(self, backend, event):
        super().__init__(
            backend,
            pprint.pformat(event),
            float(event['message'].get('timestamp', time.time())),
            )
        self.data = event['message']

        self._sender = ZulipAddress(backend, event.get('sender_email', '?'))
        if self.data.get('type') == 'stream':
            self.stream = str(self.data['display_recipient'])
        elif self.data.get('type') == 'private':
            self.personal = True
        else:
            backend.log.debug('weird message: %s', pprint.pformat(event))
            self.noise = True

    def display(self, decoration):
        tags = set(self.decotags(decoration))

        if self.data['type'] == 'private':
            title = ', '.join([
                x.get('short_name', x.get('email', str(x)))
                for x in self.data['display_recipient']])
        else:
            # we expect it's a string already, buuuut....
            title = str(self.data['display_recipient'])

        subject = self.data.get('subject')
        if subject:
            subject = ' ' + subject
        else:
            subject = ''

        name = self.data.get('sender_full_name')
        if name:
            name = ' ' + name
        else:
            name = ''

        timestamp = time.strftime(
            ' %H:%M:%S\n', time.localtime(self.data['timestamp']))

        body = self.data.get('content')
        body = body.replace('\r\n', '\n')  # conform to local custom

        # make markdown with long lines readable
        # (really, replace this with a markdown renderer that does literal text
        # & _underlining_ & *bold* &c correctly)
        body = '\n\n'.join(
            '\n'.join(textwrap.wrap(s, 72)) for s in body.split('\n\n'))
        if body[-1] != '\n':
            body += '\n'

        return [(tuple(x), y) for (x, y) in
            [
            (tags | {'bold'}, title + '>'),
            (tags, subject + ' <'),
            (tags | {'bold'}, self.data.get('sender_email', '?')),
            (tags, '>' + name),
            (tags | {'right'}, timestamp),
            (tags, body)
            ]]


class ZulipAddress(messages.SnipeAddress):

    def __init__(self, backend, text):
        self.backend = backend
        self.text = text
        super().__init__(backend, [text])

    def __str__(self):
        return self.backend.name + '; ' + self.short()

    def short(self):
        return self.text
