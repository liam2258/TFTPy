import argparse
from socket import *
import filecmp

parser = argparse.ArgumentParser(description='Uses TFTP over UDP to send or receive file')
parser.add_argument('-m', '--mode', help='mode of either reading or writing', required=True, type=str)
parser.add_argument('-a', '--address', help='remote host/server to communicate with', required=True)
parser.add_argument('-p', '--clientport', help='locate client port to use (default 5025)', type=int, required=True)
parser.add_argument('-sp', '--serverport', help='local server port to use', type=int, required=True)
parser.add_argument('-f', '--filename', help='name of file', type=str, required=True)
args = parser.parse_args()  
if args.mode != 'r' and args.mode != 'w':
    print("invalid value for 'mode' flag. Must use 'r' (read) or 'w' (write).\n" + "Please try again")
    exit()
elif args.clientport < 5000 or args.clientport > 65535 or args.serverport < 5000 or args.serverport > 65535:
    print("port range is restricted to 5000 and 65535, inclusive \n" + "Please try again")
    exit()

clientSocket = socket(AF_INET, SOCK_DGRAM)

filename = args.filename

data = ''

def shut_down():
    clientSocket.close()
    exit()

def build_error_packet(errorCode, variable):
    packet = bytearray()

    packet.append(0)
    packet.append(5)
    packet.append(0)
    packet.append(errorCode)

    variable = bytearray(variable.encode('utf-8'))
    packet += variable
    packet.append(0)

    return packet


def build_request_packet(filename, mode, opcode):
    packet = bytearray()

    #add opcode
    packet.append(0)
    packet.append(opcode)

    #encode and add filename
    filename = bytearray(filename.encode('utf-8'))
    packet += filename
    
    #add null terminator
    packet.append(0)

    #add the mode of transfer
    form = bytearray(bytes(mode, 'utf-8'))
    packet += form

    #add null terminator
    packet.append(0)

    return packet

def build_rrq(filename, mode):
    opcode = 1
    return build_request_packet(filename, mode, opcode)

def build_wrq(filename, mode):
    opcode = 2
    return build_request_packet(filename, mode, opcode)

def build_ack(byte1, byte2):
    ack = bytearray()
    ack.append(0)
    ack.append(4)
    ack.append(byte1)
    ack.append(byte2)
    return ack

def unpack_DATA(filename, packet):

    opcode = packet[1]
    block = [packet[2], packet[3]]
    j = 4
    data = bytearray()
    if len(packet) < 5:
        with open(filename, 'ba') as file_object:
            file_object.close()
    
    else:
        while j < len(packet):
            data.append(packet[j])
            j = j + 1

        with open(filename, 'ba') as file_object:
            file_object.write(data)

    file_object.close()

    return opcode, block, data

def send_first_packet(packet):
    modifiedMessage = ''
    serverAddress = ''
    flag = True
    x = 0
    while flag and x < 20:
        try:
            clientSocket.sendto(packet, (args.address, args.serverport))
            clientSocket.settimeout(10)
            modifiedMessage, serverAddress = clientSocket.recvfrom(1024)
            if len(modifiedMessage) < 2:
                error = build_error_packet(4, 'Invalid packet size: Too small')
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            if len(modifiedMessage) > 516:
                error = build_error_packet(4, 'Invalid packet size: Too large')
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            if modifiedMessage[1] == 5:
                print('Received error, shutting down')
                shut_down()
            if modifiedMessage[1] != 1 and modifiedMessage[1] != 2 and modifiedMessage[1] != 3 and modifiedMessage[1] != 4 and modifiedMessage[1] != 5:
                error = build_error_packet(4, 'Invalid op code')
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            flag = False
        except timeout:
            x += 1
        if x == 20:
            print('unable to connect, shutting down')
            shut_down()
    return modifiedMessage, serverAddress

def send_packet(packet, Address):
    modifiedMessage = ''
    serverAddress = ''
    flag = True
    x = 0
    while flag and x != 20:
        try:
            clientSocket.sendto(packet, (args.address, args.serverport))
            clientSocket.settimeout(10)
            modifiedMessage, serverAddress = clientSocket.recvfrom(1024)
            if len(modifiedMessage) < 2 and serverAddress == Address:
                error = build_error_packet(4, 'Invalid packet size: Too small')
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            if len(modifiedMessage) > 516:
                error = build_error_packet(4, 'Invalid packet size: Too large')
            if modifiedMessage[1] == 5:
                print('Received error, shutting down')
                shut_down()
            if modifiedMessage[1] != 1 and modifiedMessage[1] != 2 and modifiedMessage[1] != 3 and modifiedMessage[1] != 4 and modifiedMessage[1] != 5 and serverAddress == Address:
                error = build_error_packet(4, 'Invalid op code')
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            while serverAddress != Address:
                error = build_error_packet(5, 'Wrong port')
                clientSocket.sendto(error, (serverAddress[0], serverAddress[1]))
                modifiedMessage, serverAddress = clientSocket.recvfrom(1024)
            flag = False
        except timeout:
            x += 1
        if x == 20:
            print('unable to connect, shutting down')
            shut_down()
    return modifiedMessage

def create_data(filename):
    with open(filename) as f:
        content = f.read()

    content = bytearray(content.encode('utf-8'))

    dataPackets = []
    dataPacket = bytearray()

    y = 0
    x = 0

    while x < len(content):
        while y != 512 and x < len(content):
            dataPacket.append(content[x])
            y += 1
            x += 1
        y = 0
        dataPackets.append(dataPacket)
        dataPacket = bytearray()

    y = 0
    x = 1

    Packets = []
    Packet = bytearray()

    for count, data in enumerate(dataPackets):
        Packet = bytearray()
        Packet.append(0)
        Packet.append(3)
        if x > 255:
            y += 1
            x = 0
        Packet.append(y)
        Packet.append(x)
        Packets.append(Packet + dataPackets[count])
        x += 1

    if len(Packets) > 1 and len(Packets[-1]) == 516:
        Packet = bytearray()
        Packet.append(0)
        Packet.append(3)
        Packet.append(0)
        Packet.append(0)
        Packets.append(Packet)
    return Packets

if __name__ == '__main__':
    prev_block = 0

    if args.mode == 'r':

        packet = build_rrq(filename, 'netascii')

        modifiedMessage, serverAddress = send_first_packet(packet)
        opcode, block, data = unpack_DATA(filename, modifiedMessage)

        while len(modifiedMessage) == 516:
            ack = build_ack(block[0], block[1])
            modifiedMessage = send_packet(ack, serverAddress)
            if modifiedMessage[3] > block[1] + 1 or (modifiedMessage[2] > block[0] and modifiedMessage[3] != 0):
                error = build_error_packet(4, "Out of sequence Error")
                clientSocket.sendto(error, (args.address, args.serverport))
                shut_down()
            if block[0] != modifiedMessage[2] or block[1] != modifiedMessage[3]:
                opcode, block, data = unpack_DATA(filename, modifiedMessage)
        if len(modifiedMessage) != 516:
            ack = build_ack(block[0], block[1])
            clientSocket.sendto(ack, (args.address, args.serverport))

    if args.mode == 'w':
        content = ''
        packet = build_wrq(filename, 'netascii')

        packets = create_data(filename)

        ack, serverAddress = send_first_packet(packet)

        for data in packets:
            ack = send_packet(data, serverAddress)
            while ack[2] != data[2] or ack[3] != data[3]:
                ack = send_packet(data, serverAddress)

clientSocket.close()