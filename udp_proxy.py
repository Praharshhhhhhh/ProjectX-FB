import socket
import select
import sys

def main():
    LOCAL_IP = "0.0.0.0"
    LOCAL_PORT = 51820
    DEST_IP = "172.31.122.164"
    DEST_PORT = 51820

    print(f"Starting UDP Proxy: {LOCAL_IP}:{LOCAL_PORT} -> {DEST_IP}:{DEST_PORT}")
    
    # Socket listening on external Windows IP
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((LOCAL_IP, LOCAL_PORT))
    
    # Socket to talk to WSL
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    client_addr = None
    
    while True:
        r, _, _ = select.select([server, client], [], [])
        for s in r:
            if s is server:
                data, addr = server.recvfrom(4096)
                client_addr = addr  # Store external client
                client.sendto(data, (DEST_IP, DEST_PORT))
            elif s is client and client_addr:
                data, _ = client.recvfrom(4096)
                server.sendto(data, client_addr)

if __name__ == "__main__":
    main()
