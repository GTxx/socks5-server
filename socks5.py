# ssh -N -D 0.0.0.0:1082 server.com
# 可以在 localhost：1082建立一个socks5服务器，流量会被转发到server.com, 然后再转发到最终目的地，
# 返回的流量会返回给localhost:1082，并最终返回给客户端。
# client <-> localhost:1082 <-> server.com <-> 目的地

import curio
import struct
from curio import socket as cr_socket

async def udp_relay():
    sock = cr_socket.socket(cr_socket.AF_INET)

HAND_SHAKE_CLIENT = (('VER', 'b'), ('NMETHODS', 'b'), ('METHODS', 's'))
HAND_SHAKE_CLIENT_FORMAT = ''.join([format for name, format in HAND_SHAKE_CLIENT])

def unpack_hand_shake(data):
    hand_shake_format = 'BB'
    ver, nmethods = struct.unpack(hand_shake_format, data[:2])
    methods = struct.unpack(("B"*nmethods).format(nmethods), data[2:])
    return ver, nmethods, methods


def pack_hand_shake_server():
    ver = 5
    method  = 0
    format = 'BB'
    return struct.pack(format, ver, method)


def unpack_connection(data):
    connection_format = 'BBBB'
    ver, cmd, rsv, atyp = struct.unpack(connection_format, data[:4])
    port_format = '!H'
    if atyp == 0x01: # ipv4
        ipv4_format = 'B' * 4
        addr = struct.unpack(ipv4_format, data[4: 8])
        addr = '.'.join([str(i) for i in addr])
        (port, ) = struct.unpack(port_format, data[8:])
    elif atyp == 0x03: # domain
        (addr_length, ) = struct.unpack('B', data[4:5])
        (addr, ) = struct.unpack('{}s'.format(addr_length), data[5: 5+addr_length])
        print(addr)
        (port, ) = struct.unpack(port_format, data[5+addr_length:])
    elif atyp == 0x04: # ipv6
        ipv6_format = 'B' * 16
        addr = struct.unpack(ipv6_format, data[4: 20])
        (port, ) = struct.unpack(port_format, data[20:])
    else:
        raise Exception("data format invalid: {}".format(data))
    return ver, cmd, rsv, atyp, addr, port


def pack_connection_reply():
    format = 'BBBB4BH'
    ver = 5
    rep = 0 # success
    rsv = 0
    atyp = 1 # ipv4
    addr = [0, 0, 0, 0] # nonsense
    port = 1088 # nonsense
    return struct.pack(format, ver, rep, rsv, atyp, *addr, port)

from curio.io import Socket

async def copy(source, dest):
    while True:
        data = await source.recv(1000)
        if not data:
            break
        await dest.sendall(data)

async def bidirection_copy(source, dest):
    task1 = await curio.spawn(copy(source, dest))
    task2 = await curio.spawn(copy(dest, source))
    await task1.join()
    await task2.join()

async def socks5_client_task(client: Socket, addr):
    """
    socks5 for handshake and establish connection
    :param client:
    :param addr:
    :return:
    """
    # handshake
    print("start tcp connection")
    data = await client.recv(1000)
    print(data)
    ver, nmethods, methods = unpack_hand_shake(data)
    print("ver: {}, nmethods: {}, methods: {}".format(ver, nmethods, methods))
    if not data:
        return
    else:
        hand_shake_reply = pack_hand_shake_server()
        await client.sendall(hand_shake_reply)

    # build connection
    data = await client.recv(1000)
    print(data)
    ver, cmd, rsv, atyp, addr, port = unpack_connection(data)
    print("ver: {}, cmd: {}, rsv: {}, atyp: {}, addr: {}, port: {}".format(
        ver, cmd, rsv, atyp, addr, port
    ))
    if not data:
        return
    else:
        connect_reply_data = pack_connection_reply()
        await client.sendall(connect_reply_data)

    # transfer
    tcp_sock = await curio.open_connection(addr, port)
    async with tcp_sock:
        await bidirection_copy(client, tcp_sock)
        # while True:
        #     # socks5_client(browser) <-> client <-> internet
        #     print('wait browser send data')
        #     data = await client.recv(1000)
        #     print('source data:{}'.format(data))
        #     if not data:
        #         break
        #     await tcp_sock.sendall(data)
        #     data_from_out = await tcp_sock.recv(1000)
        #     print(data_from_out)
        #     await client.sendall(data_from_out)
        #     print("write done")
    print("-----------connection done--------------")


async def tcp_relay(host, port):
    server = await curio.tcp_server(host, port, socks5_client_task)
    print("tcp server started")


if __name__ == "__main__":
    curio.run(tcp_relay('localhost', 1082))