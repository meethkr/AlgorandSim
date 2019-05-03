import simpy
import scipy.stats
# import ecdsa
from fastecdsa import keys, curve, ecdsa
import numpy as np
import random
import hashlib
import time
import csv


### PARAMETERS
NODE_COUNT = 256
MIN_DEG = 2
MAX_DEG = 4

COMMITTEE_STEP_FACTOR = 0.685
COMMITTEE_FINAL_FACTOR = 0.74

T_PROPOSER = 5
T_STEP = 32
T_FINAL = T_PROPOSER

LAMBDA_PROPOSER = 3 * 1000
LAMBDA_BLOCK = 30 * 1000
LAMBDA_STEP = 3 * 1000

MAX_STEPS = 10
FINAL_STEP = MAX_STEPS + 1
MAX_ROUNDS = 164

MAX_ADVERSARY_ROUNDS = 5
ADVERSARY_FRACTION = 0.10
#### END OF PARAMETERS

f = open("LogsExp4_" + str(ADVERSARY_FRACTION) + "_3.txt", "w")
no_of_subs = dict()
subusers_per_step_round = dict()

counter = NODE_COUNT
current_selected_block = dict()

is_adversary_selected = False
current_adversary = None
count_adversary_rounds = 0
adversary_nodes = list()
adversary_blocks = dict()
adversary_rounds = dict()
#### CLASSES
class Node:
    def __init__(self, env, iden, conn_count):
        self.env = env
        self.iden = iden
        self.out_links = []
        self.conn_count = conn_count

        self.message_sequence_id = 0
        self.recieved_id_cache = list() #TODO

        self.stake = np.random.randint(1, 51)

        self.sk, self.pk = keys.gen_keypair(curve.P256)

        self.input_buffer = dict()
        self.count_value = dict()
        self.blockchain = list()
        self.blockchain.append(prev_block)
        self.prev_block = prev_block
        self.step_count = 0
        self.proposed_block = None
        self.adversary_round_count = 0

    def delay(self, env, timeout_n):
        yield env.timeout(timeout_n)

    def message_consumer(self, in_link):
        """unpack the message, verify the signature"""
        global is_adversary_selected
        global adversary_nodes
        global current_adversary
        while True:
            msg = yield in_link.pipe.get()
            c_sign = msg[1]
            decoded_msg = msg[0]
            payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
            nid = int(nid)
            mid = int(mid)
            roundn = int(roundn)
            stepn = int(stepn)

            if m_type == 'b':
                yield env.timeout(in_link.block_delay)
            else:
                yield env.timeout(in_link.delay)

            if ((mid, nid)) in self.recieved_id_cache:
                continue
            else:
                self.recieved_id_cache.append((mid, nid))
                self.input_buffer.setdefault((roundn, stepn), []).append(msg)
                
                #nid = int(nid)
                #if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
                #    pass
                    #print("Key verification successful for", self.iden, file = f)
                #else:
                #    print("Error occured during Public Key verification.", file = f)
                #    continue
                if m_type == 'b':
                    if is_adversary_selected == True:
                        if self.iden in adversary_nodes:
                            if self.iden != current_adversary:
                                while self.proposed_block is None:
                                    yield env.timeout(LAMBDA_STEP)
                                prev_hsh, rand_string, priority_payload = payload.split("<@>")
                                if prev_hsh == self.proposed_block.prev_hsh:
                                    self.put(msg)
                            else:
                                self.put(msg)
                        else:
                            self.put(msg)
                    else:
                        self.put(msg)
                else:            
                    self.put(msg)

    def get_output_conn(self, link):
        """Takes a link as input, appends it to the 'out_links' list and retuns the corresponding *pipe*"""
        self.out_links.append(link)
        return link

    def message_generator(self, env):
        global counter
        global current_selected_block
        global adversary_nodes
        global adversary_blocks
        global count_adversary_rounds
        global is_adversary_selected
        global adversary_rounds
        global current_adversary
        while True:
            round_start_time = time.time()
            simulation_start_time = env.now
            
            self.input_buffer = dict()
            self.count_value = dict()
            self.proposed_block = None
            self.step_count = 0
            
            step = 0
            prev_block = self.prev_block
            round_no = prev_block.height
            prev_hsh = prev_block.hsh
            hsh, j = self.sortition((prev_hsh, round_no, step), T_PROPOSER, 'r', round_no, 0, True)


            if self.iden in adversary_nodes:
                rand_string = str(random.getrandbits(32))
                adversary_block1 = Block(prev_block.hsh, rand_string, prev_block.height)
                rand_string = str(random.getrandbits(32))
                adversary_block2 = Block(prev_block.hsh, rand_string, prev_block.height)
                adversary_blocks[self.iden] = (adversary_block1, adversary_block2)

            proposed_block = None
            if j > 0:
                hx = hashlib.sha256((str(hsh) + str(1)).encode()).hexdigest() #priority
                jx = 1          #corresponding id
                for i in range(2, j+1):
                    h = hashlib.sha256((str(hsh) + str(i)).encode()).hexdigest()
                    if h < hx:
                        hx = h
                        jx = i

                gossip_body = str(round_no) + "<$>" + str(hsh) + "<$>" + str(j) + "<$>" + str(hx)
                gossip_msg = Message(self, gossip_body, 'nb', round_no, step)
                self.recieved_id_cache.append((gossip_msg.msg_id, gossip_msg.node_id))
                self.put(gossip_msg.message)

                yield env.timeout(LAMBDA_PROPOSER)
               
                p_vals = list()
                proposer_dict = dict()
                p_vals.append(str(hx))
                try:
                    for msg in self.input_buffer[(round_no, step)]:
                        c_sign = msg[1]
                        decoded_msg = msg[0]
                        payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
                        rn, hs, subuser_no, priority = payload.split("<$>")
                        p_vals.append(priority)
                        nid = int(nid)
                        proposer_dict[nid] = str(priority)
                except KeyError as e:
                    print("No matching keys", e, " buffer:", self.input_buffer, file = f)
                    
                if len(p_vals) != 0:
                    least_p_val = min(p_vals)
                else: 
                    least_p_val = hx 

                sorted_priority = sorted(proposer_dict.items(), key = lambda kv:(kv[1], kv[0]))
                print("Received proposals from other nodes, at Node:", self.iden, "are", str(sorted_priority), file = f)
                if hx == least_p_val:
                    if self.iden in adversary_nodes:
                        print("I am a byzantine adversary:", self.iden,"selected as highest proposer for round:", round_no)
                        print("I am a byzantine adversary:", self.iden,"selected as highest proposer for round:", round_no, file = f)
                        is_adversary_selected = True
                        count_adversary_rounds += 1
                        current_adversary = self.iden
                        bp_message_payload = str(prev_hsh) + "<@>" + adversary_block1.s + "<@>" + gossip_body
                        bp_message_object = Message(self, bp_message_payload, 'b', round_no, step)
                        self.recieved_id_cache.append((bp_message_object.msg_id, bp_message_object.node_id))
                        self.put(bp_message_object.message)
                        bp_message_payload = str(prev_hsh) + "<@>" + adversary_block2.s + "<@>" + gossip_body
                        bp_message_object = Message(self, bp_message_payload, 'b', round_no, step)
                        self.recieved_id_cache.append((bp_message_object.msg_id, bp_message_object.node_id))
                        self.put(bp_message_object.message)
                        print("Block proposer for Round:", round_no, "Node:", self.iden, file = f)
                    else:
                        rand_string = str(random.getrandbits(32))
                        proposed_block = Block(prev_block.hsh, rand_string, prev_block.height)
                        bp_message_payload = str(prev_hsh) + "<@>" + rand_string + "<@>" + gossip_body
                        bp_message_object = Message(self, bp_message_payload, 'b', round_no, step)
                        self.recieved_id_cache.append((bp_message_object.msg_id, bp_message_object.node_id))
                        self.put(bp_message_object.message)
                        print("Block proposer for Round:", round_no, "Node:", self.iden, file = f)

            if proposed_block == None:
                yield env.timeout(LAMBDA_PROPOSER + LAMBDA_BLOCK)
            else:
                yield env.timeout(LAMBDA_BLOCK)
        
            if is_adversary_selected == True and self.iden in adversary_nodes:
                block_no = random.randint(0,1)
                self.proposed_block = adversary_blocks.get(current_adversary)[block_no]
                proposed_block = self.proposed_block
            else:
                try:
                    for msg in self.input_buffer[(round_no, step)]:
                        c_sign = msg[1]
                        decoded_msg = msg[0]
                        payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")

                        if m_type == 'b' and proposed_block == None:
                            #print("Block message recieved from " + str(nid) + " at node" + str(self.iden), file = f)
                            prev_hsh, rand_string, priority_payload = payload.split("<@>")
                            proposed_block = Block(prev_block.hsh, rand_string, prev_block.height)
                        else:
                            continue
                except KeyError as e:
                    print("No matching keys", e, " buffer:", self.input_buffer, file = f)

            if proposed_block == None:
                proposed_block = Block(prev_block.hsh, "Empty", prev_block.height)
           
            #print("Starting Reduction on block " + proposed_block.s + " from node " + str(self.iden), file = f)
            cur_block = yield env.process(self.reduction(proposed_block, round_no, prev_hsh))
            #print("Starting BinaryBA", self.iden, file = f)
            final_block = yield env.process(self.binaryBA(round_no, cur_block, prev_hsh))
            #print("Counting Final Votes", self.iden, file = f)
            hash_block = self.count_votes(round_no, FINAL_STEP, T_FINAL, COMMITTEE_FINAL_FACTOR)

            if final_block.hsh == hash_block:
                print("Final concensus achieved on block: ",final_block.s, "in Round:", round_no, "at Node:", self.iden, file = f)
                final_block.state = "Final"
            else:
                print("Tentative concensus achieved on block: ",final_block.s, "in Round:", round_no,"at Node:", self.iden, file = f)
                final_block.state = "Tentative"

            if final_block.state == "Final":
                current_selected_block[final_block.s] = current_selected_block.get(final_block.s, (0, final_block))
                current_selected_block[final_block.s] = (current_selected_block[final_block.s][0] + 1, final_block)
 
            yield env.timeout(LAMBDA_BLOCK)

            max_block_str = None
            counter -= 1
            #print("Node", self.iden, "reduced the counter by 1")

            if is_adversary_selected == True:
                self.adversary_round_count += 1
                #print("Adversary Round Count:", self.adversary_round_count, "For Node:", self.iden)
                adversary_rounds[round_no] = max(self.step_count, adversary_rounds.get(round_no, 0))

            if counter == 0:
                print("Current Global Dict:", current_selected_block)
                max_val = -1 
                if len(current_selected_block) == 0:
                    print("Empty selected block list at round", round_no)

                for i in current_selected_block.keys():
                    if current_selected_block[i][0] > max_val:
                        max_val = current_selected_block[i][0]
                        max_block_str = str(i) 

                current_selected_block = dict() 
                if max_block_str is None:
                    print("Max voted string is None at round", round_no)

                print("Node", self.iden, "is the last to round", round_no)
                counter = NODE_COUNT
                adversary_blocks = dict()
                is_adversary_selected = False
                current_adversary = None
                round_end_time = time.time()
                simulation_end_time = env.now
                print("System Round Time: ", round_end_time - round_start_time, "for Round:", round_no, "at Node:", self.iden)
                print("Simulator Round Time: ", simulation_end_time - simulation_start_time, "for Round:", round_no, "at Node:", self.iden)
                print("Adversary Round Dict:", adversary_rounds)            

            while counter != NODE_COUNT:
                #print("Node", self.iden, "waiting")
                yield (env.timeout(LAMBDA_STEP))

            if max_block_str is not None: 
                final_block.s = max_block_str

            self.prev_block = final_block
            self.blockchain.append(final_block)

            if round_no == MAX_ROUNDS - 1 or self.adversary_round_count == MAX_ADVERSARY_ROUNDS:
                break

            print("Starting New Round:", (round_no + 1)," for Node:", self.iden, file = f)


    def put(self, value):
        """Broadcast a *value* to all receivers."""
        if not self.out_links:
            raise RuntimeError('There are no output pipes.')
        events = []
        for link in self.out_links:
            events.append(link.pipe.put(value))
        return self.env.all_of(events)  # Condition event for all "events"

    def sortition(self, s, thold, role, round_no, step_no, is_log):
        hsh = PRG(s, self.sk)
        hsh_length = hsh.bit_length()
        p = thold / W_total_stake
        j = 0
        k = 0
        lower = 0
        higher = lower + scipy.stats.binom.pmf(k, self.stake, p)
        x = (hsh / (2 ** 256))
        while (x < lower or x >= higher) and j <= self.stake:
            j += 1
            lower = 0
            higher = 0

            for k in range(0, j):
                lower += scipy.stats.binom.pmf(k, self.stake, p)

            higher = lower + scipy.stats.binom.pmf(k+1, self.stake, p)

        if is_log == True:
            no_of_subs[self.stake] = no_of_subs.get(self.stake , 0) + j
            subusers_per_step_round[(self.stake, step_no, round_no)] = j
            print("Sortition Result for Node:", self.iden," in Round:", round_no, "Step:", step_no, "returned Sub User Count:",j, file = f)
        return (hsh, j)

    def reduction(self, block, round_no, prev_hsh):
        #print("Reduction called by: " + str(self.iden), file = f)
        prev_block = self.prev_block
        v_hash, v_j = self.sortition((prev_hsh, round_no, 0), T_PROPOSER, 'r', round_no, 0, False)
        step = 1

        self.committee_vote(prev_hsh, round_no, step, T_STEP, block, v_hash, v_j)
        yield env.timeout(LAMBDA_STEP)

        hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

        step = 2
        empty_block = Block(prev_block.hsh, "Empty", prev_block.height)

        if hash_block == None or hash_block != block.hsh:
            self.committee_vote(prev_hsh, round_no, step, T_STEP, empty_block, v_hash, v_j)
            yield env.timeout(LAMBDA_STEP)
        else:
            self.committee_vote(prev_hsh, round_no, step, T_STEP, block, v_hash, v_j)
            yield env.timeout(LAMBDA_STEP)

        hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

        if hash_block == None or hash_block != block.hsh:
            #print("Returning empty block from reduction at Node", self.iden, file = f)
            return empty_block
        else:
            #print("Returning new block from reduction at Node", self.iden, file = f)
            return block


    def committee_vote(self, prev_hsh, round_no, step, threshold, block, v_hash, v_j):
        #print("Doing committee_vote for", self.iden, " at round", round_no, " and", step, file = f)
        hsh, j = self.sortition((prev_hsh, round_no, step), threshold, 'c', round_no, step, True)
        global adversary_blocks
        global adversary_nodes
        global current_adversary
        if j > 0:
            if is_adversary_selected == True and self.iden in adversary_nodes:
                block = adversary_blocks.get(current_adversary)[0]
                vote_body = str(prev_hsh) + "<$>" + str(block.hsh) + "<$>" + str(round_no) + "<$>"\
                 + str(step) + "<$>" + str(j) + "<$>" + str(hsh)
                vote_msg = Message(self, vote_body, 'nb', round_no, step)
                #print("Voting for step: " + str(step), file = f)
                self.recieved_id_cache.append((vote_msg.msg_id, vote_msg.node_id))      
                self.put(vote_msg.message)
                block = adversary_blocks.get(current_adversary)[1]
                vote_body = str(prev_hsh) + "<$>" + str(block.hsh) + "<$>" + str(round_no) + "<$>"\
                 + str(step) + "<$>" + str(j) + "<$>" + str(hsh)
                vote_msg = Message(self, vote_body, 'nb', round_no, step)
                #print("Voting for step: " + str(step), file = f)
                self.recieved_id_cache.append((vote_msg.msg_id, vote_msg.node_id))      
                self.put(vote_msg.message)
            else:
                vote_body = str(prev_hsh) + "<$>" + str(block.hsh) + "<$>" + str(round_no) + "<$>"\
                 + str(step) + "<$>" + str(j) + "<$>" + str(hsh)
                vote_msg = Message(self, vote_body, 'nb', round_no, step)
                #print("Voting for step: " + str(step), file = f)
                self.recieved_id_cache.append((vote_msg.msg_id, vote_msg.node_id))      
                self.put(vote_msg.message)


    def count_votes(self, round_no, step, threshold, committee_size_factor):
        #print("Doing count_vote for", self.iden, file = f)
        try:
            voters = list()
            for msg in self.input_buffer[(round_no, step)]:
                c_sign = msg[1]
                decoded_msg = msg[0]
                payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
                prev_hsh, cur_hsh, r_no, s_no, v_j, v_hash = payload.split("<$>")

                nid = int(nid)
                r_no = int(r_no)
                s_no = int(s_no)
                # if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
                #     pass
                #     #print("Key verification successful", file = f)
                # else:
                #     print("Error occured during Public Key verification.", file = f)
                #     continue

                if prev_hsh != self.prev_block.hsh:
                    continue

                hsh,votes = nodes[nid].sortition((prev_hsh, r_no, s_no), threshold, 'c', round_no, step, False)

                # if hsh == v_hash and votes == v_j:
                #     print("VERIFIED COUNT VOTE SORTITION for ", nid, file = f)
                # else:
                #     print("NOT VERIFIED COUNT VOTE SORTITION for ", nid, file = f)
                #     print("Original hash", v_hash, file = f)
                #     print("New hash", hsh, file = f)
                #     print("Original j", v_j, file = f)
                #     print("New j", votes, file = f)

                if pk in voters or votes == 0:
                    continue

                voters.append(pk)

                self.count_value[cur_hsh] = self.count_value.get(cur_hsh, 0) + votes

                if self.count_value[cur_hsh] > committee_size_factor * threshold:
                    print("Total Votes received in Round:", round_no, "Step:", step, "at Node", self.iden, "are:", self.count_value[cur_hsh], file = f)
                    return cur_hsh
            
            print("Total Votes received in Round:", round_no, "Step:", step, "at Node", self.iden, "are:", self.count_value[cur_hsh], file = f)
            return None

        except KeyError as e:
            print("No matching keys", e, " for node", self.iden, file = f)

    def binaryBA(self, round_no, block, prev_hsh):
        step = 3
        self.step_count = 3
        cur_block = block
        prev_block = self.prev_block
        empty_block = Block(prev_block.hsh, "Empty", prev_block.height)
        v_hash, v_j = self.sortition((prev_hsh, round_no, 0), T_PROPOSER, 'r', round_no, 0, False)

        while step < MAX_STEPS:
            self.committee_vote(prev_hsh, round_no, step, T_STEP, cur_block, v_hash, v_j)
            yield env.timeout(LAMBDA_STEP)
            hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

            if hash_block == None:
                cur_block = block
            elif hash_block != empty_block.hsh:
                for s in range(step + 1, step + 4):
                    self.committee_vote(prev_hsh, round_no, s, T_STEP, cur_block, v_hash, v_j)
                    yield env.timeout(LAMBDA_STEP)
                if step == 3:
                    self.committee_vote(prev_hsh, round_no, FINAL_STEP, T_FINAL, cur_block, v_hash, v_j)
                    yield env.timeout(LAMBDA_STEP)
                #print("Returning block from BinaryBA from Node", self.iden, " as ", cur_block.s, file = f)
                return cur_block
            step += 1
            self.step_count += 1

            self.committee_vote(prev_hsh, round_no, step, T_STEP, cur_block, v_hash, v_j)
            yield env.timeout(LAMBDA_STEP)
            hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

            if hash_block == None:
                cur_block = empty_block
            elif cur_block.hsh == empty_block.hsh:
                for s in range(step + 1, step + 4):
                    self.committee_vote(prev_hsh, round_no, s, T_STEP, cur_block, v_hash, v_j)
                    yield env.timeout(LAMBDA_STEP)
                #print("Returning block from BinaryBA from Node", self.iden, " as ", cur_block.s, file = f)
                return cur_block

            step += 1
            self.step_count += 1

            self.committee_vote(prev_hsh, round_no, step, T_STEP, cur_block, v_hash, v_j)
            yield env.timeout(LAMBDA_STEP)
            hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

            if hash_block == None:
                if self.common_coin(round_no, step, T_STEP) == 0:
                    cur_block = block
                else:
                    cur_block = empty_block

            step += 1
            self.step_count += 1

        return cur_block

    def common_coin(self, round_no, step, threshold):
        min_hash = str(1)
        votes = 0
        try:
            for msg in self.input_buffer[(round_no, step)]:
                c_sign = msg[1]
                decoded_msg = msg[0]
                payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
                prev_hsh, cur_hsh, r_no, s_no, v_j, v_hash = payload.split("<$>")

                # nid = int(nid)
                # if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
                #     pass
                #     #print("Key verification successful", file = f)
                # else:
                #     print("Error occured during Public Key verification.", file = f)
                #     votes = 0

                if prev_hsh != self.prev_block.hsh:
                    votes = 0

                hsh,votes = self.sortition((prev_hsh, round_no, step), threshold, 'c', round_no, step, False)

                if votes > 0:
                    hash_string = str(hsh) + str(1)
                    min_hash = str(hashlib.sha256(hash_string.encode()).hexdigest())

                    for i in range(2, votes + 1):
                        hash_string = str(hsh) + str(i)
                        h = str(hashlib.sha256(hash_string.encode()).hexdigest())
                        min_hash = min(h, min_hash)

        except KeyError as e:
            print("No matching keys", e, " for node", self.iden, file = f)

        #print("Common Coin: ", min_hash, file = f)
        return int(min_hash, 16) % 2


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

        self.message_string = str(self.payload) + "<|>" + str(self.publickey) + "<|>" +\
                str(self.msg_id) + "<|>" + str(self.node_id) + "<|>" + str(self.m_type) + "<|>" + str(roundn) + "<|>" + str(stepn)
        self.signature = ecdsa.sign(self.message_string, node.sk)

        self.message = (self.message_string, self.signature)

