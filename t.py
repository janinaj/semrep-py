txta=['heart','lung','spleen']

def lexA(s):
    import os
    cs=f'echo {s} | lexAccess -f:id -f:x'
    s=os.popen(cs).read()
    return s

for a in txta:
    s=lexA(a)
    print(s)

#all at once
all='\n'.join(txta)
s=lexA(all)
print(s)
