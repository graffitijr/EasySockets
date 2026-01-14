import socket
import threading
import typing
import time

def get_local_ip():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.connect(("8.8.8.8",80))

    return client.getsockname()[0]

class Server:
    def __init__(self, socket_type: str = "TCP", ip: str = get_local_ip(), port: int = 50505, on_receive: typing.Callable[[str], None] = None, debug_logs: bool = False):
        self.ip = ip
        self.port = port
        self.socket_type = socket_type
        self.debug_logs = debug_logs
        self.on_message_function = on_receive
        self.os_given_port = None

        self.server = None
        self.conn = None

        self.running: bool = False

    def _debug(self, m):
        if self.debug_logs:
            print(m)

    def send(self, m):
        self._debug(f"sent: {m}")
        if self.conn:
            self.conn.sendall(m.encode())

    def get_port(self):
        if self.os_given_port:
            return self.os_given_port
        else:
            return None

    def start(self):
        if self.socket_type == "TCP":

            t1 = threading.Thread(target=self._start_tcp_server)
            t1.start()

        else:
            print(f"{self.socket_type} is not a valid socket type. TCP is only allowed but UDP may be in the future")


    def _start_tcp_server(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._debug(f"trying to bind: {self.ip}:{self.port}")
            self.server.bind((self.ip,self.port))
            self._debug(f"bound to: {self.server.getsockname()}")
            self.os_given_port = self.server.getsockname()[1]
            self.server.listen(1)

            self._debug("waiting for connection connecting...")

            self.conn, addr = self.server.accept()

            self.running = True

            self._debug(f"connected to {addr}")

            while True:
                data = self.conn.recv(1024)
                if not data:
                    break
                self.on_message_function(data.decode())

        except Exception as e:
            print(e)

#############################################################################################################

class Client:
    def __init__(self, socket_type: str = "TCP", ip: str = get_local_ip(), port: int = 50505, on_receive: typing.Callable[[str], None] = None, debug_logs: bool = False):
        self.ip = ip
        self.port = port
        self.socket_type = socket_type
        self.debug_logs = debug_logs
        self.on_message_function = on_receive

        self.client = None

        self.running: bool = False

        self.status: str = ""

    def _debug(self, m):
        if self.debug_logs:
            print(m)
            self.status = m

    def send(self, m):
        self._debug(f"sent: {m}")
        if self.client:
            self.client.sendall(m.encode())

    def get_port(self):
        if self.port:
            return self.port
        else:
            return None

    def start(self):
        if self.socket_type == "TCP":

            t1 = threading.Thread(target=self._start_tcp_server)
            t1.start()

        else:
            print(f"{self.socket_type} is not a valid socket type. TCP is only allowed but UDP may be in the future")


    def _start_tcp_server(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._debug(f"trying to connect to: {self.ip}:{self.port}")

            self.client.connect((self.ip,self.port))

            self._debug("connected")

            self.running = True

            while True:
                data = self.client.recv(1024)
                if not data:
                    break
                self.on_message_function(data.decode())

        except Exception as e:
            print(e)

class Peer:
    def __init__(self, your_id: str = "Guest", peers_id: str = "Guest1", on_receive: typing.Callable[[str], None] = None, rendezvous_port: int = 50505):
        self.user_id = your_id
        self.peer_id = peers_id
        self.message_received_func = on_receive
        self.rendezvous_port = rendezvous_port
        self.peer_ip: str = ""
        self.peer_port: int = 0
        self.on_message_func = on_receive
        self.os_given_port: int
        self.connection_running: bool = False
        self.client: Client
        self.server: Server

    def start(self):
        self._read_rendezvous_to_find_peer_udp()

    def _read_rendezvous_to_find_peer_udp(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        client.bind(("0.0.0.0",self.rendezvous_port))

        print("waiting for 2 seconds on rendezvous")
        client.settimeout(2)

        data = None
        safe_data = ""

        try:
            data, addr = client.recvfrom(1024)
            if data:
                safe_data = data.decode()

        except Exception as e:
            print(e)

        if safe_data.startswith(self.peer_id):
            try:
                address = safe_data.split(";")[1]
                print(address)
                self.peer_ip = address.split(":")[0]
                self.peer_port = int(address.split(":")[1])
            except Exception as e:
                print(f"Error: {e}")

            client.close()
            self._connect_to_peer_server()
        else:
            client.close()
            self._host_server_on_given_port()

    def _connect_to_peer_server(self):
        def on_receive(m):
            self.on_message_func(m)

        self.client = Client(ip=self.peer_ip, port=self.peer_port, on_receive=on_receive)
        self.client.start()

        self.client.send(f"connected:{self.user_id}")

    def _host_server_on_given_port(self):
        def on_receive(m):
            if m == f"connected:{self.peer_id}":
                self.connection_running = True
                print("connection success, stopping broadcast.")
            self.on_message_func(m)

        self.server = Server(ip=get_local_ip(), port=0, on_receive=on_receive)
        self.server.start()

        self.os_given_port = self.server.get_port()

        self._broadcast_on_rendezvous()

    def _broadcast_on_rendezvous(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        message = f"{self.user_id};{get_local_ip()}:{self.os_given_port}".encode()

        while True:
            if self.connection_running:
                server.close()
                break
            server.sendto(message, ("255.255.255.255",self.rendezvous_port))
            time.sleep(.2)

    def send(self, m: str):
        if self.client:
            self.client.send(m)
        elif self.server:
            self.server.send(m)
        else:
            print('unable to send because there is no connection to any sockets')

