from collections import Counter

print("Hello World")

nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def get_x(nums):
    for num in nums:
        if num > 5:
            print(f"{num} is greater than 5")
    
get_x(nums)