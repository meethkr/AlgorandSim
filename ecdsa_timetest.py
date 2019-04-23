from fastecdsa import keys, curve, ecdsa
import time

pk = dict()
sk = dict()
m = dict()
r = dict()
s = dict()

start = time.time()
for i in range(200):
    print("Gen, sign for", i)
    sk[i], pk[i] = keys.gen_keypair(curve.P256)
    m[i] = str(i) * 4096
    r[i] = ecdsa.sign(m[i], sk[i]) 
    print(r[i])
end = time.time()

print("time for key generation and signing:", end - start)

start = time.time()
for i in range(200):
    print(ecdsa.verify(r[i], m[i]+"i", pk[i]))

end = time.time()

print("time for verification:", end - start)
