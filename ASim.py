import simpy
import scipy.stats
import ecdsa
import numpy as np
import random
import hashlib


### PARAMETERS
NODE_COUNT = 4
MIN_DEG = 2
MAX_DEG = 3

T_PROPOSER = 20
T_STEP = 200
T_FINAL = 200

LAMBDA_PROPOSER = 3 * 1000
LAMBDA_BLOCK = 30 * 1000
#### END OF PARAMETERS



#### CLASSES
class Node:
    def __init__(self, env, iden, conn_count):
        self.env = env
        # self.action #TODO
        self.iden = iden
        self.out_links = []
        self.conn_count = conn_count

        self.message_sequence_id = 0
        self.recieved_id_cache = list() #TODO

        self.stake = np.random.randint(1, 51)

        self.sk = ecdsa.SigningKey.generate()
        self.pk = self.sk.get_verifying_key()

        self.input_buffer = dict()


    def message_consumer(self, in_link):
        """unpack the message, verify the signature"""
        # # print('id', self.iden)
        while True:
            msg = yield in_link.pipe.get()
            c_sign = msg[1]
            encoded_msg = msg[0]
            payload, pk, mid, nid, m_type, roundn, stepn = encoded_msg.decode('utf-8').split("<|>")
            nid = int(nid)
            mid = int(mid)
            roundn = int(roundn)
            stepn = int(stepn)

            if m_type == 'b':
                yield env.timeout(in_link.block_delay)
                # print("Block message recieved at", str(self.iden), "from node", str(in_link.src))
            else:
                yield env.timeout(in_link.delay)

            if ((mid, nid)) in self.recieved_id_cache:
                # print("Duplicate Message \'" + str(payload) + "\' recieved at node" + str(self.iden) + " from node  " \
                        # + str(in_link.src) + " with ID " + str(mid) + str(nid) \
                        # + " at " + str(env.now))
                continue
            else:
                # print("New Message \'"  +  str(payload) + "\' recieved at node"  + str(self.iden) + " from node  " +  \
                        # str(in_link.src) + " with ID " + str(mid) + str(nid) \
                        # + " at " + str(env.now))

                self.recieved_id_cache.append((mid, nid))
                self.input_buffer.setdefault((roundn, stepn), []).append(msg)
                # print("input buffer at node", self.iden, ":", self.input_buffer)
                pks[nid].verify(c_sign, encoded_msg)
                # try:
                    # pks[nid].verify(c_sign, encoded_msg)
                # except Exception as e:
                    # # print(e)
                    # # print("Error occured during Public Key verification.")
                    # continue

                self.put(msg)

    def get_output_conn(self, link):
        """Takes a link as input, appends it to the 'out_links' list and retuns the corresponding *pipe*"""
        # # print("link from", link.src, "to", link.dest)
        self.out_links.append(link)
        return link

    def message_generator(self, env):
        while True:
            # print("generator called at", self.iden)
            # wait for next transmission
            # self.block_proposal()


            # print("Block proposal called at", self.iden)
            round_no = prev_block.height
            prev_hsh = prev_block.hsh
            hsh, j = self.sortition((prev_hsh, str(round_no), 0), T_PROPOSER, 'r') #TODO change 'r' to role

            if j > 0:
                print("found a guy")
                hx = hashlib.sha256((str(hsh) + str(1)).encode()).hexdigest() #priority
                jx = 1          #corresponding id
                for i in range(2, j+1):
                    h = hashlib.sha256((str(hsh) + str(i)).encode()).hexdigest()
                    if h < hx:
                        hx = h
                        jx = i

                gossip_body = str(round_no) + "<$>" + str(hsh) + "<$>" + str(jx) + "<$>" + str(hx)
                gossip_msg = Message(self, gossip_body, 'nb', round_no, 0)
                self.put(gossip_msg.message)
                yield env.timeout(LAMBDA_PROPOSER) #TODO : Decide the delays
                p_vals = list()
                try:
                    for msg in self.input_buffer[(round_no, 0)]:
                        c_sign = msg[1]
                        encoded_msg = msg[0]
                        payload, pk, mid, nid, m_type, roundn, stepn = encoded_msg.decode('utf-8').split("<|>")
                        rn, hs, subuser, priority = payload.split("<$>")
                        p_vals.append(priority)
                except KeyError as e:
                    print("No matching keys", e)
                least_p_val = min(p_vals)
                if hx == least_p_val:
                    bp_message_payload = str(prev_hsh) + "<@>" + str(random.getrandbits(32)) + "<@>" + gossip_body
                    bp_message_object = Message(self, bp_message_payload, 'b', round_no, 0)
                    self.put(bp_message_object.message)
                    print("Block proposer selected", self.iden)

            yield env.timeout(random.randint(6, 10)) #TODO : Decide the delays





    def put(self, value):
        """Broadcast a *value* to all receivers."""
        if not self.out_links:
            raise RuntimeError('There are no output pipes.')
        # events = [store.put(value) for store in self.out_pipes]
        events = []
        for link in self.out_links:
            events.append(link.pipe.put(value))
        return self.env.all_of(events)  # Condition event for all "events"

    def sortition(self, s, thold, role):
        # print("sortition called at", self.iden)
        hsh = PRG(s)
        p = thold / W_total_stake
        j = 0
        k = 0
        lower = scipy.stats.binom.pmf(k, self.stake, p)
        higher = lower + scipy.stats.binom.pmf(k + 1, self.stake, p)
        x = (hsh / (2 ** 256))
        # print('x', x)
        # print('lower, higher', lower, higher)
        while x >= lower and x < higher:
            j += 1
            lower = 0
            higher = 0

            for k in range(0, j+1):
                lower += scipy.stats.binom.pmf(k, self.stake, p)

            higher = lower + scipy.stats.binom.pmf(k, self.stake, p)
        # print("returning j", j)
        return (hsh, j)

    # def block_proposal(self):
    #     # print("Block proposal called at", self.iden)
    #     round_no = prev_block.height
    #     prev_hsh = prev_block.hsh
    #     hsh, j = self.sortition((prev_hsh, str(round_no), 0), T_PROPOSER, 'r') #TODO change 'r' to role
    #
    #     if j > 0:
    #         hx = 2 ** 257   #priority
    #         jx = 1          #corresponding id
    #         for i in range(1, j+1):
    #             h = hashlib.sha256(str(hsh) + str(i)).hexdigest()
    #             if h < hx:
    #                 hx = h
    #                 jx = j
    #
    #         gossip_body = str(round_no) + "<$>" + str(hsh) + "<$>" + str(jx) + "<$>" + str(hx)
    #         gossip_msg = Message(self, gossip_body, 'nb', round_no, 0)
    #         self.put(gossip_msg.message)
    #         yield env.timeout(LAMBDA_PROPOSER) #TODO : Decide the delays
    #         least_p_val = 2 ** 257
    #         for msg in self.input_buffer[(round_no, 0)]:
    #             c_sign = msg[1]
    #             encoded_msg = msg[0]
    #             payload, pk, mid, nid, m_type, roundn, stepn = encoded_msg.decode('utf-8').split("<|>")
    #             rn, hs, subuser, priority = payload.split("<$>")
    #             least_p_val = min(least_p_val, priority)
    #
    #         if hx == least_p_val:
    #             bp_message_payload = str(prev_hsh) + "<@>" + str(random.getrandbits(32)) + "<@>" + gossip_body
    #             bp_message_object = Message(self, bp_message_payload, 'b', round_no, 0)
    #             self.put(bp_message_object.message)
    #             # print("Block proposer selected", self.iden)
    #
    #     yield env.timeout(random.randint(6, 10)) #TODO : Decide the delays


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
    """<Payload || Public Key || Message ID || Node ID >, signature"""
    def __init__(self, node, payload, m_type, roundn, stepn):
        self.payload = payload
        self.m_type = m_type # non-block & block
        self.roundn = roundn
        self.stepn = stepn

        self.node_id = node.iden
        self.msg_id = node.message_sequence_id
        node.message_sequence_id += 1
        self.publickey = node.pk

        self.message_string = (str(self.payload) + "<|>" + str(self.publickey) + "<|>" +\
                str(self.msg_id) + "<|>" + str(self.node_id) + "<|>" + str(self.m_type) + "<|>" + str(roundn) + "<|>" + str(stepn)).encode('utf-8')
        self.signature = node.sk.sign(self.message_string)

        self.message = (self.message_string, self.signature)

