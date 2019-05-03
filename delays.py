import csv
import numpy as np

NODE_COUNT = 256
MIN_DEG = 2
MAX_DEG = 4
DELAY_MEAN = 30
DELAY_SD = 64

with open('node_matrix.csv', 'r') as input_file:
    reader = csv.reader(input_file)
    node_conn_matrix = list(reader)
    #print(node_conn_matrix)
input_file.close()

# 2. delays
delay_matrix = list()
block_delay_matrix = list()
for i in node_conn_matrix:
    i.sort()
    delay_matrix.append([])
    block_delay_matrix.append([])

for i in range(NODE_COUNT):
    for j in node_conn_matrix[i]:
        j = int(j)
        if j > i:
            x = int(max(np.random.normal(DELAY_MEAN, DELAY_SD), 0))
            delay_matrix[i].append(x)
            delay_matrix[j].append(x)
            y = int(max(np.random.normal(200, 400), 0))
            block_delay_matrix[i].append(y)
            block_delay_matrix[j].append(y)

print("Delay")
with open("delay_matrix.csv", 'w', newline='') as f:
    wr = csv.writer(f, quoting=csv.QUOTE_ALL)
    for row in delay_matrix:
        #print(row)
        wr.writerow(row)

f.close()

print("Block delay")
with open("block_delay_matrix.csv", 'w', newline='') as f:
    wr = csv.writer(f, quoting=csv.QUOTE_ALL)
    for row in block_delay_matrix:
        #print(row)
        wr.writerow(row)

f.close()