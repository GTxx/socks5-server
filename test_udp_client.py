import socks
import socket


DST_ADDR = '192.168.1.102'
DST_PORT = '26000'


def send_udp_in_socks5():
    s = socks.socksocket(socket.AF_INET, socket.SOCK_DGRAM) # Same API as socket.socket in the standard lib
    s.set_proxy(socks.SOCKS5, "localhost", 1082)

    # Can be treated identical to a regular socket object
    s.sendto(b'1234', ("192.168.1.102", 26000))
    resp = s.recvfrom(10000)
    print("get response: ", resp)
    s.close()


if __name__ == "__main__":
    send_udp_in_socks5()