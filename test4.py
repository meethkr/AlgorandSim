import simpy

env = simpy.Environment()

def delay(env, parking_duration):
        yield env.timeout(parking_duration)

def car(env):
  while True:
    print('Start parking at %d' % env.now)
    parking_duration = 5
    env.process(delay(env, parking_duration))
    print('Start driving at %d' % env.now)
    trip_duration = 2
    yield env.timeout(trip_duration)

def bus(env):
    while True:
        print("Bus started at %d" % env.now)
        yield env.timeout(3)


env.process(car(env))
env.process(bus(env))

env.run(until=50)
