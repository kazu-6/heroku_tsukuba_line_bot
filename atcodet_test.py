n = int(input())
e = [[int(i) for i in input().split()] for i in range(n)]

numbers = e[0]

def has_odd(numbers):
    odds = [number for number in numbers if number%2 == 1]
    if len(odds) > 0:
        return True
    else:
        return False

divid_count = 0
while True:

    if not has_odd(numbers):
        numbers = [int(number/2) for number in numbers]
        divid_count += 1
    else:
        break

print(divid_count)