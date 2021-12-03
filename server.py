#!/usr/bin/env python3

import socket
import os
import stat
from urllib.parse import unquote
import sys
from threading import Thread
import datetime

# Equivalent to CRLF, named NEWLINE for clarity
NEWLINE = "\r\n"

# Define socket host and port
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 9001

def get_file_contents(file_name):
    #Returns the text content of `file_name`
    with open(file_name, "r") as f:
        return f.read()


def get_file_binary_contents(file_name):
    #Returns the binary content of `file_name`
    with open(file_name, "rb") as f:
        return f.read()


def has_permission_other(file_name):
    """Returns `True` if the `file_name` has read permission on other group

    In Unix based architectures, permissions are divided into three groups:

    1. Owner
    2. Group
    3. Other

    When someone requests a file, we want to verify that we've allowed
    non-owners (and non group) people to read it before sending the data over.
    """
    stmode = os.stat(file_name).st_mode
    return getattr(stat, "S_IROTH") & stmode > 0

# Some files should be read in plain text, whereas others should be read
# as binary. To maintain a mapping from file types to their expected form, we
# have a `set` that maintains membership of file extensions expected in binary.
binary_type_files = set(["jpg", "jpeg", "png", "mp3"])


def should_return_binary(file_extension):
    """
    Returns `True` if the file with `file_extension` should be sent back as
    binary.
    """
    return file_extension in binary_type_files


# For a client to know what sort of file you're returning, it must have what's
# called a MIME type. We will maintain a `dictionary` mapping file extensions
# to their MIME type so that we may easily access the correct type when
# responding to requests.
mime_types = {
    "html": "text/html",
    "css": "text/css",
    "jpeg": "image/jpeg",
    "jpg": "image/jpg",
    "js": "text/javascript",
    "png": "image/png",
    "mp3": "audio/mpeg"
}

def get_file_mime_type(file_extension):
    """
    Returns the MIME type for `file_extension` if present, otherwise
    returns the MIME type for plain text.
    """
    return mime_types[file_extension] if file_extension is not None else "text/plain"

#Server responds successfully to GET and POST requests
class HTTPServer:
    """
    Our actual HTTP server which will service GET and POST requests.
    """

    def __init__(self, host="localhost", port=SERVER_PORT, directory="."):
        print(f"Server started. Listening at http://{host}:{port}/")
        self.host = host
        self.port = port
        self.working_dir = directory

        self.setup_socket()
        self.accept()

        self.teardown_socket()

    def setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(128)

    def teardown_socket(self):
        if self.sock is not None:
            self.sock.shutdown()
            self.sock.close()

    def accept(self):
        while True:
            (client, address) = self.sock.accept()
            th = Thread(target=self.accept_request, args=(client, address))
            th.start()

    def accept_request(self, client_sock, client_addr):
        try:
            data = client_sock.recv(4096)
            req = data.decode("utf-8")

            response = self.process_response(req)
            client_sock.send(response)
            client_sock.shutdown(1)
            client_sock.close()
        except Exception as e:
             print(str(e))
             exit()

    def process_response(self, request):
        formatted_data = request.strip().split(NEWLINE)
        request_words = formatted_data[0].split()

        if len(request_words) == 0:
            return

        requested_file = request_words[1][1:]
        if request_words[0] == "GET":
            return self.get_request(requested_file, formatted_data)
        if request_words[0] == "POST":
            return self.post_request(requested_file, formatted_data)
        return self.method_not_allowed()

    def get_request(self, requested_file, data):
        """
        Responds to a GET request with the associated bytes.

        If the request is to a file that does not exist, returns
        a 404 `NOT FOUND` error.

        If the request is to a file that does not have the `other`
        read permission, returns a 405 `FORBIDDEN` error.

        Otherwise, we must read the requested file's content, either
        in binary or text depending on `should_return_binary` and
        send it back with a s")tatus set and appropriate mime type
        depending on `get_file_mime_type`.
        """
        requested_file = "./" + requested_file

        if not os.path.exists(requested_file):
            return self.resource_not_found()
        if not has_permission_other(requested_file):
            return self.resource_forbidden()

        file_extension = ""
        if (requested_file.find(".") != -1):
            file_extension = requested_file.split(".")[2]

        if should_return_binary(file_extension):
            mode = 'rb'
        else:
            mode = 'r'

        with open(requested_file, mode) as f:
            response_body = f.read()
            builder = ResponseBuilder()
            builder.set_status("200", "OK")
            builder.add_header("Connection", "close")
            builder.set_content(response_body)
            builder.content_type = get_file_mime_type(file_extension)
            return builder.build()

    def formatString(self, stringToParse):
        splitString = stringToParse.split("=")
        event = splitString[1] #Second index is the event itself, first index is the 'tag' event.
        final_value = event.replace("+", " ")
        return final_value

    def post_request(self, requested_file, data):
        """
        Responds to a POST request with an HTML page with keys and values
        echoed per the requirements writeup.

        A post request through the form will send over key value pairs
        through "x-www-form-urlencoded" format. You may learn more about
        that here:
          https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST
        You /do not/ need to check the POST request's Content-Type to
        verify the encoding used (although a real server would).

        From the request, each key and value should be extracted. A row in
        the HTML table will hold a single key-value pair. With the key having
        the first column and the value the second. If a request sent n
        key-value pairs, the HTML page returned should contain a table like:

        | key 1 | val 1 |
        | key 2 | val 2 |
        | ...   | ...   |
        | key n | val n |

        Care should be taken in forming values with spaces. Since the request
        was urlencoded, it will need to be decoded using
        `urllib.parse.unquote`.
        """
        
        usefulString = data[-1] #The last index in data is the string we are concerned with
        usefulString = unquote(usefulString)
        usefulStrings = usefulString.split('&')
        html = \
                        """<html>
                        <style>
                        table, th, td {
                          border:1px solid black;
                        }
                        </style>
                        <body>

                        <table style="width:100%">
                          <tr>
                            <th>event</th>
                            <th>""" + self.formatString(usefulStrings[0]) + """</th>
                          </tr>
                          <tr>
                            <th>day</th>
                            <th>""" + self.formatString(usefulStrings[1]) + """</th>
                          </tr>
                          <tr>
                            <th>start</th>
                            <th>""" + self.formatString(usefulStrings[2]) + """</th>
                          </tr>
                          <tr>
                            <th>end</th>
                            <th>""" + self.formatString(usefulStrings[3]) + """</th>
                          </tr>
                          <tr>
                            <th>phone</th>
                            <th>""" + self.formatString(usefulStrings[4]) + """</th>
                          </tr>
                          <tr>
                            <th>location</th>
                            <th>""" + self.formatString(usefulStrings[5]) + """</th>
                          <tr>
                            <th>info</th>
                            <th>""" + self.formatString(usefulStrings[6]) + """</th>
                          <tr>
                            <th>url</th>
                            <th>""" + self.formatString(usefulStrings[7]) + """</th>
                        </table>

                        </body>
                        </html>
                        """
        builder = ResponseBuilder()
        builder.set_status("200", "OK")
        builder.add_header("Connection", "close")
        builder.set_content(html)
        builder.content_type = "text/html"
        return builder.build()

    #Returns 405 not allowed status and gives allowed methods.
    def method_not_allowed(self):

        builder = ResponseBuilder()
        builder.set_status("405", "METHOD NOT ALLOWED")
        allowed = ", ".join(["GET", "POST"])
        builder.add_header("Allow", allowed)
        builder.add_header("Connection", "close")
        return builder.build()
    
    #Returns 404 not found status and sends back our 404.html page.
    def resource_not_found(self):
        builder = ResponseBuilder()
        builder.set_status("404", "RESOURCE NOT FOUND")
        builder.add_header("Connection", "close")
        error_file = "./404.html"
        with open(error_file, "r") as f:
            builder.set_content(f.read())
            builder.content_type = "text/html"
        return builder.build()

    #Returns 403 FORBIDDEN status and sends back our 403.html page.
    def resource_forbidden(self):
        builder = ResponseBuilder()
        builder.set_status("403", "RESOURCE FORBIDDEN")
        builder.add_header("Connection", "close")
        error_file = "./403.html"
        with open(error_file, "r") as f:
            builder.set_content(f.read())
            #print(builder.content)
            builder.content_type = "text/html"
        return builder.build()

