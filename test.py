import requests

tests ="""abo10.c
abo2.c
abo3.c
abo4.c
abo5.c
abo6.c
abo7.c
abo8.c
abo9.c
e1.c
e2.c
e3.c
e4.c
e5.c
fs1.c
fs2.c
fs3.c
fs4.c
fs5.c
n1.c
n2.c
n3.c
n4.c
n5.c
s1.c
s2.c
s3.c
s4.c
sg1.c
sg2.c
sg3.c
sg4.c
sg5.c
sg6.c
stack1.c
stack2.c
stack3.c
stack4.c
stack5.c
""".strip().split("\n")

def send_task(entrypoint: str):
    print(f"[*] Sending test: {entrypoint}")
    requests.post(
        "http://127.0.0.1:5000/analyze",
        data={
            "entrypoint": f"exercises/{entrypoint}",
            "repository": "https://github.com/gerasdf/InsecureProgramming.git",
        },
    )

for test in tests:
    send_task(test)
