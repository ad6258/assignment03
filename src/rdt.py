import socket
import threading
import time
import queue
from packet import Packet, PacketType, create_data_packet, create_ack_packet, create_syn_packet, create_fin_packet

class RDTSender:
    """
    Reliable Data Transfer - Sender Side
    Implements sliding window protocol with timeouts and retransmissions
    """
    
    def __init__(self, sock, dest_addr, window_size=5, timeout=2.0, max_packet_size=1024):
        """
        Initialize RDT Sender
        
        Args:
            sock: UDP socket to use for sending
            dest_addr: Destination address (host, port)
            window_size: Maximum number of unacknowledged packets
            timeout: Timeout value in seconds for retransmission
            max_packet_size: Maximum size of data per packet
        """
        self.sock = sock
        self.dest_addr = dest_addr
        self.window_size = window_size
        self.timeout = timeout
        self.max_packet_size = max_packet_size
        
        # Sequence number management
        self.seq_num = 0
        self.base = 0  # Oldest unacknowledged packet
        self.next_seq_num = 0  # Next sequence number to send
        
        # Window management
        self.send_buffer = {}  # {seq_num: (packet, timestamp)}
        self.acks_received = set()
        
        # Thread control
        self.running = False
        self.ack_thread = None
        self.timer_thread = None
        self.lock = threading.Lock()
        
        # Statistics
        self.packets_sent = 0
        self.retransmissions = 0
        self.acks_received_count = 0
        
    def start(self):
        """Start the sender (begin listening for ACKs)"""
        self.running = True
        self.ack_thread = threading.Thread(target=self._receive_acks, daemon=True)
        self.ack_thread.start()
        self.timer_thread = threading.Thread(target=self._check_timeouts, daemon=True)
        self.timer_thread.start()
        print("[Sender] Started")
    
    def stop(self):
        """Stop the sender"""
        self.running = False
        if self.ack_thread:
            self.ack_thread.join(timeout=1)
        if self.timer_thread:
            self.timer_thread.join(timeout=1)
        print(f"[Sender] Stopped. Stats: Sent={self.packets_sent}, Retrans={self.retransmissions}, ACKs={self.acks_received_count}")
    
    def send_data(self, data):
        """
        Send data reliably
        
        Args:
            data: Bytes to send
        """
        # Split data into chunks
        chunks = [data[i:i+self.max_packet_size] for i in range(0, len(data), self.max_packet_size)]
        
        print(f"[Sender] Sending {len(data)} bytes in {len(chunks)} packets")
        
        for chunk in chunks:
            # Wait until window has space
            while True:
                with self.lock:
                    if self.next_seq_num < self.base + self.window_size:
                        break
                time.sleep(0.01)
            
            # Create and send packet
            packet = create_data_packet(self.next_seq_num, chunk, self.window_size)
            self._send_packet(packet)
            
            with self.lock:
                self.send_buffer[self.next_seq_num] = (packet, time.time())
                self.next_seq_num += 1
            
            # Very small delay to avoid flooding
            time.sleep(0.01)
        
        # Wait for all ACKs
        print("[Sender] Waiting for all ACKs...")
        while True:
            with self.lock:
                if self.base >= self.next_seq_num:
                    break
            time.sleep(0.1)
        
        print("[Sender] All data acknowledged")
    
    def _send_packet(self, packet):
        """Send a packet through the socket"""
        try:
            self.sock.sendto(packet.serialize(), self.dest_addr)
            self.packets_sent += 1
            print(f"[Sender] Sent packet seq={packet.seq_num}, size={packet.data_length}")
        except Exception as e:
            print(f"[Sender] Error sending packet: {e}")
    
    def _receive_acks(self):
        """Thread function to receive ACKs"""
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, _ = self.sock.recvfrom(2048)
                packet = Packet.deserialize(data)
                
                if packet and packet.is_ack() and not packet.is_corrupt():
                    self._handle_ack(packet)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Sender] Error receiving ACK: {e}")
    
    def _handle_ack(self, ack_packet):
        """Handle received ACK packet"""
        ack_num = ack_packet.ack_num
        
        with self.lock:
            print(f"[Sender] Received ACK={ack_num}")
            self.acks_received_count += 1
            
            # Cumulative ACK: all packets up to ack_num are acknowledged
            if ack_num >= self.base:
                # Remove acknowledged packets from buffer
                for seq in range(self.base, ack_num + 1):
                    if seq in self.send_buffer:
                        del self.send_buffer[seq]
                
                self.base = ack_num + 1
                print(f"[Sender] Window moved: base={self.base}, next={self.next_seq_num}")
    
    def _check_timeouts(self):
        """Thread function to check for timeouts and retransmit"""
        while self.running:
            time.sleep(0.1)  # Check every 100ms
            
            current_time = time.time()
            with self.lock:
                packets_to_retransmit = []
                
                for seq_num, (packet, timestamp) in list(self.send_buffer.items()):
                    if current_time - timestamp > self.timeout:
                        packets_to_retransmit.append((seq_num, packet))
                
                # Retransmit timed-out packets
                for seq_num, packet in packets_to_retransmit:
                    print(f"[Sender] TIMEOUT: Retransmitting seq={seq_num}")
                    self._send_packet(packet)
                    self.send_buffer[seq_num] = (packet, time.time())
                    self.retransmissions += 1


