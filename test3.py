def a():
    yield 1
    yield 2

for i in a():
    print(i)
