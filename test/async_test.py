async def gen():
    yield 1
    yield 2
    yield 3

    
# async def main():
#     abc = gen()
#     print(await anext(abc))  # 1
#     print(await anext(abc))  # 2
#     print(await anext(abc))  # 3

# import asyncio
# asyncio.run(main())

async def main():
    async for x in gen():
        print(x)

import asyncio
asyncio.run(main())