class Block:
    def __init__(self, prev_hsh, s, prev_height):
        self.prev_hsh = prev_hsh
        self.s = s
        self.block = str(prev_hsh) + str(s)
        self.hsh = hashlib.sha256(self.block.encode()).hexdigest()
        self.height = prev_height + 1
        self.state = None

### END OF CLASSES

## PUBLIC FUNCTIONS
def PRG(s, sk):
    random.seed(ecdsa.sign(str(s), sk))
    return random.getrandbits(256)
## END OF PUBLIC FUNCTIONS

env = simpy.Environment()
print("Number of Nodes", NODE_COUNT, file = f)
print("Simulation Start Time: ", env.now, file = f)
start_time = time.time()
print("System Start Time: ", start_time, file = f)
gb = Block(None, "We are buildling the best Algorand Discrete Event Simulator", -1)
gb.state = "Final"
prev_block = gb  # to know the current leader block

pks = dict()
nodes = list()
W_total_stake = 0
node_conn_counts = np.random.randint(MIN_DEG, MAX_DEG+1, NODE_COUNT)

for i in range(NODE_COUNT):
    nodes.append(Node(env, i, node_conn_counts[i]))
    pks[nodes[i].iden] = nodes[i].pk
    W_total_stake += nodes[i].stake

with open('node_matrix.csv', 'r') as input_file:
    reader = csv.reader(input_file)
    node_conn_matrix = list(reader)
    #print(node_conn_matrix)
