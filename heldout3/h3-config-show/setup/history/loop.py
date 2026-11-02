"""The relay loop: fetch a batch from the partner feed, publish it, repeat."""

import json
import logging
import time
import urllib.request

log = logging.getLogger('relay.loop')


def fetch(upstream, limit):
    request = urllib.request.Request(f"{upstream['url']}?limit={limit}",
                                     headers={'Authorization': f"Bearer {upstream['api_token']}"})
    with urllib.request.urlopen(request, timeout=upstream['timeout_s']) as answer:
        return json.load(answer)['events']


def relay_forever(settings, publish=None):
    """Runs until stopped; returns 1 if the feed can't be reached."""
    upstream, service = settings['upstream'], settings['service']
    while True:
        try:
            events = fetch(upstream, service['batch_size'])
        except OSError as error:
            log.error('the feed at %s is unreachable: %s', upstream['url'], error)
            return 1
        if events and not service['dry_run'] and publish:
            publish(events)
        log.info('relayed %d events', len(events))
        time.sleep(service['poll_interval_s'])