class Block:
    def __init__(self, prev_hsh, s, prev_height):
        self.prev_hsh = prev_hsh
        self.s = s
        self.block = str(prev_hsh) + str(s)
        self.hsh = hashlib.sha256(self.block.encode()).hexdigest()
        self.height = prev_height + 1

### END OF CLASSES

## PUBLIC FUNCTIONS
def PRG(s):
    random.seed(str(s))
    return random.getrandbits(256)


## END OF PUBLIC FUNCTIONS

# 0. create 2000 nodes + housekeeping
env = simpy.Environment()

pks = dict()
nodes = list()
W_total_stake = 0
node_conn_counts = np.random.randint(MIN_DEG, MAX_DEG+1, NODE_COUNT)

for i in range(NODE_COUNT):
    nodes.append(Node(env, i, node_conn_counts[i]))
    pks[nodes[i].iden] = nodes[i].pk
    W_total_stake += nodes[i].stake

# print("Total stake:", W_total_stake)

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

# print("m", node_conn_matrix)
# print("dm", delay_matrix)
# print("bm", block_delay_matrix)
gb = Block(None, "We are buildling the best Algorand Discrete Event Simulator", -1)
prev_block = gb  # to know the current leader block

# 3. create links
for i in range(NODE_COUNT):
    curr_node = nodes[i]
    env.process(curr_node.message_generator(env))
    for j in range(len(node_conn_matrix[i])):
        target = node_conn_matrix[i][j]
        delay = delay_matrix[i][j]
        block_delay = block_delay_matrix[i][j]
        """Instantiate a link, return it to get_output_conn, get_output_conn will return the pipe which is given to the message_consumer
        and the message_consumer will yield on it."""
        env.process(nodes[target].message_consumer(curr_node.get_output_conn(Link(env, i, target, delay, block_delay))))



# print("publickeys", pks)
# 4. call generator
# 5. call consumers alongwith get_output_conn
# x. TEST
######################
# m = Message(nodes[0], "hello there", 'b', -1, -1)
# m2 = Message(nodes[0], "there", 'b', -1, -1)
# nodes[0].put(m.message)
# nodes[0].put(m2.message)



#####################
# END TEST

env.run(until = None)
