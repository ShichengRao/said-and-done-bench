"""Resolve candidate-owned Projection exports without prescribing a module name."""
import importlib.util
import sys
import types
from pathlib import Path

def module_inventory(root):
    root=Path(root).resolve()
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*.py')
                  if p.is_file() and not p.is_symlink()
                  and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts)


def _source(root,relative):
    root=Path(root).resolve();path=root/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or path.resolve()!=path.absolute():
        raise ValueError('invalid candidate module path')
    if not path.is_file():raise ValueError('not a candidate module')
    return root,path


def _load_module(root,relative):
    root,path=_source(root,relative)
    pieces=list(Path(relative).with_suffix('').parts)
    package=pieces[-1]=='__init__'
    if package and len(pieces)>1:pieces.pop()
    name='.'.join(pieces)
    # Load local regular/namespace parents so nested helpers and relative imports work.
    for i in range(1,len(pieces)):
        parent_name='.'.join(pieces[:i]);directory=root.joinpath(*pieces[:i]);init=directory/'__init__.py'
        if init.is_file():_load_module(root,init.relative_to(root).as_posix())
        else:
            current=sys.modules.get(parent_name)
            if current is None or str(directory) not in getattr(current,'__path__',[]):
                current=types.ModuleType(parent_name);current.__package__=parent_name;current.__path__=[str(directory)];sys.modules[parent_name]=current
    current=sys.modules.get(name)
    if current is not None and Path(getattr(current,'__file__','')).resolve()==path.resolve():return current
    spec=importlib.util.spec_from_file_location(name,path,submodule_search_locations=[str(path.parent)] if package else None)
    if spec is None or spec.loader is None:raise ImportError(relative)
    module=importlib.util.module_from_spec(spec);previous=sys.modules.get(name);sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        if previous is None:sys.modules.pop(name,None)
        else:sys.modules[name]=previous
        raise
    return module


def load_projection(root,target):
    value=getattr(_load_module(root,target['path']),'Projection',None)
    if not callable(value):raise ValueError('module has no callable Projection export')
    return value


def candidates(root,inventory=None):
    root=Path(root).resolve();paths=module_inventory(root) if inventory is None else inventory
    seen=set()
    for relative in sorted(set(paths),key=lambda p:(p!='pipeline.py',p)):
        try:value=load_projection(root,{'path':relative})
        except (Exception,SystemExit):continue
        if id(value) in seen:continue
        seen.add(id(value));yield {'path':relative},value


def child_bootstrap(root,target):
    # Fresh processes import the exact same selected candidate export.
    helper=str(Path(__file__).resolve())
    return ('import importlib.util\n'
            f'_s=importlib.util.spec_from_file_location("_trusted_projection_loader",{helper!r})\n'
            '_m=importlib.util.module_from_spec(_s);_s.loader.exec_module(_m)\n'
            f'Projection=_m.load_projection({str(Path(root).resolve())!r},{target!r})\n')
