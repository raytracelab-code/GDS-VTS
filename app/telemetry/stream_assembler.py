class StreamAssembler:
    def __init__(self) -> None: self.buffer = b''
    def feed(self, chunk: bytes) -> list[str]:
        self.buffer += chunk
        lines = self.buffer.split(b'\n'); self.buffer = lines.pop()
        result = []
        for line in lines:
            line = line.rstrip(b'\r')
            if not line.strip(): continue
            result.append(line.decode('utf-8', errors='replace'))
        return result