class RDTReceiver:
    """
    Reliable Data Transfer - Receiver Side
    Handles receiving packets, reordering, and sending ACKs
    """
    
    def __init__(self, sock, window_size=5):
        """
        Initialize RDT Receiver
        
        Args:
            sock: UDP socket to use for receiving
            window_size: Maximum receive window size
        """
        self.sock = sock
        self.window_size = window_size
        
        # Sequence number management
        self.expected_seq_num = 0
        
        # Receive buffer for out-of-order packets
        self.receive_buffer = {}  # {seq_num: packet}
        
        # Data queue for application layer
        self.data_queue = queue.Queue()
        
        # Thread control
        self.running = False
        self.receive_thread = None
        self.lock = threading.Lock()
        
        # Statistics
        self.packets_received = 0
        self.acks_sent = 0
        self.duplicates_received = 0
        
    def start(self):
        """Start the receiver"""
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_packets, daemon=True)
        self.receive_thread.start()
        print("[Receiver] Started")
    
    def stop(self):
        """Stop the receiver"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        print(f"[Receiver] Stopped. Stats: Received={self.packets_received}, ACKs={self.acks_sent}, Duplicates={self.duplicates_received}")
    
    def receive_data(self):
        """
        Get received data from queue
        
        Returns:
            bytes: Received data, or None if no data available
        """
        try:
            return self.data_queue.get(timeout=0.1)
        except queue.Empty:
            return None
    
    def receive_all_data(self, timeout=60):
        """
        Receive all data until timeout or connection closed
        
        Args:
            timeout: Maximum time to wait for data
            
        Returns:
            bytes: All received data concatenated
        """
        all_data = b''
        last_activity_time = time.time()  # Track ANY activity (not just delivery)
        consecutive_empty_reads = 0
        
        while time.time() - last_activity_time < timeout:
            # Check if any packets were received recently
            with self.lock:
                current_packets_received = self.packets_received
            
            data = self.receive_data()
            if data:
                all_data += data
                last_activity_time = time.time()
                consecutive_empty_reads = 0
                print(f"[Receiver] Accumulated {len(all_data)} bytes so far")
            else:
                # Check if receiver thread is still receiving packets (even if not delivered)
                with self.lock:
                    if current_packets_received < self.packets_received:
                        # Packets are still arriving, reset timer
                        last_activity_time = time.time()
                        consecutive_empty_reads = 0
                    else:
                        consecutive_empty_reads += 1
                
                # Only timeout if BOTH no data delivered AND no packets arriving
                if consecutive_empty_reads > 200 and len(all_data) > 0:
                    print(f"[Receiver] No activity for 20 seconds, transfer complete")
                    break
            
            time.sleep(0.1)
        
        return all_data
        
    def _receive_packets(self):
        """Thread function to receive packets"""
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, sender_addr = self.sock.recvfrom(2048)
                packet = Packet.deserialize(data)
                
                if packet and packet.is_data():
                    self._handle_data_packet(packet, sender_addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Receiver] Error receiving packet: {e}")
    
    def _handle_data_packet(self, packet, sender_addr):
        """Handle received data packet"""
        # Check for corruption
        if packet.is_corrupt():
            print(f"[Receiver] Corrupted packet seq={packet.seq_num}, discarding")
            return
        
        seq_num = packet.seq_num
        
        with self.lock:
            print(f"[Receiver] Received packet seq={seq_num}, expected={self.expected_seq_num}")
            self.packets_received += 1
            
            # Check if duplicate
            if seq_num < self.expected_seq_num:
                print(f"[Receiver] Duplicate packet seq={seq_num}")
                self.duplicates_received += 1
                # Send ACK anyway (might have been lost)
                # For duplicates, ACK the last successfully received packet
                ack_num = max(0, self.expected_seq_num - 1)
                self._send_ack(ack_num, sender_addr)
                return
            
            # Store packet in buffer
            self.receive_buffer[seq_num] = packet
            
            # Deliver in-order packets to application
            while self.expected_seq_num in self.receive_buffer:
                pkt = self.receive_buffer[self.expected_seq_num]
                self.data_queue.put(pkt.data)
                del self.receive_buffer[self.expected_seq_num]
                print(f"[Receiver] Delivered packet seq={self.expected_seq_num} to application")
                self.expected_seq_num += 1
            
            # Send cumulative ACK for the last in-order packet received
            # ACK number is the last packet successfully delivered
            ack_num = max(0, self.expected_seq_num - 1)
            self._send_ack(ack_num, sender_addr)
    
    def _send_ack(self, ack_num, dest_addr):
        """Send ACK packet"""
        try:
            # Make sure ack_num is non-negative
            if ack_num < 0:
                ack_num = 0
            
            ack_packet = create_ack_packet(ack_num, self.window_size)
            self.sock.sendto(ack_packet.serialize(), dest_addr)
            self.acks_sent += 1
            print(f"[Receiver] Sent ACK={ack_num}")
        except Exception as e:
            print(f"[Receiver] Error sending ACK: {e}")

# Example usage and testing
if __name__ == "__main__":
    # Test sender and receiver
    print("Testing RDT Protocol\n")
    
    # Create sockets
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Bind receiver
    receiver_addr = ('localhost', 9999)
    receiver_sock.bind(receiver_addr)
    
    # Create sender and receiver
    sender = RDTSender(sender_sock, receiver_addr, window_size=5, timeout=1.0)
    receiver = RDTReceiver(receiver_sock, window_size=5)
    
    # Start both
    receiver.start()
    sender.start()
    
    # Send test data
    test_data = b"Hello, this is a test of the reliable data transfer protocol! " * 20
    print(f"\nSending {len(test_data)} bytes \n")
    
    sender.send_data(test_data)
    
    # Receive data
    print("\nReceiving data\n")
    time.sleep(2)  # Wait for all data
    received_data = receiver.receive_all_data(timeout=5)
    
    # Verify
    print(f"\nReceived {len(received_data)} bytes")
    print(f"Data matches: {test_data == received_data}")
    
    # Cleanup
    sender.stop()
    receiver.stop()
    sender_sock.close()
    receiver_sock.close()