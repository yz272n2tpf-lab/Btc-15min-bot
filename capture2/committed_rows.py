"""Observe existing completed writes; never poll, append or evaluate strategy."""
import ast
from pathlib import Path
from sprint_evidence.passive_capture import digest

ROOT=Path(__file__).resolve().parents[1]
WRAPPER_SHA='bd8973c2a9444e670213328c032f7bb3202b8eb78a31a319330db220efcb218f'
PROTECTION_SHA='783980d078d95a79d32384f0f9d4e16a85f0ee7c5d36135e7771ade89279e0e2'


def emit(source,kind,row):
    try:
        from capture2.runtime import producer
        return producer(source).offer(kind,dict(record=row,basis='ORIGINAL_WRITE_AND_CLOSE_RETURNED',
            upstream_early_origin_id=None,origin_link_status='UNAVAILABLE_UNLESS_PRESENT_IN_ORIGINAL_RECORD',
            native_action=False))
    except Exception:return False


def wrapper_tree(raw):
    if digest(raw)!=WRAPPER_SHA:raise ValueError('NATIVE_WRAPPER_SOURCE_CHANGED')
    tree=ast.parse(raw);count=0
    class Writes(ast.NodeTransformer):
        def visit_With(self,node):
            nonlocal count
            if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='COHORT_PATH' and n.func.attr=='open' for n in ast.walk(node)):
                # Only write sites; the original read-only recovery scan stays untouched.
                calls=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write']
                if calls:
                    count+=1
                    return [node,ast.parse("_capture_row_emit("+repr(WRAPPER_SHA)+", 'NATIVE_COMMITTED_COHORT', row)").body[0]]
            return self.generic_visit(node)
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in ('cohort_offer','_cohort_closeout_worker'):Writes().visit(node)
    if count!=2:raise ValueError('COHORT_WRITE_SEAMS')
    return ast.fix_missing_locations(tree)


def protection_tree(raw):
    if digest(raw)!=PROTECTION_SHA:raise ValueError('PROTECTION_SOURCE_CHANGED')
    tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='append')
    if not isinstance(fn.body[-1],ast.With):raise ValueError('PROTECTION_WRITE_SEAM')
    fn.body.append(ast.parse("_capture_row_emit("+repr(PROTECTION_SHA)+", 'SHADOW_FINAL_COMMITTED_ROW', rec)").body[0])
    return ast.fix_missing_locations(tree)


def install_wrapper(module):
    raw=Path(module.__file__).read_bytes();tree=wrapper_tree(raw)
    module.__dict__['_capture_row_emit']=emit
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('cohort_offer','_cohort_closeout_worker')]
    exec(compile(ast.Module(body=selected,type_ignores=[]),module.__file__,'exec'),module.__dict__)


def main():
    path=ROOT/'btc15_final_position_protection_shadow_v3.py'
    exec(compile(protection_tree(path.read_bytes()),str(path),'exec'),dict(__name__='__main__',__file__=str(path),_capture_row_emit=emit))
