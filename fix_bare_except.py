"""批量修复裸 except：except: -> except Exception:

裸 except 会吞掉 KeyboardInterrupt/SystemExit，长回测中 Ctrl+C 无法中断。
改成 except Exception 保持吞业务异常的行为，但放行系统级异常。
只处理纯 `except:`（含同行的 pass/continue/break 等），不动 `except X:`。
"""
import os
import re

TARGET_DIRS = ['strategies', 'data', 'trading', 'core', 'timing', 'scripts', '.']
EXCLUDE = {'fix_bare_except.py'}

pat = re.compile(r'^(\s*)except\s*:(.*)$', re.MULTILINE)


def _read(path):
    for enc in ('utf-8-sig', 'gbk', 'latin-1'):
        try:
            return open(path, encoding=enc).read()
        except Exception:
            continue
    return None


changed_files = []
total = 0

for d in TARGET_DIRS:
    if not os.path.isdir(d):
        continue
    for root, _dirs, files in os.walk(d):
        if '.pytest_tmp' in root or '__pycache__' in root:
            continue
        for fn in files:
            if not fn.endswith('.py') or fn in EXCLUDE:
                continue
            path = os.path.join(root, fn)
            src = _read(path)
            if src is None:
                continue
            new_src, n = pat.subn(r'\1except Exception:\2', src)
            if n:
                open(path, 'w', encoding='utf-8').write(new_src)
                changed_files.append((path, n))
                total += n

for path, n in changed_files:
    print(f'  {path}: {n}')
print(f'TOTAL: {total} 处，{len(changed_files)} 个文件')
