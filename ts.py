#import subprocess  #works but1shot
#process = subprocess.Popen(['echo', '"Hello stdout"'], stdout=subprocess.PIPE)
#stdout = process.communicate()[0]
#print('STDOUT:{}'.format(stdout))

from subprocess import Popen, PIPE, STDOUT
p = Popen(['./la.sh'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
#p = Popen(['lexAccess -f:id -f:x'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
stdout_data = p.communicate(input='heart')[0]
