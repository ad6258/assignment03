## Documentation:
root
│
├── src/
│   ├── packet.py          # Packet structure with checksum
│   ├── rdt.py             # RDT protocol (sender & receiver)
│   ├── connector.py       # Network simulator
│   ├── client.py          # File transfer client
│   └── server.py          # File transfer server
│
├── src/data/              # Files to send
├── files/
│   └── received/          # Received files
│
├── README.md
├── Report.pdf
├── revisions.txt
└── docs/documentation.pdf


## Requirement:
Python 3.6 or higher. No external dependencies.


## How to run:
python3 src/connector.py --loss [loss] --corrupt [corrupt] --delay-max [delay] --reorder [reorder]
python3 src/server.py --port [port]
python3 src/client.py --file [file] --port [port]


## Usage Examples

### Basic Usage

**Basic file transfer**
```bash
python3 src/connector.py --loss 0.05 --corrupt 0.02 --delay-max 0.3 --reorder 0.05
```
```bash
python3 src/server.py --port 9999
```
```bash
python3 src/client.py --file src/data/file.txt --port 8888
```

**Corrupt packet**
```bash
python3 src/connector.py  --loss 0.0 --corrupt 0.3 --delay-max 0.2 --reorder 0.0
```
```bash
python3 src/server.py --port 9999
```
```bash
python3 src/client.py --file src/data/file.txt --port 8888
```

**Packet loss**
```bash
python3 src/connector.py  --loss 0.3 --corrupt 0.0 --delay-max 0.2 --reorder 0.0
```
```bash
python3 src/server.py --port 9999
```
```bash
python3 src/client.py --file src/data/file.txt --port 8888
```

**Packet reorder**
```bash
python3 src/connector.py  --loss 0.0 --corrupt 0.0 --delay-max 0.2 --reorder 0.5
```
```bash
python3 src/server.py --port 9999
```
```bash
python3 src/client.py --file src/data/file.txt --port 8888
```