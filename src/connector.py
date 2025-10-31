import socket
import random
import time
import argparse
import threading
from packet import Packet

class NetworkConnector:
    """
    Network Connector - Acts as intermediary between client and server
    Simulates packet loss, delay, reordering, and corruption
    """
    
    def __init__(self, client_port, server_port, server_host='localhost',
                 loss_rate=0.0, corruption_rate=0.0, delay_range=(0, 0), reorder_rate=0.0):
        """
        Initialize Network Connector
        
        Args:
            client_port: Port to listen for client packets
            server_port: Port to forward packets to server
            server_host: Server hostname
            loss_rate: Probability of packet loss (0.0 to 1.0)
            corruption_rate: Probability of packet corruption (0.0 to 1.0)
            delay_range: Tuple of (min_delay, max_delay) in seconds
            reorder_rate: Probability of packet reordering (0.0 to 1.0)
        """
        self.client_port = client_port
        self.server_port = server_port
        self.server_host = server_host
        self.server_addr = (server_host, server_port)
        
        self.loss_rate = loss_rate
        self.corruption_rate = corruption_rate
        self.delay_range = delay_range
        self.reorder_rate = reorder_rate
        
        self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_sock.bind(('0.0.0.0', client_port))
        
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.reorder_buffer = []
        self.reorder_lock = threading.Lock()
        
        # Statistics
        self.packets_received = 0
        self.packets_forwarded = 0
        self.packets_dropped = 0
        self.packets_corrupted = 0
        self.packets_delayed = 0
        self.packets_reordered = 0
        
        self.running = False
        
    def start(self):
        """Start the Connector"""
        self.running = True
        
        # Thread for client -> server
        self.client_thread = threading.Thread(target=self._forward_client_to_server, daemon=True)
        self.client_thread.start()
        
        # Thread for server -> client
        self.server_thread = threading.Thread(target=self._forward_server_to_client, daemon=True)
        self.server_thread.start()
        
        self.delay_thread = threading.Thread(target=self._process_reorder_buffer, daemon=True)
        self.delay_thread.start()
        
        print(f"START")
        print(f"Client Port: {self.client_port}")
        print(f"Server: {self.server_host}:{self.server_port}")
        print(f"Loss Rate: {self.loss_rate * 100:.1f}%")
        print(f"Corruption Rate: {self.corruption_rate * 100:.1f}%")
        print(f"Delay Range: {self.delay_range[0]:.2f}s - {self.delay_range[1]:.2f}s")
        print(f"Reorder Rate: {self.reorder_rate * 100:.1f}%")
    
    def stop(self):
        """Stop the Connector"""
        self.running = False
        self.client_sock.close()
        self.server_sock.close()
        
        print(f"\nSTATISTICS:")
        print(f"Packets Received: {self.packets_received}")
        print(f"Packets Forwarded: {self.packets_forwarded}")
        print(f"Packets Dropped: {self.packets_dropped}")
        print(f"Packets Corrupted: {self.packets_corrupted}")
        print(f"Packets Delayed: {self.packets_delayed}")
        print(f"Packets Reordered: {self.packets_reordered}")
    
    def _forward_client_to_server(self):
        """Forward packets from client to server"""
        print("[Connector] Listening for client packets")
        
        while self.running:
            try:
                self.client_sock.settimeout(1.0)
                data, client_addr = self.client_sock.recvfrom(4096)
                self.packets_received += 1
                
                # Store client address for return path
                self.client_addr = client_addr
                
                # Process packet with network conditions
                self._process_packet(data, self.server_addr, self.server_sock, "C->S")
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Connector] Error in client->server: {e}")
    
    def _forward_server_to_client(self):
        """Forward packets from server to client"""
        
        while self.running:
            try:
                self.server_sock.settimeout(1.0)
                data, server_addr = self.server_sock.recvfrom(4096)
                self.packets_received += 1
                
                # Forward to client
                if hasattr(self, 'client_addr'):
                    self._process_packet(data, self.client_addr, self.client_sock, "S->C")
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Connector] Error in server->client: {e}")
    
    def _process_packet(self, data, dest_addr, sock, direction):
        """
        Process packet with network impairments
        
        Args:
            data: Packet data
            dest_addr: Destination address
            sock: Socket to send through
            direction: "C->S" or "S->C" for logging
        """
        # Parse packet for logging
        try:
            packet = Packet.deserialize(data)
            if packet:
                if packet.is_data():
                    packet_info = f"seq={packet.seq_num}"
                elif packet.is_ack():
                    packet_info = f"ack={packet.ack_num}"
                else:
                    packet_info = "unknown"
            else:
                packet_info = "invalid"
        except Exception as e:
            packet_info = f"parse_error"
        
        # Simulate packet loss
        if random.random() < self.loss_rate:
            self.packets_dropped += 1
            print(f"[Connector] {direction} DROP: {packet_info}")
            return
        
        # Simulate packet corruption
        if random.random() < self.corruption_rate:
            data = self._corrupt_packet(data)
            self.packets_corrupted += 1
            print(f"[Connector] {direction} CORRUPT: {packet_info}")
        
        # Simulate delay and reordering
        if random.random() < self.reorder_rate or self.delay_range[1] > 0:
            delay = random.uniform(self.delay_range[0], self.delay_range[1])
            if delay > 0:
                self.packets_delayed += 1
            
            if random.random() < self.reorder_rate:
                self.packets_reordered += 1
                # Add extra delay for reordering
                delay += random.uniform(0.5, 1.5)
            
            with self.reorder_lock:
                deliver_time = time.time() + delay
                self.reorder_buffer.append((deliver_time, data, dest_addr, sock, direction, packet_info))
            
            if delay > 0:
                print(f"[Connector] {direction} DELAY: {packet_info} by {delay:.2f}s")
        else:
            # Forward immediately
            self._send_packet(data, dest_addr, sock, direction, packet_info)

    def _corrupt_packet(self, data):
        """Corrupt random bits in packet"""
        data_array = bytearray(data)
        
        # Corrupt 1-3 random bytes
        num_corruptions = random.randint(1, 3)
        for _ in range(num_corruptions):
            pos = random.randint(0, len(data_array) - 1)
            data_array[pos] ^= random.randint(1, 255)
        
        return bytes(data_array)
    
    def _process_reorder_buffer(self):
        """Process delayed packets from reorder buffer"""
        while self.running:
            time.sleep(0.05)  # Check every 50ms
            
            current_time = time.time()
            packets_to_send = []
            
            with self.reorder_lock:
                # Find packets ready to send
                remaining = []
                for item in self.reorder_buffer:
                    deliver_time, data, dest_addr, sock, direction, packet_info = item
                    if deliver_time <= current_time:
                        packets_to_send.append((data, dest_addr, sock, direction, packet_info))
                    else:
                        remaining.append(item)
                
                self.reorder_buffer = remaining
            
            # Send packets outside of lock
            for data, dest_addr, sock, direction, packet_info in packets_to_send:
                self._send_packet(data, dest_addr, sock, direction, packet_info)
    
    def _send_packet(self, data, dest_addr, sock, direction, packet_info):
        """Send packet through socket"""
        try:
            sock.sendto(data, dest_addr)
            self.packets_forwarded += 1
            print(f"[Connector] {direction} FWD: {packet_info}")
        except Exception as e:
            print(f"[Connector] Error sending packet: {e}")


