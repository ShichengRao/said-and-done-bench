def initialize(path,snapshot): raise NotImplementedError('durable initialization')
def ingest(path,batch): raise NotImplementedError('durable archive ingestion')
def advance(path,target): raise NotImplementedError('verified checkpoint')
def inspect(path): raise NotImplementedError('durable inspection')
