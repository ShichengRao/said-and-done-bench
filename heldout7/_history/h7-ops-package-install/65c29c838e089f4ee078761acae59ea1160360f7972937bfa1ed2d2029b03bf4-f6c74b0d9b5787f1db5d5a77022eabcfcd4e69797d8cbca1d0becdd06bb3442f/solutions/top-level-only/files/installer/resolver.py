"""Dependency-closure resolution across repositories, with delegated target lookup."""
import fnmatch
import hashlib

from installer import trust


class Resolver:
    """Works on a private copy of the store state; the caller persists it only if the whole closure succeeds."""

    def __init__(self, state, request):
        self.state = state; self.request = request; self.at = request['at']
        self.prepared = {}; self.pins = {}; self.resolved = {}; self.visiting = set()

    def prepare(self, repo):
        if repo in self.prepared:
            return self.prepared[repo]
        if repo not in self.state['repos'] or repo not in self.request['bundles']:
            raise ValueError(f'unknown repository {repo}')
        repo_state = self.state['repos'][repo]; bundle = self.request['bundles'][repo]
        root = trust.rotate_root(repo_state['root'], bundle['roots'], self.at)
        repo_state['root'] = root
        snapshot = trust.check_snapshot(repo_state, bundle['snapshot'], root, self.at)
        self.prepared[repo] = (repo_state, bundle, root, snapshot)
        return self.prepared[repo]

    def lookup(self, repo, path):
        repo_state, bundle, root, snapshot = self.prepare(repo)

        def visit(name, authorization, stack):
            if name in stack:
                raise ValueError('delegation cycle')
            body = trust.check_role(repo_state, name, bundle['metadata'].get(name), snapshot['meta'].get(name),
                                    authorization, root, self.at)
            if path in body['targets']:
                return (body['targets'][path], name), False
            for delegate in body['delegations']:
                if any(fnmatch.fnmatchcase(path, pattern) for pattern in delegate['paths']):
                    found, terminated = visit(delegate['name'], delegate, stack | {name})
                    if found:
                        return found, False
                    if terminated or delegate['terminating']:
                        return None, True
            return None, False

        found, _ = visit('targets', root['roles']['targets'], frozenset())
        if found is None:
            raise ValueError(f'{repo}:{path} is not a trusted target')
        return found

    def resolve(self, ref):
        key = (ref['repo'], ref['path']); pin = ref['sha256']
        if key in self.pins and self.pins[key] != pin:
            raise ValueError(f'conflicting pins for {key}')
        self.pins[key] = pin
        if key in self.visiting:
            raise ValueError(f'dependency cycle at {key}')
        if key in self.resolved:
            return
        self.visiting.add(key)
        info, role = self.lookup(*key)
        if info['sha256'] != pin:
            raise ValueError(f'{key} does not match its pin')
        # Dependencies are installed by their own repositories' requests.
        repo_state, bundle, _, _ = self.prepared[key[0]]
        raw = bundle['artifacts'].get(key[1])
        if raw is None or len(raw.encode()) != info['length'] or hashlib.sha256(raw.encode()).hexdigest() != pin:
            raise ValueError(f'{key} bytes do not match the signed descriptor')
        repo_state['installed'][key[1]] = raw
        self.resolved[key] = {'repo': key[0], 'path': key[1], 'sha256': pin, 'length': info['length'], 'role': role}
        self.visiting.remove(key)

    def run(self):
        for ref in self.request['requested']:
            self.resolve(ref)
        return [self.resolved[key] for key in sorted(self.resolved)]
