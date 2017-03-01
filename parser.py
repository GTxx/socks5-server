import struct


def unpack_hand_shake(data):
    """
    +----+----------+----------+
    | VER | NMETHODS | METHODS |
    +----+----------+----------+
    | 1 | 1 | 1 to 255 |
    +----+----------+----------+
    """
    parser = Parser(data)
    ver = parser.next_value(Uchar)
    nmethods = parser.next_value(Uchar)
    methods = parser.next_value(Uchar, nmethods)
    return ver, nmethods, methods


def pack_hand_shake_server():
    """
    +----+--------+
    | VER | METHOD |
    +----+--------+
    | 1 | 1 |
    +----+--------+
    """
    ver = 5
    method = 0
    packer = Packer()
    packer.append(Uchar, ver)
    packer.append(Uchar, method)
    return packer.data



def unpack_connection(data):
    """
    +----+-----+-------+------+----------+----------+
    | VER | CMD | RSV | ATYP | DST.ADDR | DST.PORT |
    +----+-----+-------+------+----------+----------+
    | 1 | 1 | X'00' | 1 | Variable | 2 |
    +----+-----+-------+------+----------+----------+
    """
    parser = Parser(data)
    ver = parser.next_value(Uchar)
    cmd = parser.next_value(Uchar)
    rsv = parser.next_value(Uchar)
    atyp = parser.next_value(Uchar)
    if atyp == 0x01: # ipv4
        addr = parser.next_value(Uchar, 4)
        dst_addr = '.'.join([str(i) for i in addr])
        dst_port = parser.next_value(Ushort)
    elif atyp == 0x03: # domain
        size = parser.next_value(Uchar)
        dst_addr = parser.next_value(String, size)
        dst_port = parser.next_value(Ushort)
    elif atyp == 0x04: # ipv6
        dst_addr = parser.next_value(Ushort, 16)
        dst_port = parser.next_value(Ushort)
    else:
        raise Exception("data format invalid: {}".format(data))
    return ver, cmd, rsv, atyp, dst_addr, dst_port


def pack_connection_reply():
    """
    +----+-----+-------+------+----------+----------+
    | VER | REP | RSV | ATYP | BND.ADDR | BND.PORT |
    +----+-----+-------+------+----------+----------+
    | 1 | 1 | X'00' | 1 | Variable | 2 |
    +----+-----+-------+------+----------+----------+
    """
    packer = Packer()
    ver = 5
    rep = 0 # success
    rsv = 0
    atyp = 1 # ipv4
    addr = [0, 0, 0, 0] # nonsense
    port = 1088 # nonsense
    packer.append(Uchar, ver)
    packer.append(Uchar, rep)
    packer.append(Uchar, rsv)
    packer.append(Uchar, atyp)
    packer.append(4, Uchar, addr)
    packer.append(Ushort, port)
    return packer.data


def parse_udp_relay(data):
    """
    +----+------+------+----------+----------+----------+
    | RSV | FRAG | ATYP | DST.ADDR | DST.PORT | DATA |
    +----+------+------+----------+----------+----------+
    | 2 | 1 | 1 | Variable | 2 | Variable |
    +----+------+------+----------+----------+----------+
    """
    parser = Parser(data)
    rsv = parser.next_value(Ushort)
    frag = parser.next_value(Uchar)
    atyp = parser.next_value(Uchar)
    if atyp == 0x01:
        addr = parser.next_value(Uchar, 4)
        dst_addr = '.'.join([str(i) for i in addr])
        dst_port = parser.next_value(Ushort)
    elif atyp == 0x03:
        size = parser.next_value(Uchar)
        dst_addr = parser.next_value(String, size)
        dst_port = parser.next_value(Ushort)
    elif atyp == 0x04:
        # TODO: ipv6
        pass
    data = parser.rem_data()
    return rsv, frag, atyp, dst_addr, dst_port, data


def pack_udp_relay(atyp, dst_addr, dst_port, data):
    """
    +----+------+------+----------+----------+----------+
    | RSV | FRAG | ATYP | DST.ADDR | DST.PORT | DATA |
    +----+------+------+----------+----------+----------+
    | 2 | 1 | 1 | Variable | 2 | Variable |
    +----+------+------+----------+----------+----------+
    """
    packer = Packer()
    packer.append(Ushort, 0)
    packer.append(Uchar, 0)
    packer.append(Uchar, atyp)
    addr = [int(i) for i in dst_addr.split(".")]
    packer.append(4, Uchar, addr)
    packer.append(Ushort, dst_port)
    return packer.data + data


def pack_udp_associate_reply(addr, port):
    packer = Packer()
    ver = 5
    rep = 0
    rsv = 0
    atyp = 1
    packer.append(Uchar, ver)
    packer.append(Uchar, rep)
    packer.append(Uchar, rsv)
    packer.append(Uchar, atyp)
    packer.append(4, Uchar, [int(i) for i in addr.split(".")])
    packer.append(Ushort, port)
    return packer.data


class Field:
    def __init__(self, format, size):
        self.format = format
        self.size = size


Char = Field("b", size=1)
Uchar = Field("B", size=1)
Short = Field("h", size=2)
Ushort = Field('H', size=2)
String = Field('s', size=1)


class Parser:
    def __init__(self, data, byte_order="network"):
        self.data = data
        self.idx = 0
        if byte_order == "little":
            self.prefix = "<"
        elif byte_order == "big":
            self.prefix = ">"
        elif byte_order == "network":
            self.prefix = "!"
        else:
            raise RuntimeError("byte order {} not support".format(byte_order))

    def next_value(self, field, num=1):
        format = self.prefix + "{}{}".format(num, field.format)
        idx = self.idx
        res = struct.unpack(format, self.data[idx: idx+field.size*num])
        self.idx += field.size * num
        if field in (String, ):
            return res[0]
        else:
            if num == 1:
                return res[0]
            else:
                return res

    def rem_data(self):
        return self.data[self.idx: ]


class Packer:
    def __init__(self):
        self.data = b''

    def append(self, *field_data):
        if len(field_data) == 2:
            num = 1
            field, data = field_data
            self.data += struct.pack("!{}{}".format(num, field.format), data)
        elif len(field_data) == 3:
            num, field, data = field_data
            self.data += struct.pack("!{}{}".format(num, field.format), *data)


if __name__ == "__main__":
    print(pack_hand_shake_server())
    print(pack_connection_reply())
