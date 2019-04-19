import simpy
import ecdsa
import numpy as np

class Node:
    def __init__(self, env, iden, conn_count):
        self.env = env
        # self.action #TODO
        self.iden = iden
        self.out_links = []
        self.conn_count = conn_count

        self.message_sequence_id = 0

        self.stake = np.random.randint(1, 51)

        self.sk = ecdsa.SigningKey.generate()
        self.pk = self.sk.get_verifying_key()


    def message_consumer(self, in_pipe):
        pass
        # print('id', self.iden)
        # while True:
            # msg = yield in_pipe.get()
            # #TODO logic

    def get_output_conn(self, link):
        """Takes a link as input, appends it to the 'out_links' list and retuns the corresponding *pipe*"""
        # print("link from", link.src, "to", link.dest)
        self.out_links.append(link)
        return link.pipe

    # def message_generator(name, env, out_pipe):
        # while True:
            # # wait for next transmission
            # yield env.timeout(random.randint(6, 10))

            # # messages are time stamped to later check if the consumer was
            # # late getting them.  Note, using event.triggered to do this may
            # # result in failure due to FIFO nature of simulation yields.
            # # (i.e. if at the same env.now, message_generator puts a message
            # # in the pipe first and then message_consumer gets from pipe,
            # # the event.triggered will be True in the other order it will be
            # # False
            # msg = (env.now, '%s says hello at %d' % (name, env.now))
            # out_pipe.put(msg)

    def put(self, value):
        """Broadcast a *value* to all receivers."""
        if not self.out_pipes:
            raise RuntimeError('There are no output pipes.')
        # events = [store.put(value) for store in self.out_pipes]
        events = []
        for link in self.out_links:
            #TODO: Unpack value and decide on yield delay
            yield self.env.timeout(link.delay)
            events.append(link.pipe.put(value))
        return self.env.all_of(events)  # Condition event for all "events"


class Link:
    """Link has a pipe local variable"""
    def __init__(self, env,  src, dest, delay, block_delay, capacity = simpy.core.Infinity):
        self.env = env
        self.capacity = capacity
        self.pipe = simpy.Store(self.env, capacity=self.capacity)
        self.src = src
        self.dest = dest
        self.delay = delay
        self.block_delay = block_delay

class Message:
    """<Payload || Public Key || Metadata >"""
    def __init__(self, owner_id, msg_id, )

# 0. create 2000 nodes + housekeeping
NODE_COUNT = 4
MIN_DEG = 2
MAX_DEG = 3
env = simpy.Environment()

pks = dict()
nodes = list()
node_conn_counts = np.random.randint(MIN_DEG, MAX_DEG+1, NODE_COUNT)
for i in range(NODE_COUNT):
    nodes.append(Node(env, i, node_conn_counts[i]))
    pks[nodes[i].iden] = nodes[i].pk


# 1. matrix of connections
node_conn_matrix = list()
for i in range(NODE_COUNT):
    node_conn_matrix.append([(i-1) % (NODE_COUNT), (i+1) % (NODE_COUNT)])
    node_conn_counts[i] -= 2


for i in range(NODE_COUNT):
    while i != NODE_COUNT - 1 and node_conn_counts[i] > 0:
        eflag = False
        ti = np.random.randint(i + 1, NODE_COUNT)
        ti_old = ti
        while ((node_conn_counts[ti] == 0) or (ti in node_conn_matrix[i]) or (ti == i)):
            ti = (ti + 1) % NODE_COUNT
            if ti == NODE_COUNT:
                ti = i + 1
            elif ti == ti_old:
                eflag = True
                break

        if eflag == False:
            node_conn_counts[i] -= 1
            node_conn_counts[ti] -= 1
            node_conn_matrix[i].append(ti)
            node_conn_matrix[ti].append(i)
        else:
            break

# 2. delays
delay_matrix = list()
block_delay_matrix = list()
for i in node_conn_matrix:
    i.sort()
    delay_matrix.append([])
    block_delay_matrix.append([])

for i in range(NODE_COUNT):
    for j in node_conn_matrix[i]:
        if j > i:
            x = int(max(np.random.normal(30, 64), 0))
            delay_matrix[i].append(x)
            delay_matrix[j].append(x)
            y = int(max(np.random.normal(200, 400), 0))
            block_delay_matrix[i].append(y)
            block_delay_matrix[j].append(y)

print("m", node_conn_matrix)
print("dm", delay_matrix)
print("bm", block_delay_matrix)

# 3. create links
for i in range(NODE_COUNT):
    curr_node = nodes[i]
    for j in range(len(node_conn_matrix[i])):
        target = node_conn_matrix[i][j]
        delay = delay_matrix[i][j]
        block_delay = block_delay_matrix[i][j]
        """Instantiate a link, return it to get_output_conn, get_output_conn will return the pipe which is given to the message_consumer
        and the message_consumer will yield on it."""
        nodes[target].message_consumer(curr_node.get_output_conn(Link(env, i, target, delay, block_delay)))

# 4. call generator
# 5. call consumers alongwith get_output_conn

# env.run(until = None)