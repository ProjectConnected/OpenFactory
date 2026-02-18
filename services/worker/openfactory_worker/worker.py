import os
from redis import Redis
from rq import Worker, Queue, Connection

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

def main():
    r = Redis.from_url(REDIS_URL)
    with Connection(r):
        w = Worker([Queue("openfactory")])
        w.work(with_scheduler=False)

if __name__ == "__main__":
    main()
