import csv
import numpy as np

NODE_COUNT = 256
MIN_DEG = 2
MAX_DEG = 4

node_conn_counts = np.random.randint(MIN_DEG, MAX_DEG+1, NODE_COUNT)

# 1. matrix of connections
node_conn_matrix = list()
for i in range(NODE_COUNT):
    node_conn_matrix.append([(int)((i-1) % (NODE_COUNT)), (int)((i+1) % (NODE_COUNT))])
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
            node_conn_matrix[i].append((int)(ti))
            node_conn_matrix[ti].append((int)(i))
        else:
            break

with open("node_matrix.csv", 'w', newline='') as f:
    wr = csv.writer(f, quoting=csv.QUOTE_ALL)
    for row in node_conn_matrix:
        wr.writerow(row)

f.close()