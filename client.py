from socket import *
from time import sleep

# Address and port to which the client is going to connect
serverName = '127.0.0.1'
serverPort = 8080

# Create the socket used to talk with the server
clientSocket = socket(AF_INET, SOCK_STREAM)

# Attempt to connect to the server
clientSocket.connect((serverName, serverPort))

# Sleep for too long, so it times out
sleep(2)

# Send a request
request = "GET /test.txt HTTP/1.0\r\nX-additional-wait: " + str(2) + "\r\n\r\n"
clientSocket.send(request.encode())

# Wait for the response from the server
try:
    modifiedSentence = clientSocket.recv(4096)
    print(modifiedSentence.decode())
except ConnectionAbortedError:
    print("Timeout :(")

# Tear down the socket
clientSocket.close()
