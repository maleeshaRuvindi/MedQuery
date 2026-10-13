import asyncio
import httpx
import time

URL = "http://localhost:8000/chat"
QUESTION = "How many unique patients are in the database?"
CONCURRENT_REQUESTS = 10

async def send_request(client, i):
    start = time.time()
    response = await client.post(URL, params={"question": QUESTION})
    elapsed = time.time() - start
    print(f"Request {i+1}: {elapsed:.2f}s — status {response.status_code}")
    return elapsed

async def main():
    print("started")
    async with httpx.AsyncClient(timeout=120) as client:
        total_start = time.time()
        times = await asyncio.gather(*[send_request(client, i) for i in range(CONCURRENT_REQUESTS)])
        total = time.time() - total_start
        print(f"\nAll {CONCURRENT_REQUESTS} requests completed in {total:.2f}s")
        print(f"Average per request: {sum(times)/len(times):.2f}s")

asyncio.run(main())