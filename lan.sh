#lexAccess -f:id -f:x | nc -l -p 1234 &
nc -l -p 1234 |lexAccess -f:id -f:x 