def main():
    parser = argparse.ArgumentParser(description='Network Connector for RDT Protocol')
    parser.add_argument('--client-port', type=int, default=8888, 
                       help='Port to listen for client packets (default: 8888)')
    parser.add_argument('--server-port', type=int, default=9999,
                       help='Port to forward to server (default: 9999)')
    parser.add_argument('--server-host', type=str, default='localhost',
                       help='Server hostname (default: localhost)')
    parser.add_argument('--loss', type=float, default=0.1,
                       help='Packet loss rate 0.0-1.0 (default: 0.1)')
    parser.add_argument('--corrupt', type=float, default=0.05,
                       help='Packet corruption rate 0.0-1.0 (default: 0.05)')
    parser.add_argument('--delay-min', type=float, default=0.0,
                       help='Minimum delay in seconds (default: 0.0)')
    parser.add_argument('--delay-max', type=float, default=0.5,
                       help='Maximum delay in seconds (default: 0.5)')
    parser.add_argument('--reorder', type=float, default=0.1,
                       help='Packet reorder rate 0.0-1.0 (default: 0.1)')
    
    args = parser.parse_args()
    
    # Create and start Connector
    Connector = NetworkConnector(
        client_port=args.client_port,
        server_port=args.server_port,
        server_host=args.server_host,
        loss_rate=args.loss,
        corruption_rate=args.corrupt,
        delay_range=(args.delay_min, args.delay_max),
        reorder_rate=args.reorder
    )
    
    try:
        Connector.start()
        
        print("\nConnector running. Press Ctrl+C to stop.\n")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down Connector")
        Connector.stop()


if __name__ == "__main__":
    main()