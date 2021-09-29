import subprocess
#stackoverflow.com/questions/4417546/constantly-print-subprocess-output-while-process-is-running
def execute(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = process.communicate()[0]
    exitCode = process.returncode

    if (exitCode == 0):
        return output
    else:
        raise ProcessException(command, exitCode, output)

def lexA(s): #could make a parse method in class below
    import os
    import re
    s2= re.sub(r'\W+', '', s)
    cs=f'echo {s2} | lexAccess -f:id -f:x'
    s=os.popen(cs).read()
    with open("an2.tmp", 'a') as f:
            f.write(s) 
    s2=execute(cs)
    print(f's2:{s2}')
    return s


