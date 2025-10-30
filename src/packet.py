import struct
import hashlib

class PacketType:
    """Packet type flags"""
    DATA = 0x01
    ACK = 0x02
    FIN = 0x04
    SYN = 0x08

class Packet:
    """
    Packet structure for reliable data transfer
    
    Header Format (15 bytes):
    - Sequence Number: 4 bytes (unsigned int)
    - ACK Number: 4 bytes (unsigned int)
    - Flags: 1 byte (SYN, ACK, FIN, DATA)
    - Window Size: 2 bytes (unsigned short)
    - Data Length: 2 bytes (unsigned short)
    - Checksum: 2 bytes (unsigned short)
    
    Data: variable length
    """
    
    HEADER_FORMAT = '!IIBHHH'  
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, seq_num=0, ack_num=0, flags=0, window_size=0, data=b''):
        """
        Initialize a packet
        
        Args:
            seq_num: Sequence number
            ack_num: Acknowledgment number
            flags: Packet type flags (DATA, ACK, FIN, SYN)
            window_size: Receiver's window size
            data: Payload data (bytes)
        """
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.window_size = window_size
        self.data = data if isinstance(data, bytes) else data.encode()
        self.data_length = len(self.data)
        self.checksum = 0
    
    def calculate_checksum(self):
        """
        Calculate checksum for the packet (excluding checksum field)
        Uses simple sum-based checksum
        """
        header = struct.pack('!IIBHH', 
                           self.seq_num, 
                           self.ack_num, 
                           self.flags, 
                           self.window_size, 
                           self.data_length)
        
        content = header + self.data
        
        hash_obj = hashlib.md5(content)
        checksum = int.from_bytes(hash_obj.digest()[:2], byteorder='big')
        
        return checksum
    
    def serialize(self):
        """
        Convert packet to bytes for transmission
        
        Returns:
            bytes: Serialized packet
        """
        self.checksum = self.calculate_checksum()
        
        header = struct.pack(self.HEADER_FORMAT,
                           self.seq_num,
                           self.ack_num,
                           self.flags,
                           self.window_size,
                           self.data_length,
                           self.checksum)
        
        return header + self.data
    
    def deserialize(self, cls, raw_data):
        """
        Create packet from raw bytes
        
        Args:
            raw_data: Raw packet bytes
            
        Returns:
            Packet: Deserialized packet object, or None if invalid
        """
        if len(raw_data) < cls.HEADER_SIZE:
            return None
        
        try:
            seq_num, ack_num, flags, window_size, data_length, checksum = \
                struct.unpack(cls.HEADER_FORMAT, raw_data[:cls.HEADER_SIZE])
        except struct.error:
            return None
        
        data = raw_data[cls.HEADER_SIZE:cls.HEADER_SIZE + data_length]
        
        packet = cls(seq_num, ack_num, flags, window_size, data)
        packet.checksum = checksum
        
        return packet
    
    def is_corrupt(self):
        """Check if packet is corrupted by verifying checksum"""
        calculated_checksum = self.calculate_checksum()
        return calculated_checksum != self.checksum
    
    def is_ack(self):
        """Check if packet is an ACK packet"""
        return bool(self.flags & PacketType.ACK)
    
    def is_data(self):
        """Check if packet is a DATA packet"""
        return bool(self.flags & PacketType.DATA)
    
    def is_fin(self):
        """Check if packet is a FIN packet"""
        return bool(self.flags & PacketType.FIN)
    
    def is_syn(self):
        """Check if packet is a SYN packet"""
        return bool(self.flags & PacketType.SYN)
    
    def __str__(self):
        """String representation of packet for debugging"""
        flags_str = []
        if self.is_syn():
            flags_str.append('SYN')
        if self.is_ack():
            flags_str.append('ACK')
        if self.is_data():
            flags_str.append('DATA')
        if self.is_fin():
            flags_str.append('FIN')
        
        return (f"Packet(seq={self.seq_num}, ack={self.ack_num}, "
                f"flags=[{','.join(flags_str)}], window={self.window_size}, "
                f"data_len={self.data_length}, checksum={self.checksum})")
    
    def __repr__(self):
        return self.__str__()


def create_data_packet(type, seq_num, data, window_size=5):
    """Create a DATA packet"""
    return Packet(seq_num=seq_num, flags=PacketType.DATA, 
                 window_size=window_size, data=data)

def create_ack_packet(ack_num, window_size=5):
    """Create an ACK packet"""
    return Packet(ack_num=ack_num, flags=PacketType.ACK, 
                 window_size=window_size)

def create_syn_packet(seq_num=0):
    """Create a SYN packet for connection establishment"""
    return Packet(seq_num=seq_num, flags=PacketType.SYN)

def create_fin_packet(seq_num):
    """Create a FIN packet for connection termination"""
    return Packet(seq_num=seq_num, flags=PacketType.FIN)

def create_syn_ack_packet(seq_num, ack_num):
    """Create a SYN-ACK packet"""
    return Packet(seq_num=seq_num, ack_num=ack_num, 
                 flags=PacketType.SYN | PacketType.ACK)


# Test the packet implementation
if __name__ == "__main__":
    print("Testing Packet Implementation\n")
    
    # Test 1: Create and serialize a DATA packet
    print("Test 1: DATA Packet")
    data_packet = create_data_packet(seq_num=100, data="Hello, World!")
    print(f"Created: {data_packet}")
    
    serialized = data_packet.serialize()
    print(f"Serialized length: {len(serialized)} bytes")
    
    # Test 2: Deserialize packet
    print("\nTest 2: Deserialization")
    deserialized = Packet.deserialize(serialized)
    print(f"Deserialized: {deserialized}")
    print(f"Data: {deserialized.data.decode()}")
    print(f"Corrupt: {deserialized.is_corrupt()}")
    
    # Test 3: Corrupt packet
    print("\nTest 3: Corruption Detection")
    corrupted_data = bytearray(serialized)
    corrupted_data[20] ^= 0xFF  # Flip some bits in data
    corrupted_packet = Packet.deserialize(bytes(corrupted_data))
    print(f"Corrupted packet: {corrupted_packet}")
    print(f"Is corrupt: {corrupted_packet.is_corrupt()}")
    
    # Test 4: ACK packet
    print("\nTest 4: ACK Packet")
    ack_packet = create_ack_packet(ack_num=101)
    print(f"Created: {ack_packet}")
    print(f"Is ACK: {ack_packet.is_ack()}")
    
    # Test 5: SYN-ACK packet
    print("\nTest 5: SYN-ACK Packet")
    syn_ack = create_syn_ack_packet(seq_num=0, ack_num=1)
    print(f"Created: {syn_ack}")
    print(f"Is SYN: {syn_ack.is_syn()}")
    print(f"Is ACK: {syn_ack.is_ack()}")