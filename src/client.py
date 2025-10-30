import socket
import argparse
import os
import time
from rdt import RDTSender

class FileClient:
    """
    File Transfer Client
    Sends files using RDT protocol
    """
    
    def __init__(self, server_host, server_port):
        """
        Initialize File Client
        
        Args:
            server_host: Server hostname/IP
            server_port: Server port
        """
        self.server_host = server_host
        self.server_port = server_port
        self.server_addr = (server_host, server_port)
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        print(f"[Client] Connecting to server {server_host}:{server_port}")
    
    def send_file(self, filepath):
        """
        Send a file to the server
        
        Args:
            filepath: Path to file to send
        """
        if not os.path.exists(filepath):
            print(f"[Client] Error: File not found: {filepath}")
            return False
        
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        print(f"\n[Client] Sending file: {filename}")
        print(f"[Client] File size: {filesize} bytes")
        
        try:
            # Read file content
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Prepare data: filename + newline + content
            # This way the server knows what to name the file
            filename_bytes = filename.encode('utf-8')
            data = filename_bytes + b'\n' + content
            
            print(f"[Client] Total data to send: {len(data)} bytes\n")
            
            # Create RDT sender
            sender = RDTSender(
                sock=self.sock,
                dest_addr=self.server_addr,
                window_size=5,
                timeout=2.0,
                max_packet_size=1024
            )
            
            sender.start()
            
            start_time = time.time()
            
            # Send file data
            sender.send_data(data)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            sender.stop()
            
            # Calculate statistics
            throughput = len(data) / elapsed if elapsed > 0 else 0
            
            print(f"\n[Client] ✓ File sent successfully!")
            print(f"[Client] Time elapsed: {elapsed:.2f} seconds")
            print(f"[Client] Throughput: {throughput:.2f} bytes/sec ({throughput*8:.2f} bits/sec)")
            print(f"[Client] Packets sent: {sender.packets_sent}")
            print(f"[Client] Retransmissions: {sender.retransmissions}")
            
            return True
            
        except Exception as e:
            print(f"[Client] Error sending file: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.sock.close()


def main():
    parser = argparse.ArgumentParser(description='File Transfer Client using RDT Protocol')
    parser.add_argument('--file', type=str, required=True,
                       help='Path to file to send')
    parser.add_argument('--host', type=str, default='localhost',
                       help='Server hostname (default: localhost)')
    parser.add_argument('--port', type=int, default=8888,
                       help='Server port (use simulator port if using simulator, default: 8888)')
    
    args = parser.parse_args()
    
    client = FileClient(server_host=args.host, server_port=args.port)
    client.send_file(args.file)


if __name__ == "__main__":
    main()