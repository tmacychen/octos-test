# A-B-A-B loop example
def abab_loop(iterations):
    for i in range(iterations):
        if i % 2 == 0:
            print("A")
        else:
            print("B")

if __name__ == "__main__":
    abab_loop(10)
