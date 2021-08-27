import subprocess
import socket

class SocketClient:
    def __init__(self, host, port, timeout = 5, buffer_size = 4096, retries = 3):
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.retries = retries

        self.host = host
        self.port = port

    def send(self, text, receive_once = False):
        # try:
            # add a line break -- important for connecting to Java servers
            if text[-1] != '\n':
                text += '\n'

            # create connection and send data to server
            sock = socket.create_connection((self.host, self.port))
            sock.sendall(text.encode('UTF-8'))

            # receive data (broken down in to buffer_size chunks)
            response = ''
            while True:
                bytes_received = sock.recv(self.buffer_size)

                # stop listening when no more bytes are received
                # if not bytes_received or bytes_received.decode().strip() == '':
                #     break

                # convert received bytes into string and merge with current response
                response += bytes_received.decode()

                # stop listening when no more bytes are received
                # print(len(bytes_received))
                if not bytes_received or receive_once:
                    break

            sock.close()

            # check output
            # print(f'echo "{text.strip()}" | nc {self.host} {self.port}')
            # ps = subprocess.Popen(f'echo "{text.strip()}" | nc {self.host} {self.port}', shell=True,
            #                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # output = ps.communicate()[0]
            # if output.decode().strip() != response.strip():
            #     print('-------')
            #     print(output.decode())
            #     print('-------')
            #     print(len(response.encode()))
            #     print(len(response.strip()))
            #     input('ERROR')

            return response.strip()
        # what to do if exception is received??
        # except Exception as e:
        #     print(f'Error connecting to server: {self.host}:{self.port}')
        #     print(e)
        #     return ''