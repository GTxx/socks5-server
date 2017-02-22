import socks
import socket


def create_udp_client():
    s = socks.socksocket(socket.AF_INET, socket.SOCK_DGRAM) # Same API as socket.socket in the standard lib
    # s.set_proxy(socks.SOCKS5, "192.168.1.102", 1084) # SOCKS4 and SOCKS5 use port 1080 by default
    s.set_proxy(socks.SOCKS5, "localhost", 1084) # SOCKS4 and SOCKS5 use port 1080 by default

    # Can be treated identical to a regular socket object
    # s.connect(("192.168.1.102", 26000))
    s.sendto(b'1234', ("192.168.1.102", 26000))
    res = s.recvfrom(100)
    print(res)
    s.close()

if __name__ == "__main__":
    create_udp_client()