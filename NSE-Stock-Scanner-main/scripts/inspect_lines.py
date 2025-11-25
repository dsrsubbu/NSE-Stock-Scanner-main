from pathlib import Path
p = Path('helpers/datahandler.py')
lines = p.read_text(encoding='utf-8').splitlines()
for i in range(660, 688):
    s = lines[i]
    print(f"{i+1}: {s!r}")
print('---')
print('\n'.join(f"{i+1}: {ord(c)}" for i,c in enumerate(lines[671][0:20])))
