import sys
import os
import argparse
import socket
import time
from threading import Thread

# Set defaults for variables
errmsg = 'HTTP/1.1 404 NOT FOUND\r\n\r\n'
response10 = 'HTTP/1.0 200 OK\r\n\r\n'
response11 = 'HTTP/1.1 200 OK\r\n\r\n'
servername = "127.0.0.1"


# Implementation of a simple queue
class Queue:
    def __init__(self):
        self.items = []

    def is_empty(self):
        return self.items == []

    def enqueue(self, item):
        self.items.insert(0, item)

    def dequeue(self):
        return self.items.pop()

    def size(self):
        return len(self.items)


# Safely prints to console without interruption
# Normal print is bad because implicit newline can cause a race condition with other print statements
def safeprint(output):
    printqueue.enqueue(output)


# Thread constantly checks if there's anything to print and prints it if so
def checkprint():
    while True:
        if not printqueue.is_empty():
            while not printqueue.is_empty():
                text = printqueue.dequeue()
                print(text, file=sys.stderr)


# If any thread has finished, remove it from the list
def checkthreads():
    while True:
        for thread in threads:
            if not thread.is_alive():
                threads.remove(thread)


# Handles a single request from a specific client, then closes
def handlerequest(clientsocket):
    # Attempts to receive message, terminating process if it times out
    starttime = time.time()
    message = ""
    clientsocket.setblocking(0)
    while message == "":
        if time.time() > starttime + timeout:
            safeprint("Error: socket recv timed out")
            clientsocket.close()
            return
        # Try to get the message, and if it doesn't work immediately, loop back to check the time again
        try:
            message = clientsocket.recv(1024).decode()
        except socket.error:
            pass

    # If end of data is hit while waiting for more input, terminate connection immediately
    if len(message) == 0 or "\r\n" not in message:
        safeprint("Error: unexpected end of input")
        clientsocket.close()
        return

    # If message has non-ascii in it, print error and kill connection
    if not message.isascii():
        safeprint("Error: invalid input character")
        clientsocket.close()
        return

    # Split the request by spaces
    request = message[:message.index("\r\n")].split(" ")

    # Splits headings by "/r/n" (filtering out empty lines), and forms it into a list of (headername, headervalue)
    headings = []
    badheadings = False
    for heading in list(filter(None, message.split("\r\n")))[1:]:
        try:
            split = heading.index(":")
        except ValueError:
            badheadings = True
            break
        headings.append([heading[:split].strip(), heading[split + 1:].strip()])

    # If any heading is malformed, print error and kill connection
    if badheadings:
        safeprint("Error: invalid headers")
        clientsocket.close()
        return

    # If 'X-additional-wait' exists as a header, set timeout to that value, otherwise set it to 0
    delay = 0
    for heading in headings:
        if heading[0] == "X-additional-wait":
            delay = int(heading[1])

    # If the request line is incorrectly formatted, print error and kill connection
    if len(request) != 3 or request[0] != "GET" or not request[1].startswith("/") or not \
            (request[2].endswith("1.0") or request[2].endswith("1.1")):
        safeprint("Error: invalid request line")
        clientsocket.close()
        return

    # If request tries to access parent directory or the path is invalid,
    # print error message, send back Error 404, and close connection
    currentpath = os.path.normpath(os.getcwd() + request[1])
    if ".." in request[1] or not os.path.isfile(currentpath):
        safeprint("Error: invalid path")
        clientsocket.send(errmsg.encode())
        clientsocket.close()
        return

    # Reads the file
    file = open(currentpath, "rb")
    body = file.read()
    file.close()

    # If there's a delay, then delay it
    time.sleep(delay)

    # Return HTTP message to the client
    if request[2].endswith("1.0"):
        http_response = response10.encode() + body
    elif request[2].endswith("1.1"):
        http_response = response11.encode() + body
    else:
        safeprint("Error: invalid request line")
        clientsocket.close()
        return
    clientsocket.send(http_response)
    safeprint("Success: served file %s" % request[1])

    # Tear down the communication
    clientsocket.close()


# BEGIN HERE

# Determine command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--port", help="port server listens on (default is 8080)", default=8080)
parser.add_argument("--maxrq", help="max number of concurrent requests (default is 10)", default=10)
parser.add_argument("--timeout", help="max seconds to wait for a client (default is 10)", default=10)
args = parser.parse_args()

# Set variables based on command line arguments
port = int(args.port)
maxrq = int(args.maxrq)
timeout = float(args.timeout)

# Create the main server socket (to listen for incoming connections) and bind server to the socket
serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversocket.bind((servername, port))

# Tell the OS this will be used as a passive socket (i.e., to receive incoming connections)
serversocket.listen(maxrq)

# Set up printer thread
printqueue = Queue()
printer = Thread(target=checkprint, daemon=True)
printer.start()

# Must keep track of every thread currently running something, and when they die
threads = list()
deathchecker = Thread(target=checkthreads, daemon=True)
deathchecker.start()

while True:
    # Block waiting for incoming connections, then prints information about new socket
    connectionsocket, addr = serversocket.accept()
    safeprint("Information: received new connection from %s, port %s" % (addr[0], addr[1]))

    # If there's space for a new connection, add it to the list of threads and start it
    if len(threads) < maxrq:
        newthread = Thread(target=handlerequest, args=(connectionsocket,), daemon=True)
        newthread.start()
        threads.append(newthread)
    # Otherwise, print error and kill the connection immediately
    else:
        safeprint("Error: too many requests")
        connectionsocket.close()
        continue
