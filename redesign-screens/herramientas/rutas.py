import ast, sys, glob, re
files = ['app.py'] + sorted(glob.glob('routes/*.py'))
for f in files:
    src = open(f, encoding='utf-8-sig').read()
    tree = ast.parse(src)
    # blueprint prefixes
    prefixes = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and getattr(n.value.func,'id','')=='Blueprint':
            kw = {k.arg: getattr(k.value,'value',None) for k in n.value.keywords}
            prefixes[n.targets[0].id] = kw.get('url_prefix') or ''
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr=='route':
                    bp = getattr(d.func.value,'id','app')
                    url = d.args[0].value
                    meth = [getattr(e,'value','') for kw in d.keywords if kw.arg=='methods' for e in kw.value.elts] or ['GET']
                    seg = ast.get_source_segment(src, n) or ''
                    tpl = sorted(set(re.findall(r"render_template\(\s*['\"]([^'\"]+)", seg)))
                    ses = 'session' in seg and ('user_id' in seg)
                    redir = sorted(set(re.findall(r"redirect\(\s*['\"]([^'\"]+)", seg)))[:3]
                    js = 'jsonify' in seg
                    print(f"{f}|{bp}|{prefixes.get(bp,'')}{url}|{','.join(meth)}|{','.join(tpl)}|ses={int(ses)}|json={int(js)}|{n.name}")