input_file.close()

with open('delay_matrix.csv', 'r') as input_file:
    reader = csv.reader(input_file)
    delay_matrix = list(reader)
    #print(delay_matrix)
input_file.close()

with open('block_delay_matrix.csv', 'r') as input_file:
    reader = csv.reader(input_file)
    block_delay_matrix = list(reader)
    #print(block_delay_matrix)
input_file.close

print("matrix", node_conn_matrix, file = f)
print("delay_matrix", delay_matrix, file = f)
print("block_delay_matrix", block_delay_matrix, file = f)

total_adversary = int(NODE_COUNT * ADVERSARY_FRACTION)

adversary_nodes = random.sample(range(0, NODE_COUNT), total_adversary)

print("Adversary Nodes:", adversary_nodes, file = f)
print("Adversary Nodes:", adversary_nodes)

# 3. create links
for i in range(NODE_COUNT):
    curr_node = nodes[i]
    env.process(curr_node.message_generator(env))
    for j in range(len(node_conn_matrix[i])):
        target = int(node_conn_matrix[i][j])
        delay = int(delay_matrix[i][j])
        block_delay = int(block_delay_matrix[i][j])
        """Instantiate a link, return it to get_output_conn, get_output_conn will return the pipe which is given to the message_consumer
        and the message_consumer will yield on it."""
        env.process(nodes[target].message_consumer(curr_node.get_output_conn(Link(env, i, target, delay, block_delay))))


#4. GLOBAL VARIABLES FOR EXPIREMENTS

outc_3 = open("output_blockchain_exp4_" + str(ADVERSARY_FRACTION) + "_3.csv", "w")

env.run(until = None)

print("Simulation End Time: ", env.now, file = f)
end_time = time.time()
print("System End Time: ", end_time, file = f)

for i in range(NODE_COUNT):
    outc_3.write(str(i+1) + ",")
    for block in nodes[i].blockchain:
        outc_3.write(block.s + ",")
    outc_3.write("\n")

print("Step Counter: ", adversary_rounds, file = f)
print("Step Counter: ", adversary_rounds)
f.close()
outc_3.close()