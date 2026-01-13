import socket, threading, typing
import time

from cryptography.fernet import Fernet

class EasySocketServer:
    def __init__(self, host_ip: str = "localhost", port: int = 50505, on_receive: typing.Optional[typing.Callable[[str, typing.Optional[bytes]], None]] = None, ipv4_or_6: int = 4):
        self.receive_function = on_receive
        self.ip = host_ip
        self.port = port
        self.conn = None
        self._running = True
        self.f = Fernet('key')
        self.ipv4_or_6 = ipv4_or_6

    def start(self):

        self._start_tcp_connection()

        t1 = threading.Thread(target=self._accept_receive)
        t1.start()

    def send(self, message):
        if self.conn and self._running:

            self.conn.sendall(self.f.encrypt(message.encode()))
        else:
            print("Error: No client connected")

    def get_port(self):
        return self.tcp_server_socket.getsockname()[1]

    def _accept_receive(self):
        self.conn, self.client_address = self.tcp_server_socket.accept()

        while self._running:
            data = self.conn.recv(1024)
            if not data:
                break
            if self.receive_function:
                self.receive_function(self.f.decrypt(data).decode(), self.f.decrypt(data))

    def _start_tcp_connection(self):
        if self.ipv4_or_6 == 4:
            self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif self.ipv4_or_6 == 6:
            self.tcp_server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            print("Error, please input either 4 or 6 into ipv4_or_6 parameter.")
            quit()

        server_address = (self.ip, self.port)

        self.tcp_server_socket.bind(server_address)

        print("waiting for client connection...")
        self.port = self.tcp_server_socket.getsockname()[1]

        print(self.port)

        self.tcp_server_socket.listen(1)

    def close(self):
        self._running = False
        if self.conn:
            self.conn.close()
        if self.tcp_server_socket:
            self.tcp_server_socket.close()

class EasySocketClient:
    def __init__(self, host_ip: str = "localhost", port: int = 50505, on_receive: typing.Optional[typing.Callable[[str, typing.Optional[bytes]], None]] = None, ipv4_or_6: int = 4):
        self.receive_function = on_receive
        self.ip = host_ip
        self.port = port
        self._running = True
        self.f = Fernet('key')
        self.ipv4_or_6 = ipv4_or_6

    def start(self):
        self._start_tcp_connection()

        self.t1 = threading.Thread(target=self._accept_receive)
        self.t1.start()


    def send(self, message):
        if self.tcp_client_socket and self._running:
            self.tcp_client_socket.sendall(self.f.encrypt(message.encode()))
        else:
            print("Error: No server connected")

    def _accept_receive(self):
        while self._running:
            if self.tcp_client_socket:
                data = self.tcp_client_socket.recv(1024)
                if not data:
                    break
                if self.receive_function:
                    self.receive_function(self.f.decrypt(data).decode(), self.f.decrypt(data))

    def _start_tcp_connection(self):
        if self.ipv4_or_6 == 4:
            self.tcp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif self.ipv4_or_6 == 6:
            self.tcp_client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            print("Error, please input either 4 or 6 into ipv4_or_6 parameter.")
            quit()

        server_address = (self.ip, self.port)

        try:
            self.tcp_client_socket.connect(server_address)
        except ConnectionRefusedError:
            print("Server is not open on this port")
            self._running = False

        self.port = self.tcp_client_socket.getsockname()[1]

        #print(self.port)

    def close(self):
        self._running = False
        if self.tcp_client_socket:
            self.tcp_client_socket.close()

class EasySocketPeerWithUDPBroadcasting:
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
        self.client: EasySocketClient
        self.server: EasySocketServer

        self._read_rendezvous_to_find_peer_udp()

    def _read_rendezvous_to_find_peer_udp(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        client.bind(("0.0.0.0",self.rendezvous_port))

        search_start_time = time.time()

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
        def on_receive(m, b):
            self.on_message_func(m)

        self.client = EasySocketClient(self.peer_ip, self.peer_port, on_receive)
        self.client.start()

        self.client.send(f"connected:{self.user_id}")

    def _host_server_on_given_port(self):
        def on_receive(m, b):
            if m == f"connected:{self.peer_id}":
                self.connection_running = True
                print("connection success, stopping broadcast.")
            self.on_message_func(m)

        self.server = EasySocketServer(get_local_ip(), 0, on_receive)
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


#############################################################

def get_local_ip():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        client.connect(("1.1.1.1",53))
        return client.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())
