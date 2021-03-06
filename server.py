import logging
from logging import NullHandler

import click
import curio
from curio import socket as cr_socket

from parser import unpack_connection, pack_connection_reply, \
    pack_udp_associate_reply, unpack_hand_shake, pack_hand_shake_server, \
    parse_udp_relay, pack_udp_relay


logging.getLogger(__name__).addHandler(NullHandler())
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name) -3s %(funcName)s %(lineno)d %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


CMD_CONNECT = 1
CMD_BIND = 2
CMD_UDP_ASSOCIATE = 3


SERVER_HOST = None
SERVER_PORT = None


async def upstream_copy(local_sock, remote_sock):
    while True:
        try:
            data = await local_sock.recv(1000)
        except ConnectionResetError as e:
            logger.debug("local_sock: {} is broken for: {}".format(local_sock, e))
            await remote_sock.shutdown(cr_socket.SHUT_RDWR)
            return

        if not data:
            try:
                await remote_sock.shutdown(cr_socket.SHUT_RDWR)
            except OSError as e:
                # if ConnectionResetError occur for remote_sock, remote_sock is
                # already not connected,
                logger.debug("shutdown remote_sock fail, e: {}".format(e))
            return
        else:
            await remote_sock.sendall(data)


async def downstream_copy(local_sock, remote_sock):
    while True:
        try:
            data = await remote_sock.recv(1000)
        except ConnectionResetError as e:
            logger.debug("remote_sock: {} is broken for: {}".format(remote_sock, e))
            await local_sock.shutdown(cr_socket.SHUT_RDWR)
            return

        if not data:
            try:
                await local_sock.shutdown(cr_socket.SHUT_RDWR)
            except OSError as e:
                logger.debug("shutdown local_sock fail, e: {}".format(e))
            return
        else:
            await local_sock.sendall(data)


async def bidirection_copy(source, dest):
    task1 = await curio.spawn(upstream_copy(source, dest))
    task2 = await curio.spawn(downstream_copy(source, dest))
    try:
        async for task in curio.wait([task1, task2]):
            await task.join()
    except curio.TaskCancelled:
        pass # fail silently if curio is shutdown
    except Exception as e:
        logger.debug("tcp proxy error: {}, source: {}, dest: {}".format(e, source, dest))
    finally:
        await task1.cancel()
        await task2.cancel()


async def socks5_handler(client: cr_socket, addr):
    """
    socks5 for handshake and establish connection
    :param client:
    :param addr:
    :return:
    """
    # handshake
    data = await client.recv(1000)
    if not data:
        return

    ver, nmethods, methods = unpack_hand_shake(data)
    hand_shake_reply = pack_hand_shake_server()
    await client.sendall(hand_shake_reply)

    # build connection
    data = await client.recv(1000)
    if not data:
        return
    ver, cmd, rsv, atyp, addr, port = unpack_connection(data)

    if cmd == CMD_CONNECT:
        connect_reply_data = pack_connection_reply()
        await client.sendall(connect_reply_data)

        # transfer
        async with client:
            try:
                tcp_sock = await curio.open_connection(addr, port)
            except Exception as e:
                logger.debug("tcp fail to connect addr: {} port{}, error: {}".format(addr, port, e))
                return

            async with tcp_sock:
                await bidirection_copy(client, tcp_sock)

    elif cmd == CMD_UDP_ASSOCIATE:
        connect_reply_data = pack_udp_associate_reply(SERVER_HOST, SERVER_PORT)
        await client.sendall(connect_reply_data)
        while True:
            data = await client.recv(1000)
            # print("udp associate, recv from tcp connection : ", data)
            if not data:
                break
            else:
                raise RuntimeError("don't know how to handle this data: ", data)

    print("-----------connection done--------------")


async def udp_relay(src_addr, data, server_sock):
    rsv, frag, atyp, dst_addr, dst_port, data = parse_udp_relay(data)
    sock = cr_socket.socket(cr_socket.AF_INET, cr_socket.SOCK_DGRAM)
    await sock.connect((dst_addr, dst_port))
    await sock.sendall(data)
    resp = await sock.recv(10000)
    reply_data = pack_udp_relay(atyp, dst_addr, dst_port, resp)
    await server_sock.sendto(reply_data, src_addr)


async def udp_relay_server(host, port):
    sock = cr_socket.socket(cr_socket.AF_INET, cr_socket.SOCK_DGRAM)
    sock.bind((host, port))
    while True:
        data, src_addr = await sock.recvfrom(10000)
        await curio.spawn(udp_relay(src_addr, data, sock))


async def socks5_server(host, port):
    # start handshake server
    await curio.spawn(curio.tcp_server(host, port, socks5_handler))

    # start udp server to relay udp data
    await curio.spawn(udp_relay_server(host, port))


@click.command()
@click.option('--host', default="127.0.0.1", help='socks5 server address.')
@click.option('--port', default=1082, help='socks5 server port.')
@click.option('--monitor', default=False, help="turn on curio monitor")
@click.option('--debug_log', default=False, help="turn on debug log")
def start(host, port, monitor, debug_log):
    global SERVER_HOST
    global SERVER_PORT
    SERVER_HOST = host
    SERVER_PORT = port
    if debug_log:
        logger.setLevel(logging.DEBUG)
    click.echo("socks5 server started!")
    curio.run(socks5_server(host, port), with_monitor=monitor)


if __name__ == '__main__':
    start()