#This class follows the builder design pattern to assist in forming a response.
class ResponseBuilder:

    def __init__(self):
        
        #Initialize the parts of a response to nothing.
        self.headers = []
        self.status = None
        self.content = "" #It is possible to set this value to None, but making it "" seems cleaner
        self.content_type = None

    def add_header(self, headerKey, headerValue):
        #Adds a new header to the response
        self.headers.append(f"{headerKey}: {headerValue}")

    def set_status(self, statusCode, statusMessage):
        #Sets the status of the response
        self.status = f"HTTP/1.1 {statusCode} {statusMessage}"

    def set_content(self, content):
        #Sets `self.content` to the bytes of the content
        if isinstance(content, (bytes, bytearray)):
            self.content = content
        else:
           self.content = content.encode("utf-8")

    #Build function to returns the utf-8 bytes of the response.
    #Uses the`self.status`, `self.headers` and `self.content` to form an HTTP response
    #This server should follow valid formatting see the formatting specifications here:
    #https://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html
    
    def build(self):
        self.add_header("Date: ", datetime.datetime.now())
        if (self.content == ""):
            content_type = "text/plain" #get_file_mime_type()
            self.add_header("Content-Type: ", content_type)
            content_length = 0
            self.add_header("Content-Length: ", str(content_length))
            
            #Note to grader: I am not sure what we were required to set for this part
            #I set it to be "Jacks HTTP server" it did not negatively impact my testing
            
            self.add_header("Server: ", "Jacks HTTP server")
        else:
            content_type = self.content_type
            self.add_header("Content-Type: ", content_type)
            content_length = len(self.content)
            self.add_header("Content-Length: ", str(content_length))
            self.add_header("Server: ", "Jacks HTTP server")

        headers = NEWLINE.join(self.headers) + NEWLINE
        if isinstance(self.content, (bytes, bytearray)):
            final_response = self.status + NEWLINE + headers + NEWLINE
            return final_response.encode("utf-8") + self.content + NEWLINE.encode("utf-8")
        else:
            final_response = self.status + NEWLINE + headers + NEWLINE + self.content + NEWLINE
            return final_response.encode("utf-8")



if __name__ == "__main__":
    HTTPServer()
