import simpy
import scipy.stats
# import ecdsa
from fastecdsa import keys, curve, ecdsa
import numpy as np
import random
import hashlib


### PARAMETERS
NODE_COUNT = 2000
MIN_DEG = 4
MAX_DEG = 8

COMMITTEE_STEP_FACTOR = 0.685
COMMITTEE_FINAL_FACTOR = 0.74

T_PROPOSER = 20
T_STEP = 200
T_FINAL = 20

LAMBDA_PROPOSER = 3 * 10000
LAMBDA_BLOCK = 30 * 10000
LAMBDA_STEP = 3 * 10000

MAX_STEPS = 15
FINAL_STEP = MAX_STEPS + 1
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

		self.sk, self.pk = keys.gen_keypair(curve.P256)

		self.input_buffer = dict()
		self.count_value = dict()

	def delay(self, env, timeout_n):
		yield env.timeout(timeout_n)

	def message_consumer(self, in_link):
		"""unpack the message, verify the signature"""
		# # print('id', self.iden)
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
				#print("Block message recieved at", str(self.iden), "from node", str(in_link.src))
			else:
				yield env.timeout(in_link.delay)

			if ((mid, nid)) in self.recieved_id_cache:
				# print("Duplicate Message " + "recieved at node" + str(self.iden) + " from node  " \
				# 		+ str(in_link.src) + " with ID " + str(mid) + str(nid) \
				# 		+ " at " + str(env.now))
				continue
			else:
				# print("New Message " + "recieved at node"  + str(self.iden) + " from node  " +  \
				# 		str(in_link.src) + " with ID " + str(mid) + str(nid) \
				# 		+ " at " + str(env.now))

				self.recieved_id_cache.append((mid, nid))
				self.input_buffer.setdefault((roundn, stepn), []).append(msg)
				#print("input buffer at node", self.iden, ":", len(self.input_buffer[(roundn, stepn)]), " round:", roundn, " step: ", stepn)

				nid = int(nid)
				if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
					pass
					#print("Key verification successful for", self.iden)
				else:
					print("Error occured during Public Key verification.")
					continue

				self.put(msg)

	def get_output_conn(self, link):
		"""Takes a link as input, appends it to the 'out_links' list and retuns the corresponding *pipe*"""
		# # print("link from", link.src, "to", link.dest)
		self.out_links.append(link)
		return link

	def message_generator(self, env):
		#while True:2000
			#self.input_buffer = dict()
			#self.count_value = dict()
			#print("generator called at", self.iden)
			step = 0
			global prev_block
			round_no = prev_block.height
			prev_hsh = prev_block.hsh
			hsh, j = self.sortition((prev_hsh, round_no, step), T_PROPOSER, 'r') #TODO change 'r' to role

			proposed_block = None
			if j > 0:
				print("found a guy", self.iden)
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

				#env.process(self.delay(env, LAMBDA_PROPOSER))
				yield env.timeout(LAMBDA_PROPOSER) #TODO : Decide the delays
				#yield env.timeout(10000)
				#print("After Gossiping block proposal messages ", self.iden)
				p_vals = list()
				p_vals.append(str(hx))
				try:
					for msg in self.input_buffer[(round_no, step)]:
						c_sign = msg[1]
						decoded_msg = msg[0]
						payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
						rn, hs, subuser_no, priority = payload.split("<$>")
						p_vals.append(priority)
				except KeyError as e:
					print("No matching keys", e, " buffer:", self.input_buffer)

				if len(p_vals) != 0:
					least_p_val = min(p_vals)
				else: 
					least_p_val = hx 

				# print("After priority detection ", self.iden, " least", least_p_val, " mine", hx)
				if hx == least_p_val:
					#print("After priority detection ", self.iden, " least", least_p_val, " mine", hx)
					rand_string = str(random.getrandbits(32))
					proposed_block = Block(prev_block.hsh, rand_string, prev_block.height)
					bp_message_payload = str(prev_hsh) + "<@>" + rand_string + "<@>" + gossip_body
					bp_message_object = Message(self, bp_message_payload, 'b', round_no, step)
					self.recieved_id_cache.append((bp_message_object.msg_id, bp_message_object.node_id))
					self.put(bp_message_object.message)
					print("Block proposer selected", self.iden)

			if proposed_block == None:
				yield env.timeout(LAMBDA_PROPOSER + LAMBDA_BLOCK)
			else:
				yield env.timeout(LAMBDA_BLOCK)
		
			#print("Before Before Before Before Node: " + str(self.iden) + " Time: " + str(env.now))
			#yield env.timeout(10000)
			#print("After After After After Node: " + str(self.iden) + " Time: " + str(env.now))

			try:
				for msg in self.input_buffer[(round_no, step)]:
					c_sign = msg[1]
					decoded_msg = msg[0]
					payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")

					if m_type == 'b' and proposed_block == None:
						print("Block message recieved from " + str(nid) + " at node" + str(self.iden))
						prev_hsh, rand_string, priority_payload = payload.split("<@>")
						proposed_block = Block(prev_block.hsh, rand_string, prev_block.height)
					else:
						continue
			except KeyError as e:
				print("No matching keys", e, " buffer:", self.input_buffer)

			if proposed_block == None:
				proposed_block = Block(prev_block.hsh, "Empty", prev_block.height)

			#print("Starting Reduction on block " + proposed_block.s + " from node " + str(self.iden))
			# cur_block = yield env.process(self.reduction(proposed_block, round_no, prev_hsh))
			# #print("After Reduction", self.iden)
			# final_block = yield env.process(self.binaryBA(round_no, cur_block, prev_hsh))
			# #print("After BinaryBA", self.iden)
			# hash_block = self.count_votes(round_no, FINAL_STEP, T_FINAL, COMMITTEE_FINAL_FACTOR)

			# #TODO final consensus logic
			# if final_block.hsh == hash_block:
			# 	final_block.state = "Final"
			# else:
			# 	final_block.state = "Tentative"

			# prev_block = final_block
			# print("Block consensus achieved, block string", self.iden, final_block.s)

			#print("new round for", self.iden)
			#env.process(self.delay(env, 30))
			yield env.timeout(30) #TODO : Decide the delays
		#	input()
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
		#print("sortition called at", self.iden)
		hsh = PRG(s, self.sk)
		hsh_length = hsh.bit_length()
		p = thold / W_total_stake
		j = 0
		k = 0
		lower = 0
		higher = lower + scipy.stats.binom.pmf(k, self.stake, p)
		x = (hsh / (2 ** 256))
		#print('x', x)
		#print('lower, higher, p', lower, higher, p)
		#if x < lower then return j as 0
		#if x < lower:
		#	print("Sortition called by Node " + str(self.iden) + " returned sub user count " + str(j))
		#	return (hsh, j)
		while (x < lower or x >= higher) and j <= self.stake:
			j += 1
			lower = 0
			higher = 0

			for k in range(0, j):
				lower += scipy.stats.binom.pmf(k, self.stake, p)

			higher = lower + scipy.stats.binom.pmf(k+1, self.stake, p)
			#print('lower, higher, j', lower, higher, j)

		if j > 0:
			print("Sortition selected Node " + str(self.iden) + " returned sub user count " + str(j))
		return (hsh, j)

	def reduction(self, block, round_no, prev_hsh):
		#print("Reduction called by: " + str(self.iden))
		v_hash, v_j = self.sortition((prev_hsh, round_no, 0), T_PROPOSER, 'r')
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
			self.committee_vote(prev_hsh, round_no, step, T_STEP, hash_block, v_hash, v_j)
			yield env.timeout(LAMBDA_STEP)

		hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

		#print("Exiting reduction")
		if hash_block == None or hash_block != block.hsh:
			return empty_block
		else:
			return block


	def committee_vote(self, prev_hsh, round_no, step, threshold, block, v_hash, v_j):
		#print("Doing committee_vote for", self.iden)
		hsh, j = self.sortition((prev_hsh, round_no, step), threshold, 'c')
		if j > 0:
			vote_body = str(prev_hsh) + "<$>" + str(block.hsh) + "<$>" + str(round_no) + "<$>"\
			 + str(step) + "<$>" + str(v_j) + "<$>" + str(v_hash)
			vote_msg = Message(self, vote_body, 'nb', round_no, step)
			#print("Voting for step: " + str(step))
			self.recieved_id_cache.append((vote_msg.msg_id, vote_msg.node_id))		
			self.put(vote_msg.message)


	def count_votes(self, round_no, step, threshold, committee_size_factor):
		#print("Doing count_vote for", self.iden)
		try:
			voters = list()
			for msg in self.input_buffer[(round_no, step)]:
				c_sign = msg[1]
				decoded_msg = msg[0]
				payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
				prev_hsh, cur_hsh, r_no, s_no, v_j, v_hash = payload.split("<$>")

				nid = int(nid)
				if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
					pass
					#print("Key verification successful")
				else:
					print("Error occured during Public Key verification.")
					continue

				if prev_hsh != prev_block.hsh:
					continue

				hsh,votes = self.sortition((prev_hsh, round_no, step), threshold, 'c')

				if pk in voters or votes == 0:
					continue

				voters.append(pk)

				self.count_value[cur_hsh] = self.count_value.get(cur_hsh, 0) + votes

				if self.count_value[cur_hsh] > committee_size_factor * threshold:
					return cur_hsh

			return None

		except KeyError as e:
			print("No matching keys", e)

	def binaryBA(self, round_no, block, prev_hsh):
		step = 3
		cur_block = block
		empty_block = Block(prev_block.hsh, "Empty", prev_block.height)
		v_hash, v_j = self.sortition((prev_hsh, round_no, 0), T_PROPOSER, 'r')

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
				return cur_block
			step += 1

			self.committee_vote(prev_hsh, round_no, step, T_STEP, cur_block, v_hash, v_j)
			yield env.timeout(LAMBDA_STEP)
			hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

			if hash_block == None:
				cur_block = empty_block
			elif cur_block.hsh == empty_block.hsh:
				for s in range(step + 1, step + 4):
					self.committee_vote(prev_hsh, round_no, s, T_STEP, cur_block, v_hash, v_j)
					yield env.timeout(LAMBDA_STEP)
				return cur_block

			step += 1

			self.committee_vote(prev_hsh, round_no, step, T_STEP, cur_block, v_hash, v_j)
			yield env.timeout(LAMBDA_STEP)
			hash_block = self.count_votes(round_no, step, T_STEP, COMMITTEE_STEP_FACTOR)

			if hash_block == None:
				if self.common_coin(round_no, step, T_STEP) == 0:
					cur_block = block
				else:
					cur_block = empty_block

			step += 1

		print("Inside BinaryBA, hanging forever...", self.iden)
		while True:
			continue

	def common_coin(self, round_no, step, threshold):
		min_hash = str(1)
		votes = 0
		try:
			for msg in self.input_buffer[(round_no, step)]:
				c_sign = msg[1]
				decoded_msg = msg[0]
				payload, pk, mid, nid, m_type, roundn, stepn = decoded_msg.split("<|>")
				prev_hsh, cur_hsh, r_no, s_no, v_j, v_hash = payload.split("<$>")

				nid = int(nid)
				if ecdsa.verify(c_sign, decoded_msg, pks[nid]):
					pass
					#print("Key verification successful")
				else:
					print("Error occured during Public Key verification.")
					votes = 0

				if prev_hsh != prev_block.hsh:
					votes = 0

				hsh,votes = self.sortition((prev_hsh, round_no, step), threshold, 'c')

				if votes > 0:
					hash_string = str(hsh) + str(1)
					min_hash = str(hashlib.sha256(hash_string.encode()).hexdigest())

					for i in range(2, votes + 1):
						hash_string = str(hsh) + str(i)
						h = str(hashlib.sha256(hash_string.encode()).hexdigest())
						min_hash = min(h, min_hash)

		except KeyError as e:
			print("No matching keys", e)

		#print("Common Coin: ", min_hash)
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

print("m", node_conn_matrix)
# print("dm", delay_matrix)
# print("bm", block_delay_matrix)
gb = Block(None, "We are buildling the best Algorand Discrete Event Simulator", -1)
gb.state = "Final"
prev_block = gb  # to know the current leader block

#print("Genesis bock created: " + str(prev_block))
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
