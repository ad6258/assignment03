import socket
import argparse
import os
from rdt import RDTReceiver

class FileServer:
    """
    File Transfer Server
    Receives files using RDT protocol and saves them to disk
    """
    
    def __init__(self, port, save_dir='files/received'):
        """
        Initialize File Server
        
        Args:
            port: Port to listen on
            save_dir: Directory to save received files
        """
        self.port = port
        self.save_dir = save_dir
        
        # Create save directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', port))
        
        print(f"[Server] Started on port {port}")
        print(f"[Server] Saving files to: {save_dir}")
    
    def start(self):
        """Start the server and listen for file transfers"""
        print("[Server] Waiting for file transfers...\n")
        
        try:
            while True:
                # Wait for incoming connection
                print("[Server] Ready to receive file...")
                
                # Create RDT receiver for this transfer
                receiver = RDTReceiver(self.sock, window_size=5)
                receiver.start()
                
                # Receive file data
                file_data = receiver.receive_all_data(timeout=30)
                
                if file_data:
                    # Extract filename and content
                    # Protocol: first line is filename, rest is file content
                    try:
                        lines = file_data.split(b'\n', 1)
                        if len(lines) == 2:
                            filename = lines[0].decode('utf-8')
                            content = lines[1]
                        else:
                            filename = "received_file.bin"
                            content = file_data
                        
                        # Save file
                        filepath = os.path.join(self.save_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        
                        print(f"\n[Server] ✓ File received and saved: {filepath}")
                        print(f"[Server] File size: {len(content)} bytes\n")
                    
                    except Exception as e:
                        print(f"[Server] Error saving file: {e}")
                
                receiver.stop()
                
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
            self.sock.close()


def main():
    parser = argparse.ArgumentParser(description='File Transfer Server using RDT Protocol')
    parser.add_argument('--port', type=int, default=9999,
                       help='Port to listen on (default: 9999)')
    parser.add_argument('--save-dir', type=str, default='files/received',
                       help='Directory to save received files (default: files/received)')
    
    args = parser.parse_args()
    
    server = FileServer(port=args.port, save_dir=args.save_dir)
    server.start()


if __name__ == "__main__":
    main()